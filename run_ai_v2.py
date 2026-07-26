"""7-day AI run via subprocess — no register_callbacks, EnergyPlus self-discovers plugin."""
import subprocess, os

BASE = os.path.dirname(os.path.abspath(__file__))
IDF = os.path.join(BASE, "models", "5ZoneAirCooled_summer.idf")
EPW = os.path.join(BASE, "models", "USA_IL_Chicago-OHare.Intl.AP.725300_TMY3.epw")
OUT = os.path.join(BASE, "outputs", "phase6_ai_v2")
exe = r"C:\EnergyPlusV26-1-0\energyplus.exe"
os.makedirs(OUT, exist_ok=True)

env = os.environ.copy()
env["EPW_PATH"] = EPW

print("Running AI 7-day v2 (subprocess, no register_callbacks)...")
result = subprocess.run([exe, "-d", OUT, "-w", EPW, IDF],
                        capture_output=True, text=True, timeout=3600, env=env)
for line in result.stdout.split("\n"):
    if any(x in line for x in ["Run Time", "Completed", "Terminated", "AGENT Reasoning"]):
        print(line.strip()[:120])
print(f"Exit: {result.returncode}")
