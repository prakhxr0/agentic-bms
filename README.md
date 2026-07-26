# eco-loop-building-agent

LLM-driven HVAC setpoint optimization for EnergyPlus co-simulation.

## Project Structure

```
eco-loop-building-agent/
├── models/                    # EnergyPlus input files (unchanged)
│   ├── 5ZoneAirCooled_summer.idf      # July 1-7 Chicago run with PythonPlugin
│   ├── 5ZoneAirCooled_summer_noplugin.idf  # Same IDF, no plugin (baseline)
│   └── *.epw                  # Weather files
├── src/ecoloop/               # Main package
│   ├── __init__.py
│   ├── config.py              # Single source of truth: paths, bounds, names
│   ├── plugin.py              # EnergyPlusPlugin subclass (thin, delegates)
│   ├── sim/
│   │   ├── __init__.py
│   │   ├── runner.py          # run(control_mode) -> single entry point
│   │   └── environment.py     # current_environment_num guards
│   ├── control/
│   │   ├── __init__.py
│   │   ├── guardrail.py       # ASHRAE 55 clamping (18-24 heat, 22-28 cool, 2C deadband)
│   │   ├── agent.py           # LLM client (Gemma-4-E2B via localhost:8080)
│   │   └── static_controller.py  # Hardcoded 26/18 test controller
│   ├── io/
│   │   ├── __init__.py
│   │   ├── state_store.py     # JSONL history (state_history.jsonl)
│   │   ├── metrics.py         # extract_metrics(sql_path) -> dict
│   │   └── weather.py         # EPW lookahead helper
│   └── tools.py               # Agent tool functions (zone, energy, weather)
├── scripts/                   # Thin CLI entrypoints only
│   ├── run_baseline.py        # Native schedules (no plugin)
│   ├── run_wiring_test.py     # Hardcoded 26/18 via plugin
│   ├── run_ai.py              # LLM agent (requires localhost:8080)
│   └── compare_results.py     # Compare two metrics.json
├── outputs/                   # Simulation outputs (gitignored)
├── tests/
│   └── test_environment_guard.py  # Sizing guard regression test
├── pyproject.toml
├── REFACTOR_LOG.md            # This refactor's mapping
└── README.md                  # This file
```

## Quick Start

### 1. Baseline (native schedules, no plugin)
```bash
python scripts/run_baseline.py
```
Runs `5ZoneAirCooled_summer_noplugin.idf` (July 1-7, Chicago).  
Expected: ~2,741.7 kWh, PMV ≈ -0.63

### 2. Wiring Test (plugin active, hardcoded 26°C/18°C)
```bash
python scripts/run_wiring_test.py
```
Runs `5ZoneAirCooled_summer.idf` with PythonPlugin.  
Verifies Schedule Value output shows 26.0/18.0 (not 24.0/21.0) and sizing completes.

### 3. AI Agent (requires LLM server)
```bash
# Terminal 1: Start local LLM (Gemma-4-E2B-GGUF via llama.cpp server)
llama-server -m gemma-4-E2B_q4_0-it.gguf --port 8080

# Terminal 2: Run AI-controlled simulation
python scripts/run_ai.py
```
Uses `agent.py` to call `http://localhost:8080/v1` every hour.

### 4. Compare Results
```bash
python scripts/compare_results.py outputs/baseline/baseline_metrics.json outputs/wiring_test/wiring_test_results.json
```

## Key Configuration (`src/ecoloop/config.py`)

| Parameter | Value | Description |
|-----------|-------|-------------|
| `HEAT_SETPOINT_MIN/MAX` | 18.0 / 24.0 °C | Heating setpoint clamp range |
| `COOL_SETPOINT_MIN/MAX` | 22.0 / 28.0 °C | Cooling setpoint clamp range |
| `DEADBAND_MIN` | 2.0 °C | Minimum cooling - heating |
| `RUN_PERIOD` | Jul 1 - Jul 7 | Simulation period |
| `COOL_SCHEDULE_NAME` | `Clg-SetP-Sch` | Must match IDF |
| `HEAT_SCHEDULE_NAME` | `Htg-SetP-Sch` | Must match IDF |

## Verified Behavior (Refactor Checkpoint)

| Test | Status | Details |
|------|--------|---------|
| Baseline run | ✅ PASS | 2,741.7 kWh, PMV -0.63 |
| Wiring test | ✅ PASS | Schedule Value = 26.0/18.0, no sizing crash |
| Sizing guard | ✅ PASS | `current_environment_num < 3` skips design days |

## Requirements

- EnergyPlus 26.1.0 installed at `C:\EnergyPlusV26-1-0` (Windows) or standard Linux/macOS path
- Python 3.11+
- `pyenergyplus` (bundled with EnergyPlus install)
- For AI mode: llama.cpp server with Gemma-4-E2B-GGUF at `localhost:8080`

## Notes

- The `scripts/run_ai.py` entrypoint exists but is **not verified** in this refactor — it requires the LLM server running.
- All business logic lives in `src/ecoloop/`; scripts are <50 lines each.
- `state_history.jsonl` accumulates per-timestep state for debugging.