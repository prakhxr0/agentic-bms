"""Quick probe of llama-server response shape for Gemma reasoning models."""
import json
import re
import urllib.request


def call(max_tokens: int, system: str, user: str) -> dict:
    payload = {
        "model": "gemma-4-E2B_q4_0-it.gguf",
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.2,
        "max_tokens": max_tokens,
    }
    req = urllib.request.Request(
        "http://localhost:8080/v1/chat/completions",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        return json.loads(resp.read().decode())


def extract_json(text: str):
    if not text:
        return None
    m = re.search(r"\{[^{}]*heating_sp[^{}]*\}", text, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group())
    except json.JSONDecodeError:
        return None


system = (
    "You are a Building Energy Supervisor. Keep internal reasoning under 5 short bullets. "
    "Then output exactly one JSON object and stop.\n"
    'Schema: {"heating_sp": <float>, "cooling_sp": <float>, "reasoning": "<one sentence>"}\n'
    "Bounds: heat 18-24C, cool 22-28C, cool >= heat+2."
)
user = (
    "Zone temp=24.5C PMV=0.3 outdoor=28C forecast=[29,30,29] hvac_w=1200. "
    "Choose setpoints now."
)

body = call(1024, system, user)
msg = body["choices"][0]["message"]
content = msg.get("content") or ""
reasoning = msg.get("reasoning_content") or ""
combined = (content + "\n" + reasoning).strip()
print("FINISH", body["choices"][0].get("finish_reason"))
print("CONTENT_LEN", len(content), "REASONING_LEN", len(reasoning))
print("CONTENT_TAIL:", repr(content[-300:]))
print("REASONING_TAIL:", repr(reasoning[-400:]))
print("PARSED", extract_json(combined) or extract_json(reasoning) or extract_json(content))
print("USAGE", body.get("usage"))
