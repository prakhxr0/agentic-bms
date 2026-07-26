"""Quick LLM response structure probe."""
import json
import urllib.request

SYSTEM = (
    "You are a Building Energy Supervisor AI controlling an EnergyPlus HVAC model.\n"
    "TASK: Choose heating_sp and cooling_sp to save energy while keeping PMV near 0.\n"
    "HARD RULES:\n"
    "- Heating: 18.0-24.0 C\n"
    "- Cooling: 22.0-28.0 C\n"
    "- Cooling >= Heating + 2.0 C\n"
    "THINKING: Keep internal reasoning under 6 short bullets.\n"
    'OUTPUT: After thinking, output EXACTLY one JSON object and stop. No markdown fences.\n'
    'Schema: {"heating_sp": <float>, "cooling_sp": <float>, "reasoning": "<one sentence>"}'
)

USER = (
    'Simulation clock: {"month": 7, "day": 1, "hour": 14}\n'
    'Zone: {"temperature_c": 24.5, "pmv": 0.3}\n'
    'Energy: {"hvac_w": 1200}\n'
    'Weather: {"current_temp": 28.0, "future_temps": [29.0, 30.0, 29.5]}\n'
    "No prior decisions.\n"
    "Choose new heating/cooling setpoints now."
)

payload = {
    "model": "gemma-4-E2B_q4_0-it.gguf",
    "messages": [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": USER},
    ],
    "temperature": 0.3,
    "max_tokens": 1024,
    "top_p": 0.9,
}

req = urllib.request.Request(
    "http://localhost:8080/v1/chat/completions",
    data=json.dumps(payload).encode(),
    headers={"Content-Type": "application/json"},
)

with urllib.request.urlopen(req, timeout=120) as resp:
    body = json.loads(resp.read().decode())

msg = body["choices"][0]["message"]
print("KEYS:", list(msg.keys()))
print("CONTENT:", repr(msg.get("content", "")[:800]))
print("REASONING_CONTENT:", repr((msg.get("reasoning_content") or "")[:400]))
print("FINISH:", body["choices"][0].get("finish_reason"))
print("USAGE:", body.get("usage"))
