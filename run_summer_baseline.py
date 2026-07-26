"""Run Phase 2 baseline on summer (Tampa, July 1-7)."""
import sys, os
sys.path.append(r"C:\EnergyPlusV26-1-0")
from pyenergyplus.api import EnergyPlusAPI
from plugin import register_callbacks

BASE = os.path.dirname(os.path.abspath(__file__))
IDF = os.path.join(BASE, "models", "5ZoneAirCooled_summer.idf")
EPW = os.path.join(BASE, "models", "USA_FL_Tampa.Intl.AP.722110_TMY3.epw")
OUT = os.path.join(BASE, "outputs", "summer_baseline")

os.makedirs(OUT, exist_ok=True)
os.environ["EPW_PATH"] = EPW

api = EnergyPlusAPI()
register_callbacks(api, baseline_mode=True)
state = api.state_manager.new_state()

print("Running SUMMER BASELINE (Tampa, July 1-7)...")
exit_code = api.runtime.run_energyplus(state, ["-d", OUT, "-w", EPW, IDF])
if exit_code == 0:
    print(f"Complete. Output: {OUT}")
else:
    print(f"Failed with code {exit_code}")
