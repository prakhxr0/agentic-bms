"""Run 7-day AI via subprocess (no register_callbacks — EnergyPlus self-discovers the plugin)."""
import subprocess, os, time

BASE = os.path.dirname(os.path.abspath(__file__))
IDF = os.path.join(BASE, "models", "5ZoneAirCooled_summer.idf")
EPW = os.path.join(BASE, "models", "USA_IL_Chicago-OHare.Intl.AP.725300_TMY3.epw")
OUT = os.path.join(BASE, "outputs", "phase6_ai_v2")
LOG = os.path.join(BASE, "ai_7day_v2.log")
exe = r"C:\EnergyPlusV26-1-0\energyplus.exe"

os.makedirs(OUT, exist_ok=True)
env = os.environ.copy()
env["EPW_PATH"] = EPW

print(f"Launching AI 7-day via subprocess. Output: {OUT}")
print(f"Log: {LOG}")
print(f"This will take ~62 minutes.")

with open(LOG, "w") as log:
    proc = subprocess.Popen(
        [exe, "-d", OUT, "-w", EPW, IDF],
        stdout=log, stderr=subprocess.STDOUT, env=env
    )

with open("ai_7day_v2.pid", "w") as pf:
    pf.write(str(proc.pid))

print(f"PID: {proc.pid}")
print("Check progress: tail -5 ai_7day_v2.log")
print("Check alive: Get-Process -Id {} -ErrorAction SilentlyContinue".format(proc.pid))
