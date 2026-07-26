"""Central configuration for eco-loop-building-agent."""

from pathlib import Path

# Project root
ROOT = Path(__file__).resolve().parents[2]  # eco-loop-building-agent/

# Model & weather
IDF_PATH = ROOT / "models" / "5ZoneAirCooled_summer.idf"
EPW_PATH = Path(r"C:\EnergyPlusV26-1-0\WeatherData\USA_IL_Chicago-OHare.Intl.AP.725300_TMY3.epw")

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
HEAT_SETPOINT_MIN = 18.0
HEAT_SETPOINT_MAX = 24.0
COOL_SETPOINT_MIN = 22.0
COOL_SETPOINT_MAX = 28.0
DEADBAND_MIN = 2.0  # minimum cooling - heating difference

# Actuator schedule names (must match IDF)
COOL_SCHEDULE_NAME = "Clg-SetP-Sch"
HEAT_SCHEDULE_NAME = "Htg-SetP-Sch"

# Zone name for sensors
ZONE_NAME = "SPACE1-1"

# EnergyPlus install path
EPLUS_INSTALL = Path(r"C:\EnergyPlusV26-1-0")

# LLM endpoint (not used in this refactor)
LLM_BASE_URL = "http://localhost:8080/v1"
LLM_MODEL = "gemma-4-E2B_q4_0-it.gguf"
LLM_API_KEY = "dummy"