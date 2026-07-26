#!/usr/bin/env python3
"""Run AI-controlled simulation (requires llama-server on localhost:8080)."""

from src.ecoloop.sim.runner import run

if __name__ == "__main__":
    print("Starting AI simulation - ensure llama-server is running on localhost:8080")
    metrics = run("ai")
    print(f"AI metrics: {metrics}")