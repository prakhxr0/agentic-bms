"""Run AI simulation via pyenergyplus API, redirecting prints to log file."""
import sys, os

# Redirect stdout to log file
log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ai_run.log")
log = open(log_path, "w", buffering=1)
_orig_stdout = sys.stdout
sys.stdout = log

sys.path.append(r"C:\EnergyPlusV26-1-0")
from pyenergyplus.api import EnergyPlusAPI
from plugin import register_callbacks

BASE = os.path.dirname(os.path.abspath(__file__))
IDF = os.path.join(BASE, "models", "5ZoneAirCooled_summer.idf")
EPW = os.path.join(BASE, "models", "USA_IL_Chicago-OHare.Intl.AP.725300_TMY3.epw")
OUT = os.path.join(BASE, "outputs", "phase6_ai_1d")
os.makedirs(OUT, exist_ok=True)
os.environ["EPW_PATH"] = EPW

print("Starting AI simulation...")
api = EnergyPlusAPI()
register_callbacks(api, baseline_mode=False)
state = api.state_manager.new_state()
exit_code = api.runtime.run_energyplus(state, ["-d", OUT, "-w", EPW, IDF])
print(f"Exit code: {exit_code}")

sys.stdout = _orig_stdout
log.close()
print(f"Done. Log: {log_path}")
