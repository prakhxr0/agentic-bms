import json
import os
from datetime import datetime

STATE_FILE = "state_history.jsonl"

def write_state(state_dict: dict):
    import time
    state_dict['timestamp'] = datetime.now().isoformat()
    state_dict['wall_clock'] = time.time()
    print(f"[STATE] write at wall-clock {time.time():.3f}", flush=True)
    with open(STATE_FILE, 'a') as f:
        f.write(json.dumps(state_dict) + "\n")

def read_state():
    if not os.path.exists(STATE_FILE):
        return None
    with open(STATE_FILE, 'r') as f:
        lines = [line.strip() for line in f if line.strip()]
    if not lines:
        return None
    return json.loads(lines[-1])