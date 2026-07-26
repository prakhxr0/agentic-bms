"""LLM agent client for HVAC setpoint decisions (OpenAI-compatible).

Handles Gemma-style models that emit long reasoning_content before a final
JSON answer in content. Emits live events for the PoC demo TUI.
"""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request

from ecoloop.config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL
from ecoloop.io.event_bus import emit

SYSTEM_PROMPT = """You are a Building Energy Supervisor AI controlling an EnergyPlus HVAC model.

TASK: Choose heating_sp and cooling_sp to save energy while keeping PMV near 0 (ASHRAE 55 band -0.5..+0.5).

HARD RULES:
- Heating: 18.0-24.0 C
- Cooling: 22.0-28.0 C
- Cooling >= Heating + 2.0 C (deadband)
- If PMV < -0.5 (too cold): raise heating and/or lower cooling
- If PMV > +0.5 (too hot): lower cooling and/or raise heating
- Use weather lookahead to anticipate outdoor changes
- Widen deadband in mild weather to save energy

THINKING: Keep internal reasoning under 6 short bullets.
OUTPUT: After thinking, output EXACTLY one JSON object and stop. No markdown fences.
Schema: {"heating_sp": <float>, "cooling_sp": <float>, "reasoning": "<one sentence>"}"""


def _parse_json(text: str) -> dict | None:
    """Extract a setpoint JSON object from free-form model text."""
    if not text:
        return None
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        text = text.strip()
    try:
        obj = json.loads(text)
        if isinstance(obj, dict) and "heating_sp" in obj and "cooling_sp" in obj:
            return obj
    except json.JSONDecodeError:
        pass

    # Prefer objects that look like our schema
    for match in re.finditer(
        r"\{[^{}]*\"heating_sp\"[^{}]*\"cooling_sp\"[^{}]*\}", text, re.DOTALL
    ):
        try:
            obj = json.loads(match.group())
            if isinstance(obj, dict) and "heating_sp" in obj and "cooling_sp" in obj:
                return obj
        except json.JSONDecodeError:
            continue

    # Last-ditch: any single-level object with both keys (any order)
    for match in re.finditer(r"\{[^{}]+\}", text, re.DOTALL):
        try:
            obj = json.loads(match.group())
            if isinstance(obj, dict) and "heating_sp" in obj and "cooling_sp" in obj:
                return obj
        except json.JSONDecodeError:
            continue
    return None


def _build_memory_summary(memory: list) -> str:
    if not memory:
        return "No prior decisions."
    lines = []
    for m in memory[-3:]:
        hs = m.get("heating_sp", "?")
        cs = m.get("cooling_sp", "?")
        pmv = m.get("pmv", "?")
        lines.append(f"heating={hs} cooling={cs} -> PMV={pmv}")
    return "Previous decisions: " + "; ".join(lines)


def _normalize_message(msg: dict) -> tuple[str, str, str]:
    """Return (content, reasoning, combined) from an OpenAI-style message."""
    content = msg.get("content") or ""
    if isinstance(content, list):
        # Some servers return multimodal content parts
        parts = []
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text":
                parts.append(part.get("text") or "")
            elif isinstance(part, str):
                parts.append(part)
        content = "".join(parts)

    reasoning = (
        msg.get("reasoning_content")
        or msg.get("reasoning")
        or msg.get("thinking")
        or ""
    )
    if isinstance(reasoning, list):
        reasoning = " ".join(str(x) for x in reasoning)

    # Strip empty content that is just whitespace
    content = content.strip() if isinstance(content, str) else ""
    reasoning = reasoning.strip() if isinstance(reasoning, str) else ""
    combined = "\n".join(p for p in (content, reasoning) if p)
    return content, reasoning, combined


def _call_llm(user_prompt: str, decision_num: int | None = None) -> dict:
    """Call chat/completions. Returns dict with content/reasoning/raw/error/elapsed."""
    payload = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.3,
        "max_tokens": 1024,
        "top_p": 0.9,
    }
    body_bytes = json.dumps(payload).encode()

    emit(
        "llm_request",
        decision_num=decision_num,
        endpoint=LLM_BASE_URL + "/chat/completions",
        model=LLM_MODEL,
        max_tokens=payload["max_tokens"],
        prompt_chars=len(user_prompt),
        user_prompt=user_prompt,
    )

    req = urllib.request.Request(
        LLM_BASE_URL + "/chat/completions",
        data=body_bytes,
        headers={
            "Authorization": f"Bearer {LLM_API_KEY}",
            "Content-Type": "application/json",
        },
    )

    try:
        start = time.time()
        with urllib.request.urlopen(req, timeout=90) as resp:
            body = json.loads(resp.read().decode())
        elapsed = time.time() - start
        msg = body["choices"][0]["message"]
        content, reasoning, combined = _normalize_message(msg)
        finish = body["choices"][0].get("finish_reason")
        usage = body.get("usage") or {}

        if reasoning:
            emit(
                "llm_thinking",
                decision_num=decision_num,
                text=reasoning,
                chars=len(reasoning),
                elapsed_s=round(elapsed, 2),
            )
        emit(
            "llm_response",
            decision_num=decision_num,
            content=content,
            reasoning=reasoning,
            finish_reason=finish,
            elapsed_s=round(elapsed, 2),
            usage=usage,
            content_chars=len(content),
            reasoning_chars=len(reasoning),
        )
        print(
            f"[AGENT] LLM ok ({elapsed:.1f}s) content={len(content)}c "
            f"thinking={len(reasoning)}c finish={finish}",
            flush=True,
        )
        return {
            "content": content,
            "reasoning": reasoning,
            "combined": combined,
            "elapsed_s": elapsed,
            "finish_reason": finish,
            "usage": usage,
            "error": None,
        }
    except Exception as e:
        emit("error", stage="llm_call", decision_num=decision_num, message=str(e))
        print(f"[AGENT] LLM call failed: {e}", flush=True)
        return {
            "content": "",
            "reasoning": "",
            "combined": "",
            "elapsed_s": 0.0,
            "finish_reason": None,
            "usage": {},
            "error": str(e),
        }


def _coerce_decision(result: dict, source: str) -> dict | None:
    if not result:
        return None
    try:
        heat = float(result["heating_sp"])
        cool = float(result["cooling_sp"])
    except (KeyError, TypeError, ValueError):
        return None
    reasoning = str(result.get("reasoning") or source)
    return {
        "heating_sp": heat,
        "cooling_sp": cool,
        "reasoning": reasoning,
        "source": source,
    }


def agent_decide(
    zone_data: dict,
    energy_data: dict,
    weather_data: dict,
    errors: dict,
    memory: list,
    last_good: dict | None = None,
    decision_num: int | None = None,
    sim_clock: dict | None = None,
) -> dict:
    """Get setpoint decision from LLM with fallback to last known good values."""
    if last_good is None:
        last_good = {"heating_sp": 21.0, "cooling_sp": 24.0}

    zone_str = json.dumps(zone_data, default=str)
    energy_str = json.dumps(energy_data, default=str)
    weather_str = json.dumps(weather_data, default=str)
    memory_str = _build_memory_summary(memory)
    clock_str = json.dumps(sim_clock or {}, default=str)

    user_prompt = (
        f"Simulation clock: {clock_str}\n"
        f"Zone: {zone_str}\n"
        f"Energy: {energy_str}\n"
        f"Weather: {weather_str}\n"
        f"{memory_str}\n"
        "Choose new heating/cooling setpoints now."
    )

    attempts: list[dict] = []
    attempts.append(_call_llm(user_prompt, decision_num=decision_num))

    for attempt, blob in enumerate(attempts, start=1):
        if not blob or blob.get("error"):
            if attempt == 1:
                emit("status", message="LLM call error — retrying once", decision_num=decision_num)
                attempts.append(_call_llm(user_prompt, decision_num=decision_num))
            continue

        # Prefer content (final answer), then combined, then reasoning alone
        for label, text in (
            ("content", blob.get("content") or ""),
            ("combined", blob.get("combined") or ""),
            ("reasoning", blob.get("reasoning") or ""),
        ):
            parsed = _parse_json(text)
            decision = _coerce_decision(parsed, source=f"llm:{label}")
            if decision:
                if blob.get("reasoning"):
                    decision["thinking"] = blob["reasoning"]
                decision["llm_elapsed_s"] = blob.get("elapsed_s")
                emit(
                    "llm_parse",
                    decision_num=decision_num,
                    ok=True,
                    source=decision["source"],
                    heating_sp=decision["heating_sp"],
                    cooling_sp=decision["cooling_sp"],
                    reasoning=decision["reasoning"],
                )
                if decision.get("reasoning"):
                    print(f"[AGENT] Reasoning: {decision['reasoning']}", flush=True)
                return decision

        emit(
            "llm_parse",
            decision_num=decision_num,
            ok=False,
            attempt=attempt,
            content_preview=(blob.get("content") or "")[:200],
            reasoning_preview=(blob.get("reasoning") or "")[:200],
        )
        if attempt == 1:
            emit("status", message="LLM parse failed — retrying once", decision_num=decision_num)
            print("[AGENT] JSON parse failed, retrying...", flush=True)
            attempts.append(_call_llm(user_prompt, decision_num=decision_num))

    print(f"[AGENT] Using fallback: {last_good}", flush=True)
    emit(
        "llm_parse",
        decision_num=decision_num,
        ok=False,
        fallback=True,
        last_good=last_good,
    )
    return {
        "heating_sp": last_good["heating_sp"],
        "cooling_sp": last_good["cooling_sp"],
        "reasoning": "LLM fallback",
        "source": "fallback",
        "thinking": "",
    }
