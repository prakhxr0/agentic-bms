"""Run 1-day AI simulation with direct actuator control."""
import sys, os, subprocess

BASE = os.path.dirname(os.path.abspath(__file__))
IDF = os.path.join(BASE, "models", "5ZoneAirCooled_summer.idf")
EPW = os.path.join(BASE, "models", "USA_IL_Chicago-OHare.Intl.AP.725300_TMY3.epw")
OUT = os.path.join(BASE, "outputs", "phase6_ai_1d")
os.makedirs(OUT, exist_ok=True)

env = os.environ.copy()
env["EPW_PATH"] = EPW

exe = r"C:\EnergyPlusV26-1-0\energyplus.exe"
result = subprocess.run(
    [exe, "-d", OUT, "-w", EPW, IDF],
    capture_output=True, text=True, env=env, timeout=900
)

print(f"Exit code: {result.returncode}")
for line in result.stdout.split("\n")[-5:]:
    if line.strip():
        print(f"  {line.strip()[:120]}")
for line in result.stderr.split("\n")[-3:]:
    if line.strip():
        print(f"  ERR: {line.strip()[:120]}")
