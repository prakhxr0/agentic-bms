#!/usr/bin/env python3
"""Run baseline simulation (native schedules, no plugin)."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ecoloop.sim.runner import run

if __name__ == "__main__":
    metrics = run("baseline")
    print(f"Baseline metrics: {metrics}")