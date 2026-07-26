"""1-day AI test via subprocess — EnergyPlus self-discovers plugin."""
import subprocess, os

BASE = os.path.dirname(os.path.abspath(__file__))
IDF = os.path.join(BASE, "models", "5ZoneAirCooled_summer_1d.idf")
EPW = os.path.join(BASE, "models", "USA_IL_Chicago-OHare.Intl.AP.725300_TMY3.epw")
OUT = os.path.join(BASE, "outputs", "ai_1day_test_v3")
exe = r"C:\EnergyPlusV26-1-0\energyplus.exe"
os.makedirs(OUT, exist_ok=True)

env = os.environ.copy()
env["EPW_PATH"] = EPW
env["GROQ_API_KEY"] = "dummy"

result = subprocess.run([exe, "-d", OUT, "-w", EPW, IDF],
                        capture_output=True, text=True, timeout=600, env=env)
for line in result.stdout.split("\n"):
    if any(x in line for x in ["Run Time", "Completed", "Terminated", "AGENT", "act_cool", "Handles"]):
        print(line.strip()[:150])
print(f"Exit: {result.returncode}")
