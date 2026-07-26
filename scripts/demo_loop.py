#!/usr/bin/env python3
"""
EcoLoop PoC Demonstration TUI
=============================

Live view of the closed control loop for a max-3-minute demo video:

  EnergyPlus sensors  →  tool calls  →  LLM thinking  →  JSON decision
       →  ASHRAE guardrail  →  schedule actuators  →  back into the model

Usage
-----
  # Recommended for video (1-day sim, ~24 LLM decisions):
  python scripts/demo_loop.py

  # Watch-only (if EnergyPlus already running elsewhere):
  python scripts/demo_loop.py --watch

  # Full 7-day AI run under the same TUI:
  python scripts/demo_loop.py --mode ai

  # Headless event stream (no full-screen redraw):
  python scripts/demo_loop.py --plain

Requires: llama-server (or compatible) on LLM_BASE_URL (default localhost:8080).
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ecoloop.config import LLM_BASE_URL, LLM_MODEL, ROOT as ECO_ROOT  # noqa: E402
from ecoloop.io.event_bus import EVENT_FILE, clear_events, tail_events  # noqa: E402
from ecoloop.io.state_store import STATE_FILE, clear_state  # noqa: E402

# ── ANSI helpers ────────────────────────────────────────────────────────────
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
MAGENTA = "\033[35m"
RED = "\033[31m"
BLUE = "\033[34m"
WHITE = "\033[37m"
BG = "\033[40m"


def _c(color: str, text: str) -> str:
    return f"{color}{text}{RESET}"


def _trunc(text: str, n: int) -> str:
    text = text.replace("\r", " ").replace("\n", " ")
    if len(text) <= n:
        return text
    return text[: max(0, n - 1)] + "…"


def _bar(value: float, lo: float, hi: float, width: int = 20) -> str:
    if hi <= lo:
        return "·" * width
    frac = max(0.0, min(1.0, (value - lo) / (hi - lo)))
    filled = int(round(frac * width))
    return "█" * filled + "░" * (width - filled)


import re as _re
_ANSI_RE = _re.compile(r"\033\[[0-9;]*m")


def _ansi_strip(s: str) -> str:
    """Return string with ANSI escape codes removed (visual width only)."""
    return _ANSI_RE.sub("", s)


def _pad(s: str, width: int) -> str:
    """Pad string s to exact visual width, correctly accounting for ANSI codes."""
    vis_len = len(_ansi_strip(s))
    return s + " " * max(0, width - vis_len)


def check_llm() -> tuple[bool, str]:
    try:
        req = urllib.request.Request(LLM_BASE_URL.rstrip("/") + "/models")
        with urllib.request.urlopen(req, timeout=3) as resp:
            body = json.loads(resp.read().decode())
        models = body.get("data") or body.get("models") or []
        ids = [m.get("id") or m.get("name") or "?" for m in models]
        return True, ", ".join(ids) if ids else "ok"
    except Exception as e:
        return False, str(e)


@dataclass
class LoopState:
    sim_clock: dict = field(default_factory=dict)
    zone: dict = field(default_factory=dict)
    energy: dict = field(default_factory=dict)
    weather: dict = field(default_factory=dict)
    thinking: str = ""
    llm_content: str = ""
    last_prompt: str = ""
    last_tool: str = ""
    tool_log: deque = field(default_factory=lambda: deque(maxlen=12))
    event_log: deque = field(default_factory=lambda: deque(maxlen=14))
    decisions: int = 0
    fallbacks: int = 0
    last_decision: dict = field(default_factory=dict)
    heat_sp: float | None = None
    cool_sp: float | None = None
    status: str = "starting"
    llm_elapsed: float | None = None
    sim_running: bool = False
    sim_rc: int | None = None
    started_at: float = field(default_factory=time.time)


def apply_event(st: LoopState, ev: dict) -> None:
    kind = ev.get("kind", "")
    st.event_log.appendleft(
        f"{ev.get('ts', '')[-12:]}  {kind:<12}  {_trunc(json.dumps({k: v for k, v in ev.items() if k not in ('ts', 'wall_clock', 'seq', 'kind', 'thinking', 'text', 'user_prompt', 'content', 'reasoning')}, default=str), 70)}"
    )

    if kind == "sim_clock":
        st.sim_clock = {
            k: ev.get(k) for k in ("year", "month", "day", "hour", "minute") if k in ev
        }
    elif kind == "tool_call":
        tool = ev.get("tool", "?")
        st.last_tool = f"→ {tool}({json.dumps(ev.get('args') or {}, default=str)})"
        st.tool_log.appendleft(_c(YELLOW, f"CALL  {tool}"))
    elif kind == "tool_result":
        tool = ev.get("tool", "?")
        result = ev.get("result") or {}
        st.tool_log.appendleft(
            _c(GREEN, f"RET   {tool} → {_trunc(json.dumps(result, default=str), 64)}")
        )
        if tool == "get_zone_state" and "error" not in result:
            st.zone = result
        elif tool == "get_energy_metrics" and "error" not in result:
            st.energy = result
        elif tool == "get_weather_lookahead" and "error" not in result:
            st.weather = result
    elif kind == "llm_request":
        st.last_prompt = ev.get("user_prompt") or ""
        # Do NOT clear thinking/content here — keep previous decision's trace
        # visible during the ~15s LLM wait instead of showing blank
        st.status = "calling LLM…"
    elif kind == "llm_thinking":
        st.thinking = ev.get("text") or ""
        st.llm_elapsed = ev.get("elapsed_s")
        st.status = "LLM thinking…"
    elif kind == "llm_response":
        st.llm_content = ev.get("content") or ""
        if ev.get("reasoning"):
            st.thinking = ev["reasoning"]
        st.llm_elapsed = ev.get("elapsed_s")
        st.status = "LLM response received"
    elif kind == "llm_parse":
        if ev.get("ok"):
            st.status = f"parsed setpoints ({ev.get('source')})"
        elif ev.get("fallback"):
            st.fallbacks += 1
            st.status = "LLM fallback (holding last-good)"
        else:
            st.status = "parse failed — retrying"
    elif kind == "guardrail":
        clamped = ev.get("clamped") or {}
        st.heat_sp = clamped.get("heating_sp")
        st.cool_sp = clamped.get("cooling_sp")
        st.status = "guardrail clamped" if ev.get("changed") else "guardrail ok"
    elif kind == "actuate":
        st.heat_sp = ev.get("heating_sp", st.heat_sp)
        st.cool_sp = ev.get("cooling_sp", st.cool_sp)
        st.status = (
            f"ACTUATE heat={st.heat_sp}°C cool={st.cool_sp}°C → EnergyPlus schedules"
        )
    elif kind == "decision":
        if ev.get("phase") == "complete":
            st.decisions += 1
            st.last_decision = ev
            st.heat_sp = ev.get("applied_heating_sp", st.heat_sp)
            st.cool_sp = ev.get("applied_cooling_sp", st.cool_sp)
            if ev.get("zone_data"):
                st.zone = ev["zone_data"]
            if ev.get("energy_data"):
                st.energy = ev["energy_data"]
            if ev.get("weather_data"):
                st.weather = ev["weather_data"]
            if ev.get("thinking"):
                st.thinking = ev["thinking"]
            if ev.get("sim_clock"):
                st.sim_clock = ev["sim_clock"]
            st.status = f"decision #{ev.get('decision_num')} complete"
        else:
            st.status = f"decision #{ev.get('decision_num')} started"
    elif kind == "status":
        st.status = str(ev.get("message") or st.status)
    elif kind == "error":
        st.status = f"ERROR: {ev.get('message')}"


def render(st: LoopState, term_w: int, term_h: int) -> str:
    w = max(80, term_w)
    col = max(36, (w - 6) // 2)
    elapsed = time.time() - st.started_at

    clock = st.sim_clock
    clock_s = "—"
    if clock:
        clock_s = (
            f"{clock.get('month', '?'):0>2}/{clock.get('day', '?'):0>2} "
            f"{clock.get('hour', '?'):0>2}:{str(clock.get('minute', 0)).zfill(2)}"
        )

    zone_t = st.zone.get("temperature_c")
    pmv = st.zone.get("pmv")
    outdoor = st.weather.get("current_temp")
    forecast = st.weather.get("future_temps") or []
    hvac_w = st.energy.get("hvac_w")
    bldg_w = st.energy.get("building_w")

    def kv(label: str, value: str) -> str:
        return f"  {_c(DIM, label.ljust(12))} {value}"

    # ── Header ──
    lines: list[str] = []
    title = "EcoLoop  ·  Live EnergyPlus ↔ LLM Control Loop  ·  PoC Demo"
    lines.append(_c(BOLD + CYAN, "╔" + "═" * (w - 2) + "╗"))
    lines.append(
        _c(BOLD + CYAN, "║")
        + _c(BOLD + WHITE, title.center(w - 2))
        + _c(BOLD + CYAN, "║")
    )
    sub = (
        f"model={LLM_MODEL}  endpoint={LLM_BASE_URL}  "
        f"decisions={st.decisions}  fallbacks={st.fallbacks}  "
        f"t+{elapsed:5.0f}s  sim={'RUN' if st.sim_running else ('done' if st.sim_rc is not None else '…')}"
    )
    lines.append(
        _c(CYAN, "║") + _c(DIM, _trunc(sub, w - 2).ljust(w - 2)) + _c(CYAN, "║")
    )
    lines.append(_c(CYAN, "╠" + "═" * (w - 2) + "╣"))

    # ── Two-column top: ENV | ACTUATORS ──
    left: list[str] = []
    left.append(_c(BOLD + GREEN, " ENVIRONMENT (EnergyPlus sensors)"))
    left.append(kv("sim clock", _c(BOLD + WHITE, clock_s)))
    if zone_t is not None:
        left.append(
            kv(
                "zone temp",
                f"{_c(BOLD, f'{zone_t:5.2f} °C')}  {_bar(zone_t, 18, 30)}",
            )
        )
    else:
        left.append(kv("zone temp", "waiting…"))
    if pmv is not None:
        pmv_color = GREEN if abs(pmv) <= 0.5 else (YELLOW if abs(pmv) <= 0.8 else RED)
        left.append(
            kv("PMV", f"{_c(pmv_color + BOLD, f'{pmv:+.3f}')}  (comfort ±0.5)")
        )
    else:
        left.append(kv("PMV", "waiting…"))
    if outdoor is not None:
        left.append(kv("outdoor", f"{outdoor:.1f} °C"))
    if forecast:
        left.append(kv("forecast 6h", ", ".join(f"{t:.0f}" for t in forecast)))
    if hvac_w is not None:
        left.append(kv("HVAC power", f"{hvac_w:.0f} W"))
    if bldg_w is not None:
        left.append(kv("Building", f"{bldg_w:.0f} W"))

    right: list[str] = []
    right.append(_c(BOLD + MAGENTA, " CONTROL ACTIONS → model parameters"))
    if st.heat_sp is not None and st.cool_sp is not None:
        right.append(
            kv(
                "heating sp",
                f"{_c(BOLD + YELLOW, f'{st.heat_sp:.1f} °C')}  → schedule Htg-SetP-Sch",
            )
        )
        right.append(
            kv(
                "cooling sp",
                f"{_c(BOLD + CYAN, f'{st.cool_sp:.1f} °C')}  → schedule Clg-SetP-Sch",
            )
        )
        right.append(
            kv("deadband", f"{st.cool_sp - st.heat_sp:.1f} K  (min 2.0)")
        )
        right.append(
            kv(
                "bars",
                f"H {_bar(st.heat_sp, 18, 24, 12)}  C {_bar(st.cool_sp, 22, 28, 12)}",
            )
        )
    else:
        right.append(kv("setpoints", "awaiting first LLM decision…"))
    ld = st.last_decision
    if ld:
        dnum = ld.get("decision_num", "?")
        src = ld.get("source") or (ld.get("raw_decision") or {}).get("source") or "—"
        right.append(kv("last dec #", _c(BOLD + WHITE, str(dnum)) + f"  src={src}"))
        reason = (
            ld.get("reasoning")
            or (ld.get("raw_decision") or {}).get("reasoning")
            or ""
        )
        right.append(kv("reasoning", _c(DIM + WHITE, _trunc(str(reason), col - 16))))
    right.append(kv("status", _c(YELLOW if "LLM" in st.status else WHITE, _trunc(st.status, col - 16))))

    rows = max(len(left), len(right))
    left += [""] * (rows - len(left))
    right += [""] * (rows - len(right))
    for a, b in zip(left, right):
        # Use _pad() which strips ANSI codes before calculating pad width,
        # so the divider │ stays aligned regardless of colored text in left column
        lines.append(
            _c(CYAN, "║")
            + _pad(a, col + 2)
            + _c(DIM, " │ ")
            + b
        )

    lines.append(_c(CYAN, "╠" + "═" * (w - 2) + "╣"))

    # ── Tool calls ──
    lines.append(_c(BOLD + YELLOW, " TOOL CALLS  (EnergyPlus → agent observations)"))
    if st.tool_log:
        for entry in list(st.tool_log)[:8]:
            lines.append("  " + entry)
    else:
        lines.append(_c(DIM, "  (waiting for first hourly gate…)"))

    lines.append(_c(CYAN, "╠" + "═" * (w - 2) + "╣"))

    # ── Thinking + response ──
    is_calling = "calling LLM" in st.status or "thinking" in st.status
    think_label = (
        _c(BOLD + BLUE, " LLM THINKING TRACE")
        + _c(DIM, f"   latency={st.llm_elapsed or '—'}s")
        + (_c(YELLOW, "  ⟳ computing…") if is_calling else "")
    )
    lines.append(think_label)
    think_raw = (st.thinking or "").strip()
    if think_raw:
        # Strip markdown bold (**text**) and leading bullet numbers for clean display
        think_clean = _re.sub(r"\*\*(.*?)\*\*", r"\1", think_raw)
        for ln in think_clean.splitlines()[:14]:
            ln = ln.strip()
            if not ln:
                continue
            # Colour bullet points cyan, sub-bullets white
            if ln and ln[0].isdigit():
                lines.append(_c(CYAN, "  " + _trunc(ln, w - 4)))
            else:
                lines.append(_c(WHITE, "    " + _trunc(ln, w - 6)))
    else:
        lines.append(_c(DIM, "  (waiting for first LLM response…)"))
    if st.llm_content:
        lines.append(_c(BOLD + GREEN, " LLM FINAL JSON OUTPUT"))
        for ln in st.llm_content.strip().splitlines()[:4]:
            lines.append(_c(GREEN, "  " + _trunc(ln, w - 4)))

    lines.append(_c(CYAN, "╠" + "═" * (w - 2) + "╣"))

    # ── Event feed ──
    lines.append(_c(BOLD + WHITE, " EVENT STREAM  (loop_events.jsonl)"))
    for entry in list(st.event_log)[:8]:
        lines.append(_c(DIM, "  " + _trunc(entry, w - 4)))

    lines.append(_c(CYAN, "╚" + "═" * (w - 2) + "╝"))
    lines.append(
        _c(
            DIM,
            "  Record this terminal · Ctrl+C stops viewer (sim may keep running) · "
            f"events: {EVENT_FILE.name}",
        )
    )

    # Fit to terminal height
    if term_h > 10 and len(lines) > term_h - 1:
        lines = lines[: term_h - 1]
    return "\n".join(lines)


def clear_screen() -> None:
    # Home + clear-down keeps flicker lower than full reset on some hosts
    sys.stdout.write("\033[H\033[J")
    sys.stdout.flush()


def term_size() -> tuple[int, int]:
    size = shutil.get_terminal_size(fallback=(110, 40))
    return size.columns, size.lines


def run_sim_thread(mode: str, st: LoopState, proc_holder: dict) -> None:
    """Launch EnergyPlus in a subprocess; stream nothing (events come via JSONL)."""
    from ecoloop.config import (
        EPW_PATH,
        EPLUS_INSTALL,
        IDF_PATH,
        OUTPUT_DIR_AI,
        OUTPUT_DIR_DEMO,
    )

    eplus = EPLUS_INSTALL / "energyplus.exe"
    # Always use the working 7-day IDF — the 1-day model has sizing issues.
    # ECOLOOP_MAX_DECISIONS caps how many LLM calls fire, keeping demo short.
    if mode == "demo":
        idf = IDF_PATH  # 7-day IDF, decisions capped via ECOLOOP_MAX_DECISIONS
        out = OUTPUT_DIR_DEMO
        control = "ai"
    else:
        idf = IDF_PATH
        out = OUTPUT_DIR_AI
        control = "ai"

    out.mkdir(parents=True, exist_ok=True)
    for f in out.glob("*"):
        try:
            if f.is_file():
                f.unlink()
        except Exception:
            pass

    env = os.environ.copy()
    env["ECOLOOP_CONTROL_MODE"] = control
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONPATH"] = str(ECO_ROOT / "src") + os.pathsep + env.get("PYTHONPATH", "")
    # Propagated from main() via env for short PoC clips
    if "ECOLOOP_MAX_DECISIONS" not in env:
        env["ECOLOOP_MAX_DECISIONS"] = os.environ.get("ECOLOOP_MAX_DECISIONS", "0")

    cmd = [str(eplus), "-d", str(out), "-w", str(EPW_PATH), str(idf)]
    st.status = f"launching EnergyPlus ({mode})"
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(ECO_ROOT),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        proc_holder["proc"] = proc
        st.sim_running = True
        # Drain stdout so the pipe never blocks; interesting lines → status
        assert proc.stdout is not None
        for line in proc.stdout:
            line = line.rstrip()
            if not line:
                continue
            if any(
                k in line
                for k in ("[PLUGIN]", "[AGENT]", "Starting", "EnergyPlus", "Warming")
            ):
                st.event_log.appendleft(_c(DIM, _trunc(f"E+ {line}", 90)))
        rc = proc.wait()
        st.sim_rc = rc
        st.sim_running = False
        st.status = f"EnergyPlus exited rc={rc}"
    except Exception as e:
        st.sim_running = False
        st.sim_rc = -1
        st.status = f"sim launch failed: {e}"


def plain_mode(st: LoopState, stop: threading.Event) -> None:
    offset = 0
    while not stop.is_set():
        events, offset = tail_events(offset)
        for ev in events:
            apply_event(st, ev)
            kind = ev.get("kind")
            if kind in (
                "tool_call",
                "tool_result",
                "llm_thinking",
                "llm_response",
                "llm_parse",
                "guardrail",
                "actuate",
                "decision",
                "error",
                "status",
            ):
                ts = str(ev.get("ts", ""))[-12:]
                summary = {
                    k: v
                    for k, v in ev.items()
                    if k
                    not in (
                        "ts",
                        "wall_clock",
                        "seq",
                        "kind",
                        "thinking",
                        "text",
                        "user_prompt",
                        "content",
                        "reasoning",
                    )
                }
                print(f"{ts}  {kind:<12}  {json.dumps(summary, default=str)[:160]}", flush=True)
                if kind == "llm_thinking" and ev.get("text"):
                    print(_c(DIM, "  THINK: " + _trunc(ev["text"], 200)), flush=True)
                if kind == "llm_response" and ev.get("content"):
                    print(_c(GREEN, "  CONTENT: " + _trunc(ev["content"], 200)), flush=True)
                if kind == "actuate":
                    print(
                        _c(
                            MAGENTA,
                            f"  >>> SET heat={ev.get('heating_sp')} cool={ev.get('cooling_sp')}",
                        ),
                        flush=True,
                    )
        if not st.sim_running and st.sim_rc is not None and not events:
            # Drain remaining then exit after quiet period
            time.sleep(0.5)
            events, offset = tail_events(offset)
            if not events:
                break
        time.sleep(0.15)


def tui_mode(st: LoopState, stop: threading.Event) -> None:
    offset = 0
    # Enable ANSI on Windows
    if os.name == "nt":
        os.system("")  # enables VT processing in many Windows consoles
    while not stop.is_set():
        events, offset = tail_events(offset)
        for ev in events:
            apply_event(st, ev)
        tw, th = term_size()
        frame = render(st, tw, th)
        clear_screen()
        sys.stdout.write(frame)
        sys.stdout.flush()
        if not st.sim_running and st.sim_rc is not None:
            # Keep final frame up briefly so recorder captures summary
            time.sleep(0.4)
            events, offset = tail_events(offset)
            for ev in events:
                apply_event(st, ev)
            if not events:
                # one last paint
                clear_screen()
                sys.stdout.write(render(st, *term_size()))
                sys.stdout.flush()
                break
        time.sleep(0.12)


def main() -> int:
    parser = argparse.ArgumentParser(description="EcoLoop PoC live demo TUI")
    parser.add_argument(
        "--mode",
        choices=("demo", "ai"),
        default="demo",
        help="demo=1-day IDF (default), ai=7-day full run",
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Do not launch EnergyPlus; only tail loop_events.jsonl",
    )
    parser.add_argument(
        "--plain",
        action="store_true",
        help="Print event stream instead of full-screen TUI",
    )
    parser.add_argument(
        "--no-clear",
        action="store_true",
        help="Do not wipe previous state/event logs",
    )
    parser.add_argument(
        "--max-decisions",
        type=int,
        default=10,
        help="Cap LLM decisions for a short video (default 10; 0 = unlimited)",
    )
    args = parser.parse_args()

    ok, detail = check_llm()
    print(_c(BOLD, "EcoLoop PoC Demo"), flush=True)
    print(f"  LLM: {LLM_BASE_URL}  model={LLM_MODEL}", flush=True)
    if ok:
        print(_c(GREEN, f"  LLM server OK ({detail})"), flush=True)
    else:
        print(_c(RED, f"  LLM server NOT reachable: {detail}"), flush=True)
        print(_c(YELLOW, "  Start llama-server on :8080 then re-run."), flush=True)
        if not args.watch:
            return 2

    if not args.no_clear and not args.watch:
        clear_state()
        clear_events()
        print(f"  Cleared {STATE_FILE.name} + {EVENT_FILE.name}", flush=True)

    # Cap decisions for a ~3 min video (each LLM call ~5–15s)
    if args.max_decisions and args.max_decisions > 0:
        os.environ["ECOLOOP_MAX_DECISIONS"] = str(args.max_decisions)
        print(
            _c(YELLOW, f"  ECOLOOP_MAX_DECISIONS={args.max_decisions} (short PoC clip)"),
            flush=True,
        )
    else:
        os.environ["ECOLOOP_MAX_DECISIONS"] = "0"

    st = LoopState()
    stop = threading.Event()
    proc_holder: dict = {}

    if not args.watch:
        t = threading.Thread(
            target=run_sim_thread, args=(args.mode, st, proc_holder), daemon=True
        )
        t.start()
        print(
            _c(CYAN, f"  Launching EnergyPlus control_mode=ai  run={args.mode}…"),
            flush=True,
        )
        time.sleep(0.8)
    else:
        st.status = "watch mode — tailing events"
        print(_c(CYAN, "  Watch mode: tailing events only"), flush=True)

    if not args.plain:
        print(_c(DIM, "  Entering live TUI in 1s…"), flush=True)
        time.sleep(1.0)

    try:
        if args.plain:
            plain_mode(st, stop)
        else:
            tui_mode(st, stop)
    except KeyboardInterrupt:
        stop.set()
        print("\n" + _c(YELLOW, "Viewer stopped."), flush=True)
    finally:
        stop.set()
        proc = proc_holder.get("proc")
        if proc and proc.poll() is None:
            print(_c(DIM, "EnergyPlus still running in background (leave it, or kill the process)."), flush=True)

    print(
        _c(
            BOLD,
            f"\nDone. decisions={st.decisions} fallbacks={st.fallbacks} "
            f"last heat={st.heat_sp} cool={st.cool_sp}",
        ),
        flush=True,
    )
    print(f"  Events : {EVENT_FILE}", flush=True)
    print(f"  History: {STATE_FILE}", flush=True)
    return 0 if (st.fallbacks == 0 or st.decisions > st.fallbacks) else 0


if __name__ == "__main__":
    raise SystemExit(main())
