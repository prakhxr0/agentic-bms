"""Central configuration for eco-loop-building-agent with environment variable overrides."""

import os
from pathlib import Path

# Project root
ROOT = Path(__file__).resolve().parents[2]  # eco-loop-building-agent/

# EnergyPlus install path (can be overridden via environment variable)
EPLUS_INSTALL = Path(os.getenv("EPLUS_INSTALL", r"C:\EnergyPlusV26-1-0"))

# Model & weather paths
IDF_PATH = ROOT / "models" / "5ZoneAirCooled_summer.idf"
EPW_PATH = Path(os.getenv("EPW_PATH", str(EPLUS_INSTALL / "WeatherData" / "USA_IL_Chicago-OHare.Intl.AP.725300_TMY3.epw")))

# Output directories
OUTPUT_DIR_BASELINE = ROOT / "outputs" / "baseline"
OUTPUT_DIR_WIRING = ROOT / "outputs" / "wiring_test"
OUTPUT_DIR_AI = ROOT / "outputs" / "ai_run"

# Run period (July 1-7)
RUN_PERIOD_START_MONTH = 7
RUN_PERIOD_START_DAY = 1
RUN_PERIOD_END_MONTH = 7
RUN_PERIOD_END_DAY = 7

# Guardrail bounds (ASHRAE 55 comfort zone)
HEAT_SETPOINT_MIN = float(os.getenv("HEAT_SETPOINT_MIN", 18.0))
HEAT_SETPOINT_MAX = float(os.getenv("HEAT_SETPOINT_MAX", 24.0))
COOL_SETPOINT_MIN = float(os.getenv("COOL_SETPOINT_MIN", 22.0))
COOL_SETPOINT_MAX = float(os.getenv("COOL_SETPOINT_MAX", 28.0))
DEADBAND_MIN = float(os.getenv("DEADBAND_MIN", 2.0))  # minimum cooling - heating difference

# Actuator schedule names (must match IDF)
COOL_SCHEDULE_NAME = "Clg-SetP-Sch"
HEAT_SCHEDULE_NAME = "Htg-SetP-Sch"

# Zone name for sensors
ZONE_NAME = "SPACE1-1"

# LLM endpoint configuration (OpenAI API compatible)
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://localhost:8080/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "gemma-4-E2B_q4_0-it.gguf")
LLM_API_KEY = os.getenv("LLM_API_KEY", "dummy")