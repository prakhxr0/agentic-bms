"""Smoke-test agent_decide against the live LLM server."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ecoloop.control.agent import agent_decide, _parse_json
from ecoloop.io.event_bus import clear_events, EVENT_FILE

# unit: parse from reasoning-only blob
sample = '''Thinking Process:
1. PMV cold
{"heating_sp": 22.0, "cooling_sp": 25.0, "reasoning": "raise heat"}
'''
assert _parse_json(sample)["heating_sp"] == 22.0
print("parse_ok")

clear_events()
result = agent_decide(
    zone_data={"zone": "SPACE1-1", "temperature_c": 24.5, "pmv": 0.3},
    energy_data={"total_w": 1500, "building_w": 400, "hvac_w": 1100},
    weather_data={"current_temp": 28.0, "future_temps": [29, 30, 29, 28, 27, 26]},
    errors={"errors": []},
    memory=[],
    last_good={"heating_sp": 21.0, "cooling_sp": 24.0},
    decision_num=1,
    sim_clock={"year": 2009, "month": 7, "day": 1, "hour": 14, "minute": 0},
)
print("DECISION", json.dumps(result, indent=2))
print("EVENTS", EVENT_FILE)
if EVENT_FILE.exists():
    for line in EVENT_FILE.read_text(encoding="utf-8").splitlines():
        ev = json.loads(line)
        print(f"  {ev['kind']}: { {k:v for k,v in ev.items() if k not in ('ts','wall_clock','seq','user_prompt','text','thinking','content','reasoning') } }")
assert result.get("source") != "fallback", result
assert 18 <= result["heating_sp"] <= 24
assert 22 <= result["cooling_sp"] <= 28
print("SMOKE OK")
