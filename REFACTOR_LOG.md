# REFACTOR_LOG.md

Mapping of legacy files → new modular structure (or deletion).

---

## New Package Structure (`src/ecoloop/`)

| New Module | Source(s) | Notes |
|------------|-----------|-------|
| `config.py` | *new* | Centralized all paths, bounds, schedule names, run period |
| `plugin.py` | `plugin.py` (root) | Trimmed to thin delegator; hardcoded 26/18 + env guard |
| `sim/runner.py` | `run_ai_*.py`, `run_baseline.py`, `run_summer_*.py` | Single `run(control_mode)` entrypoint |
| `sim/environment.py` | *new* | `current_environment_num` sizing guard helper |
| `control/guardrail.py` | `guardrail.py` (root) | Moved as-is, imports from config |
| `control/agent.py` | `agent.py` (root) | Moved as-is, LLM client logic untouched |
| `control/static_controller.py` | `plugin_wiring_test.py` | Formalized hardcoded test controller |
| `io/state_store.py` | `state_store.py` (root) | Moved as-is |
| `io/metrics.py` | `check_sql.py`, `query_wiring*.py`, `compare.py`, `extract_baseline_metrics.py`, `verify_outputs.py` | Consolidated into `extract_metrics()` + `extract_schedule_values()` |
| `io/weather.py` | `tools.py` (partial) | EPW loader extracted, `__file__` fragility fixed |
| `tools.py` | `tools.py` (root) | Moved as-is, now imports from `io.weather` |

---

## Scripts (`scripts/`)

| New Script | Replaces | Notes |
|------------|----------|-------|
| `run_baseline.py` | `run_baseline.py`, `run_summer_baseline.py`, `step1_baseline.py`, `_run_baseline.py` | Runs native IDF (no plugin) |
| `run_wiring_test.py` | `run_ai_1day.py`, `run_ai_1day_v3.py`, `plugin_wiring_test.py` | Hardcoded 26/18 via plugin |
| `run_ai.py` | `run_ai_7day.py`, `run_ai_7day_v2.py`, `run_ai_v2.py`, `step2_ai_1day.py` | LLM mode (not verified in refactor) |
| `compare_results.py` | `compare.py`, `check_decisions.py`, `check_setpoints.py`, `check_state.py` | Loads two metrics.json, prints table |

---

## Deleted Files (logic merged above)

### Scratch / duplicate runners
- `_check_baseline.py` → merged into `metrics.py`
- `_run_ai_background.py` → merged into `runner.py`
- `_run_ai_direct.py` → merged into `runner.py`
- `_run_baseline.py` → merged into `runner.py`

### Query / check scripts (merged into `metrics.py`)
- `query_wiring.py`
- `query_wiring2.py`
- `query_wiring3.py`
- `query_wiring4.py`
- `check_sql.py`
- `check_decisions.py`
- `check_setpoints.py`
- `check_state.py`

### Comparison / verify scripts (merged into `compare_results.py` / `metrics.py`)
- `compare.py`
- `extract_baseline_metrics.py`
- `verify_outputs.py`

### Runner variants (all merged into `runner.py`)
- `run_ai_1day.py`
- `run_ai_1day_v3.py`
- `run_ai_7day.py`
- `run_ai_7day_v2.py`
- `run_ai_v2.py`
- `run_summer_baseline.py`
- `run_smoke_test.py`
- `step1_baseline.py`
- `step2_ai_1day.py`

### MCP / experimental (not used in current pipeline)
- `test_mcp.py` → **removed, logic unused**
- `mcp_server.py` → **removed, logic unused**

---

## Stale Output/Log Files Deleted

| File | Reason |
|------|--------|
| `ai_1day_metrics.json` | superseded by canonical metrics |
| `ai_1day_v3_metrics.json` | superseded |
| `ai_1day_run.log` | log file |
| `ai_7day_err.log` | log file |
| `ai_7day_launch_err.log` | log file |
| `ai_7day_launch.log` | log file |
| `ai_7day_run.log` | log file |
| `ai_7day.pid` | pid file |
| `ai_run.log` | log file |
| `ai_run.pid` | pid file |
| `ai_stderr.log` | log file |
| `ai_stdout.log` | log file |
| `ai.pid` | pid file |
| `phase3_ems_metrics.json` | superseded |
| `phase6_ai_1d_metrics.json` | superseded |
| `phase6_ai_metrics.json` | superseded |
| `current_building_state.json` | temp state |
| `summer_baseline_1d_metrics.json` | superseded |

---

## Canonical Reference Files KEPT (not deleted)

| File | Purpose |
|------|---------|
| `baseline_metrics.json` | Original annual baseline reference |
| `summer_baseline_metrics.json` | July 1-7 baseline (2,741.7 kWh, PMV -0.63) |
| `phase6_ai_v2_metrics.json` | 7-day AI run reference (687 decisions, PMV -0.253) |
| `state_history.jsonl` | Accumulated decision log |

---

## Tests Added

| Test File | Purpose |
|-----------|---------|
| `tests/test_environment_guard.py` | Mock `current_environment_num` to verify sizing guard logic |

---

## Verification Performed

1. `python scripts/run_baseline.py` → 2,741.7 kWh, PMV -0.63 ✅
2. `python scripts/run_wiring_test.py` → Schedule Value 26.0/18.0, no sizing crash ✅
3. `python scripts/compare_results.py outputs/baseline/baseline_metrics.json outputs/wiring_test/wiring_test_results.json` → table printed ✅

---

## Pending (Next Step)

- Re-enable LLM path in `plugin.py` (swap `static_controller.apply_static_test_setpoints` → `agent_decide` + `guardrail.clamp_setpoints`)
- Run `scripts/run_ai.py` with `llama-server` on localhost:8080
- Full 7-day comparison against `phase6_ai_v2_metrics.json`