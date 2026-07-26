"""Single entrypoint for all simulation modes."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from ecoloop.config import (
    EPW_PATH,
    EPLUS_INSTALL,
    IDF_PATH,
    IDF_PATH_1D,
    OUTPUT_DIR_AI,
    OUTPUT_DIR_BASELINE,
    OUTPUT_DIR_DEMO,
    OUTPUT_DIR_WIRING,
    ROOT,
)

EPLUS_EXE = EPLUS_INSTALL / "energyplus.exe"


def run_simulation(
    idf_path: Path,
    epw_path: Path,
    output_dir: Path,
    plugin: bool = True,
    control_mode: str = "static_test",
    stream: bool = False,
) -> int:
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
        "-d",
        str(output_dir),
        "-w",
        str(epw_path),
        str(idf_path),
    ]

    env = os.environ.copy()
    env["ECOLOOP_CONTROL_MODE"] = control_mode
    # Ensure plugin package is importable from EnergyPlus's Python
    src = str(ROOT / "src")
    env["PYTHONPATH"] = src + os.pathsep + env.get("PYTHONPATH", "")

    print(f"[RUNNER] {' '.join(cmd)} (control_mode={control_mode})", flush=True)

    if stream:
        # Live stdout/stderr for the demo TUI (unbuffered-ish)
        env["PYTHONUNBUFFERED"] = "1"
        result = subprocess.run(
            cmd,
            cwd=str(ROOT),
            env=env,
            timeout=7200,
        )
        return result.returncode

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=7200,
        env=env,
        cwd=str(ROOT),
    )

    # Write stdout/stderr for debugging
    (output_dir / "stdout.log").write_text(result.stdout or "", encoding="utf-8", errors="replace")
    (output_dir / "stderr.log").write_text(result.stderr or "", encoding="utf-8", errors="replace")

    if result.returncode != 0:
        print(f"[RUNNER] FAILED (exit {result.returncode})")
        print((result.stderr or "")[-2000:])
    else:
        print(f"[RUNNER] SUCCESS -> {output_dir}")

    return result.returncode


def run(control_mode: str = "static_test", stream: bool = False) -> dict:
    """
    Main entrypoint.

    control_mode:
      - "baseline": native schedules, no plugin (uses _noplugin IDF)
      - "static_test": plugin active, hardcoded 26/18 (wiring test)
      - "ai": plugin active, LLM agent, 7-day summer IDF
      - "demo": plugin active, LLM agent, 1-day IDF (PoC video)

    Returns metrics dict.
    """
    from ecoloop.io.metrics import extract_metrics

    if control_mode == "baseline":
        idf = IDF_PATH.with_name("5ZoneAirCooled_summer_noplugin.idf")
        out = OUTPUT_DIR_BASELINE
        plugin = False
        mode = "baseline"
    elif control_mode == "static_test":
        idf = IDF_PATH
        out = OUTPUT_DIR_WIRING
        plugin = True
        mode = "static_test"
    elif control_mode == "ai":
        idf = IDF_PATH
        out = OUTPUT_DIR_AI
        plugin = True
        mode = "ai"
        from ecoloop.io.event_bus import clear_events
        from ecoloop.io.state_store import clear_state

        clear_state()
        clear_events()
    elif control_mode == "demo":
        idf = IDF_PATH_1D if IDF_PATH_1D.exists() else IDF_PATH
        out = OUTPUT_DIR_DEMO
        plugin = True
        mode = "ai"  # plugin still uses ai control path
        from ecoloop.io.event_bus import clear_events
        from ecoloop.io.state_store import clear_state

        clear_state()
        clear_events()
    else:
        raise ValueError(f"Unknown control_mode: {control_mode}")

    rc = run_simulation(
        idf, EPW_PATH, out, plugin=plugin, control_mode=mode, stream=stream
    )
    if rc != 0:
        return {"error": f"Simulation failed with exit code {rc}", "exit_code": rc}

    sql_path = out / "eplusout.sql"
    if not sql_path.exists():
        return {"error": "No eplusout.sql produced", "output_dir": str(out)}

    metrics = extract_metrics(sql_path)
    metrics["control_mode"] = control_mode
    metrics["output_dir"] = str(out)

    import json

    (out / f"{control_mode}_metrics.json").write_text(
        json.dumps(metrics, indent=2), encoding="utf-8"
    )

    return metrics


if __name__ == "__main__":
    import sys

    mode = sys.argv[1] if len(sys.argv) > 1 else "static_test"
    result = run(mode)
    print(result)
