"""Single entrypoint for all simulation modes."""

import os
import subprocess
import shutil
from pathlib import Path

from ecoloop.config import (
    IDF_PATH, EPW_PATH, EPLUS_INSTALL,
    OUTPUT_DIR_BASELINE, OUTPUT_DIR_WIRING, OUTPUT_DIR_AI,
)


EPLUS_EXE = EPLUS_INSTALL / "energyplus.exe"


def run_simulation(idf_path: Path, epw_path: Path, output_dir: Path, plugin: bool = True, control_mode: str = "static_test") -> int:
    """
    Run EnergyPlus simulation.
    Returns exit code (0 = success).
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Clean previous run
    for f in output_dir.glob("*"):
        try:
            f.unlink() if f.is_file() else shutil.rmtree(f)
        except Exception:
            pass

    cmd = [
        str(EPLUS_EXE),
        "-d", str(output_dir),
        "-w", str(epw_path),
        str(idf_path),
    ]

    env = os.environ.copy()
    env["ECOLOOP_CONTROL_MODE"] = control_mode

    print(f"[RUNNER] {' '.join(cmd)} (control_mode={control_mode})")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600, env=env)

    # Write stdout/stderr for debugging
    (output_dir / "stdout.log").write_text(result.stdout)
    (output_dir / "stderr.log").write_text(result.stderr)

    if result.returncode != 0:
        print(f"[RUNNER] FAILED (exit {result.returncode})")
        print(result.stderr[-2000:])
    else:
        print(f"[RUNNER] SUCCESS -> {output_dir}")

    return result.returncode


def run(control_mode: str = "static_test") -> dict:
    """
    Main entrypoint.

    control_mode:
      - "baseline": native schedules, no plugin (uses _noplugin IDF)
      - "static_test": plugin active, hardcoded 26/18 (wiring test)
      - "ai": plugin active, LLM agent (requires llama-server on :8080)

    Returns metrics dict.
    """
    from ecoloop.io.metrics import extract_metrics

    if control_mode == "baseline":
        idf = IDF_PATH.with_name("5ZoneAirCooled_summer_noplugin.idf")
        out = OUTPUT_DIR_BASELINE
        plugin = False
    elif control_mode == "static_test":
        idf = IDF_PATH
        out = OUTPUT_DIR_WIRING
        plugin = True
    elif control_mode == "ai":
        idf = IDF_PATH
        out = OUTPUT_DIR_AI
        plugin = True
        from ecoloop.io.state_store import clear_state
        clear_state()
    else:
        raise ValueError(f"Unknown control_mode: {control_mode}")

    rc = run_simulation(idf, EPW_PATH, out, plugin=plugin, control_mode=control_mode)
    if rc != 0:
        return {"error": f"Simulation failed with exit code {rc}", "exit_code": rc}

    sql_path = out / "eplusout.sql"
    if not sql_path.exists():
        return {"error": "No eplusout.sql produced"}

    metrics = extract_metrics(sql_path)
    metrics["control_mode"] = control_mode
    metrics["output_dir"] = str(out)

    # Save metrics JSON for comparison
    import json
    (out / f"{control_mode}_metrics.json").write_text(json.dumps(metrics, indent=2))

    return metrics


if __name__ == "__main__":
    import sys
    mode = sys.argv[1] if len(sys.argv) > 1 else "static_test"
    result = run(mode)
    print(result)