"""State persistence for agent decisions."""

import json
import time
from datetime import datetime
from pathlib import Path

from src.ecoloop.config import ROOT

STATE_FILE = ROOT / "state_history.jsonl"


def write_state(state_dict: dict):
    """Append state record to JSONL file."""
    state_dict['timestamp'] = datetime.now().isoformat()
    state_dict['wall_clock'] = time.time()
    with open(STATE_FILE, 'a') as f:
        f.write(json.dumps(state_dict) + "\n")


def read_state() -> dict | None:
    """Read most recent state record."""
    if not STATE_FILE.exists():
        return None
    with open(STATE_FILE, 'r') as f:
        lines = [line.strip() for line in f if line.strip()]
    if not lines:
        return None
    return json.loads(lines[-1])


def clear_state():
    """Clear state history (use between runs)."""
    if STATE_FILE.exists():
        STATE_FILE.unlink()