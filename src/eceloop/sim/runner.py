"""Single entrypoint for running simulations in different modes."""

import subprocess
import sys
from pathlib import Path

from src.ecoloop.config import (
    IDF_PATH, EPW_PATH, EPLUS_INSTALL,
    OUTPUT_DIR_BASELINE, OUTPUT_DIR_WIRING, OUTPUT_DIR_AI,
)
from src.ecoloop.io.metrics import extract_metrics


def run_energyplus(idf_path: Path, epw_path: Path, output_dir: Path) -> int:
    """Run EnergyPlus and return exit code."""
    output_dir.mkdir(parents=True, exist_ok=True)
    eplus_exe = EPLUS_INSTALL / "energyplus.exe"

    cmd = [
        str(eplus_exe),
        "-d", str(output_dir),
        "-w", str(epw_path),
        str(idf_path),
    ]

    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

    if result.stdout:
        print(result.stdout[-2000:])  # last 2KB
    if result.stderr:
        print(result.stderr[-2000:], file=sys.stderr)

    return result.returncode


def run(mode: str) -> dict:
    """
    Run simulation in specified mode.
    mode: "baseline" | "wiring_test" | "ai"
    Returns metrics dict.
    """
    if mode == "baseline":
        output_dir = OUTPUT_DIR_BASELINE
    elif mode == "wiring_test":
        output_dir = OUTPUT_DIR_WIRING
    elif mode == "ai":
        output_dir = OUTPUT_DIR_AI
    else:
        raise ValueError(f"Unknown mode: {mode}")

    print(f"\n=== Running {mode} simulation ===")
    exit_code = run_energyplus(IDF_PATH, EPW_PATH, output_dir)

    if exit_code != 0:
        raise RuntimeError(f"EnergyPlus failed with exit code {exit_code}")

    sql_path = output_dir / "eplusout.sql"
    if not sql_path.exists():
        raise FileNotFoundError(f"SQL output not found: {sql_path}")

    metrics = extract_metrics(sql_path)
    print(f"\n{mode} metrics: {metrics}")
    return metrics


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python runner.py <baseline|wiring_test|ai>")
        sys.exit(1)

    metrics = run(sys.argv[1])
    import json
    print(json.dumps(metrics, indent=2))