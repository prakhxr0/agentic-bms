"""LLM agent client for setpoint decisions (NOT invoked in this refactor)."""

import json
import time
import re
import urllib.request
import urllib.error

from ecoloop.config import LLM_BASE_URL, LLM_MODEL, LLM_API_KEY

SYSTEM_PROMPT = """You are a Building Energy Supervisor AI. Adjust HVAC setpoints to minimize energy while keeping PMV between -0.5 and +0.5 (ASHRAE 55).

RULES:
- Heating: 18.0-24.0C  Cooling: 22.0-28.0C
- Cooling >= Heating + 2.0C (deadband)
- If PMV < -0.5 (too cold): raise heating OR lower cooling
- If PMV > +0.5 (too hot): lower cooling OR raise heating
- Use weather lookahead to anticipate outdoor changes
- Widen deadband during mild weather to save energy

Output ONLY valid JSON. No explanations, no markdown, no thinking tags.
Schema: {"heating_sp": 21.0, "cooling_sp": 24.0, "reasoning": "brief explanation"}"""


def _parse_json(text: str) -> dict | None:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        text = text.strip()
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass
    brace_match = re.search(r"\{[^{}]*\}", text, re.DOTALL)
    if brace_match:
        try:
            obj = json.loads(brace_match.group())
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass
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


def _call_llm(user_prompt: str) -> str | None:
    payload = json.dumps({
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.6,
        "max_tokens": 2048,
        "top_p": 0.95,
    }).encode()

    req = urllib.request.Request(
        LLM_BASE_URL + "/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {LLM_API_KEY}",
            "Content-Type": "application/json",
        },
    )

    try:
        start = time.time()
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read().decode())
        elapsed = time.time() - start
        raw = body["choices"][0]["message"]["content"]
        print(f"[AGENT] LLM response ({elapsed:.1f}s, {len(raw)} chars)", flush=True)
        return raw
    except Exception as e:
        print(f"[AGENT] LLM call failed: {e}", flush=True)
        return None


def agent_decide(zone_data: dict, energy_data: dict, weather_data: dict,
                 errors: dict, memory: list, last_good: dict | None = None) -> dict:
    """Get setpoint decision from LLM with fallback to last known good values."""
    if last_good is None:
        last_good = {"heating_sp": 21.0, "cooling_sp": 24.0}

    zone_str = json.dumps(zone_data, default=str)
    energy_str = json.dumps(energy_data, default=str)
    weather_str = json.dumps(weather_data, default=str)
    memory_str = _build_memory_summary(memory)

    user_prompt = f"""Current Building State:
Zone: {zone_str}
Energy: {energy_str}
Weather: {weather_str}
{memory_str}

Output new heating/cooling setpoints as JSON."""

    raw = _call_llm(user_prompt)

    if raw:
        print(f"[AGENT] Raw: {raw[:300]}", flush=True)
        result = _parse_json(raw)
        if result and "heating_sp" in result and "cooling_sp" in result:
            result["heating_sp"] = float(result["heating_sp"])
            result["cooling_sp"] = float(result["cooling_sp"])
            reasoning = result.get("reasoning", "")
            if reasoning:
                print(f"[AGENT] Reasoning: {reasoning}", flush=True)
            return result
        else:
            print(f"[AGENT] JSON parse failed, retrying...", flush=True)
            raw2 = _call_llm(user_prompt)
            if raw2:
                result = _parse_json(raw2)
                if result and "heating_sp" in result and "cooling_sp" in result:
                    result["heating_sp"] = float(result["heating_sp"])
                    result["cooling_sp"] = float(result["cooling_sp"])
                    return result

    print(f"[AGENT] Using fallback: {last_good}", flush=True)
    return {"heating_sp": last_good["heating_sp"],
            "cooling_sp": last_good["cooling_sp"],
            "reasoning": "LLM fallback"}