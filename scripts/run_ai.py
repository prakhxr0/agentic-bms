#!/usr/bin/env python3
"""Run AI-controlled simulation (requires llama-server on localhost:8080)."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ecoloop.sim.runner import run

if __name__ == "__main__":
    print("Starting AI simulation - ensure llama-server is running on localhost:8080")
    metrics = run("ai")
    print(f"AI metrics: {metrics}")