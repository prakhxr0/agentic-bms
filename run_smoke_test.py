import sys
import os

EPLUS_PATH = r"C:\EnergyPlusV26-1-0"
if EPLUS_PATH not in sys.path:
    sys.path.append(EPLUS_PATH)

from pyenergyplus.api import EnergyPlusAPI
from plugin import register_callbacks

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR = os.path.join(BASE_DIR, "models")
OUTPUTS_DIR = os.path.join(BASE_DIR, "outputs")

IDF_PATH = os.path.join(MODELS_DIR, "5ZoneAirCooled_smoke.idf")
EPW_PATH = os.path.join(MODELS_DIR, "USA_IL_Chicago-OHare.Intl.AP.725300_TMY3.epw")
OUT_DIR = os.path.join(OUTPUTS_DIR, "phase3_ems")

os.makedirs(OUT_DIR, exist_ok=True)
os.environ["EPW_PATH"] = EPW_PATH
groq_key = os.environ.get("GROQ_API_KEY")
if not groq_key:
    os.environ["GROQ_API_KEY"] = "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"

api = EnergyPlusAPI()
register_callbacks(api, baseline_mode=False)
state = api.state_manager.new_state()

argv = ["-d", OUT_DIR, "-w", EPW_PATH, IDF_PATH]

print("=" * 60)
print("PHASE 4 SMOKE TEST — LLM Agent running for 2 days")
print("=" * 60)

exit_code = api.runtime.run_energyplus(state, argv)
if exit_code != 0:
    print(f"EnergyPlus exited with code {exit_code}")
else:
    print("Smoke test completed successfully.")
