"""Run 7-day AI simulation (July 1-7). Redirects stdout to ai_7day_run.log."""
import sys, os

log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ai_7day_run.log")
log = open(log_path, "w", buffering=1)
sys.stdout = log

sys.path.append(r"C:\EnergyPlusV26-1-0")
from pyenergyplus.api import EnergyPlusAPI
from plugin import register_callbacks

BASE = os.path.dirname(os.path.abspath(__file__))
IDF = os.path.join(BASE, "models", "5ZoneAirCooled_summer.idf")
EPW = os.path.join(BASE, "models", "USA_IL_Chicago-OHare.Intl.AP.725300_TMY3.epw")
OUT_DIR = os.path.join(BASE, "outputs", "phase6_ai")
os.makedirs(OUT_DIR, exist_ok=True)
os.environ["EPW_PATH"] = EPW

print("Starting 7-day AI simulation (July 1-7)...")
api = EnergyPlusAPI()
register_callbacks(api, baseline_mode=False)
state = api.state_manager.new_state()
exit_code = api.runtime.run_energyplus(state, ["-d", OUT_DIR, "-w", EPW, IDF])
print(f"Exit code: {exit_code}")

sys.stdout = sys.__stdout__
log.close()
print(f"Done. Log: {log_path}")
print(f"Output: {OUT_DIR}")
