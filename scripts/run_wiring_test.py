#!/usr/bin/env python3
"""Run wiring test (plugin active, hardcoded 26/18 setpoints)."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ecoloop.sim.runner import run

if __name__ == "__main__":
    metrics = run("static_test")
    print(f"Wiring test metrics: {metrics}")