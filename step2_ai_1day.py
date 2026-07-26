"""Step 2: Run 1-day AI test (July 1), redirect stdout to log."""
import sys, os

log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ai_1day_run.log")
log = open(log_path, "w", buffering=1)
sys.stdout = log

sys.path.append(r"C:\EnergyPlusV26-1-0")
from pyenergyplus.api import EnergyPlusAPI
from plugin import register_callbacks

BASE = os.path.dirname(os.path.abspath(__file__))
IDF = os.path.join(BASE, "models", "5ZoneAirCooled_summer_1d.idf")
EPW = os.path.join(BASE, "models", "USA_IL_Chicago-OHare.Intl.AP.725300_TMY3.epw")
OUT_DIR = os.path.join(BASE, "outputs", "ai_1day_test")
os.makedirs(OUT_DIR, exist_ok=True)
os.environ["EPW_PATH"] = EPW

print("Starting 1-day AI test (July 1)...")
api = EnergyPlusAPI()
register_callbacks(api, baseline_mode=False)
state = api.state_manager.new_state()
exit_code = api.runtime.run_energyplus(state, ["-d", OUT_DIR, "-w", EPW, IDF])
print(f"Exit code: {exit_code}")

sys.stdout = sys.__stdout__
log.close()
print(f"AI 1-day test done. Log: {log_path}")
print(f"Output: {OUT}")
