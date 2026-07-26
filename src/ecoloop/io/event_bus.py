"""Live event bus for PoC demo (JSONL stream + optional stdout).

EnergyPlus plugin and LLM agent emit structured events that the demo TUI tails.
"""

from __future__ import annotations

import json
import os
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from ecoloop.config import ROOT

EVENT_FILE = Path(os.getenv("ECOLOOP_EVENT_FILE", str(ROOT / "loop_events.jsonl")))
_lock = threading.Lock()
_seq = 0


def clear_events() -> None:
    """Wipe the event log (start of a demo run)."""
    global _seq
    with _lock:
        _seq = 0
        if EVENT_FILE.exists():
            EVENT_FILE.unlink()


def emit(kind: str, **payload: Any) -> dict:
    """Append one structured event and return it.

    kind examples:
      - status, sim_clock, tool_call, tool_result
      - llm_request, llm_thinking, llm_response, llm_parse
      - guardrail, actuate, decision, error
    """
    global _seq
    with _lock:
        _seq += 1
        event = {
            "seq": _seq,
            "ts": datetime.now().isoformat(timespec="milliseconds"),
            "wall_clock": time.time(),
            "kind": kind,
            **payload,
        }
        EVENT_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(EVENT_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, default=str) + "\n")
            f.flush()
        return event


def tail_events(offset: int = 0) -> tuple[list[dict], int]:
    """Read new events from byte offset. Returns (events, new_offset)."""
    if not EVENT_FILE.exists():
        return [], offset
    with open(EVENT_FILE, "rb") as f:
        f.seek(offset)
        chunk = f.read()
        new_offset = f.tell()
    if not chunk:
        return [], new_offset
    events: list[dict] = []
    for line in chunk.decode("utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events, new_offset
