![Honeywell](assets/Honeywell-Logo.png)

# Eco - Loop Building Agent

**LLM-Driven Autonomous HVAC Setpoint Optimization for EnergyPlus Co-Simulation**  
*Built for the Honeywell Campus Connect*
*Candidate ID: 20518043*

---
*Candidate ID: 20518043*
- [POC Demo Video](https://drive.google.com/file/d/1ieBUQ4MHPLnhh2ycpOaxJB7iP1LR6gKw/view?usp=sharing)
- [System Architecture](system_architecture.md)
- [Presentation](Presentation_Honeywell_Hackathon.pdf)
- [Dashboard](https://dashboard-honeywell.vercel.app/)

---

## Problem Statement

HVAC systems account for over 40% of commercial building energy consumption. Traditional fixed setpoints (e.g., constant 24°C cooling / 21°C heating) fail to adapt to outdoor weather forecasts, real-time occupant comfort metrics, and dynamic thermal inertia, leading to significant overcooling and wasted energy.

**EcoLoop** is an autonomous building intelligence system that integrates a local Large Language Model (Gemma-4-E2B) directly with **EnergyPlus 26.1.0** co-simulation. At hourly intervals, EcoLoop observes current zone thermal comfort (Fanger PMV), electricity meter readings, and a 6-hour EPW weather lookahead forecast to make optimal setpoint decisions while strictly enforcing **ASHRAE 55 thermal comfort safety guardrails**.

---

## Benchmark Results (July 1–7 Chicago Summer Run)

| Metric | Native Baseline (Fixed 24°C/21°C) | EcoLoop AI Agent (Gemma-4-E2B) | Performance Delta | Impact |
|---|:---:|:---:|:---:|:---:|
| **Cooling Energy** | `173.70 kWh` | **`133.16 kWh`** | **-40.54 kWh** | **23.34% Energy Saved** |
| **Indoor Comfort (Avg PMV)** | `-0.66` | **`-0.55`** | **+0.11** | **16.11% Comfort Improvement** |
| **Avg Zone Temperature** | `22.96 °C` | `23.35 °C` | **+0.39 °C** | Comfortably floating near ~24.5°C neutral |
| **Total Timesteps / Decisions** | 672 / 0 | 672 / **168** | Gated Hourly | 7-day run in **< 4 minutes** |

> **Key Finding**: Raising setpoints dynamically during warm hours eliminated unnecessary HVAC overcooling (shifting average zone temp from 22.96°C to 23.35°C), saving **23.34% cooling energy** while bringing occupant PMV thermal comfort closer to 0 (comfort neutral).

---

## Modular & Configurable Architecture

EcoLoop features a centralized, environment-driven configuration system. **No python code needs to be edited** to change LLM models, API ports, setpoint bounds, or installation paths.

### Configuration (`.env.example` / `src/ecoloop/config.py`)

Copy `.env.example` to `.env` or pass standard environment variables:

```env
# EnergyPlus installation directory
EPLUS_INSTALL=C:\EnergyPlusV26-1-0

# LLM Endpoint (OpenAI API compliant: llama-server, vLLM, Ollama, etc.)
LLM_BASE_URL=http://localhost:8080/v1
LLM_MODEL=gemma-4-E2B_q4_0-it.gguf
LLM_API_KEY=dummy

# Comfort Guardrails (ASHRAE 55 Bounds °C)
HEAT_SETPOINT_MIN=18.0
HEAT_SETPOINT_MAX=24.0
COOL_SETPOINT_MIN=22.0
COOL_SETPOINT_MAX=28.0
DEADBAND_MIN=2.0
```

---

## Repository Structure

```
eco-loop-building-agent/
├── .env.example               # Environment variable configuration template
├── models/                    # EnergyPlus IDF and weather files
│   ├── 5ZoneAirCooled_summer.idf          # July 1-7 Chicago IDF with PythonPlugin
│   ├── 5ZoneAirCooled_summer_noplugin.idf # Baseline IDF (native schedules)
│   └── *.epw                              # EPW weather file
├── src/ecoloop/               # Canonical Python Package
│   ├── config.py              # Environment configuration & path resolver
│   ├── plugin.py              # EnergyPlusPlugin subclass (handles EMS API & hourly gating)
│   ├── sim/
│   │   ├── runner.py          # Simulation runner with subprocess environment isolation
│   │   └── environment.py     # Sizing guard (bypasses design-day environments 1 & 2)
│   ├── control/
│   │   ├── agent.py           # OpenAI-compliant LLM client (with retry & fallback)
│   │   ├── guardrail.py       # ASHRAE 55 clamping & deadband logic
│   │   └── static_controller.py # Hardcoded 26/18°C test controller
│   ├── io/
│   │   ├── state_store.py     # Decision logger (state_history.jsonl)
│   │   ├── metrics.py         # SQLite eplusout.sql metrics extractor
│   │   └── weather.py         # EPW weather lookahead loader
│   └── tools.py               # Agent tools (zone state, energy meters, forecast)
├── scripts/                   # CLI Execution Entrypoints
│   ├── run_baseline.py        # Run native schedule baseline
│   ├── run_wiring_test.py     # Run static test (26°C/18°C setpoints)
│   ├── run_ai.py              # Run LLM-driven autonomous agent
│   └── compare_results.py     # Compare two metrics JSON outputs
├── plugin.py                  # Root entrypoint wrapper loaded by EnergyPlus
├── pyproject.toml             # Package setup
└── README.md                  # Project documentation
```

---

## Setup Guide

### 1. Prerequisites
* **Python 3.11+**
* **EnergyPlus 26.1.0** installed at `C:\EnergyPlusV26-1-0` (or set `EPLUS_INSTALL` env var)
* **`pyenergyplus`** (bundled automatically with EnergyPlus installation)
* For AI Mode: Any OpenAI-compatible local server running (e.g. `llama-server` on port `8080`)

### 2. Installation
```bash
# Clone the repository
git clone https://github.com/your-username/eco-loop-building-agent.git
cd eco-loop-building-agent

# Install editable package
pip install -e .
```

### 3. Run Baseline Simulation
```bash
python scripts/run_baseline.py
```
* **Output**: `outputs/baseline/baseline_metrics.json`
* **Metrics**: ~2,741.7 total site kWh, 173.70 cooling kWh, PMV -0.66.

### 4. Run Wiring Verification Test
```bash
python scripts/run_wiring_test.py
```
* **Output**: `outputs/wiring_test/static_test_metrics.json`
* **Verification**: Applies constant 26.0°C cooling / 18.0°C heating via actuators to verify direct IDF schedule overriding.

### 5. Run Autonomous AI Agent

**Terminal 1**: Start your local LLM server (e.g., Gemma-4-E2B via llama.cpp):
```bash
llama-server -m gemma-4-E2B_q4_0-it.gguf --port 8080
```

**Terminal 2**: Execute the 7-day AI simulation:
```bash
python scripts/run_ai.py
```
* **Output**: `outputs/ai_run/ai_metrics.json` and decision logs in `state_history.jsonl`.
* **Runtime**: ~3.5 to 4 minutes (168 decisions gated hourly over 672 timesteps).

### 6. Generate Performance Comparison Table
```bash
python scripts/compare_results.py outputs/baseline/baseline_metrics.json outputs/ai_run/ai_metrics.json
```

---

## Safety & Reliability Mechanisms

1. **ASHRAE 55 Guardrail Clamping**: Proposed setpoints are clamped to $18^\circ\text{C} \le \text{Heating} \le 24^\circ\text{C}$ and $22^\circ\text{C} \le \text{Cooling} \le 28^\circ\text{C}$, maintaining a strict minimum deadband of $\ge 2.0^\circ\text{C}$.
2. **Design-Day Sizing Guard**: `is_sizing_period()` inspects `current_environment_num` and bypasses actuation during design-day sizing periods (environments 1 & 2), preventing severe sizing balance errors.
3. **Resilient LLM Fallback**: If the LLM API call times out (10s) or fails JSON parsing after 1 retry, the controller gracefully falls back to `last_good` setpoints without interrupting simulation execution.
