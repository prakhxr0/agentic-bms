"""Run 1-day baseline — fast, no plugin."""
import subprocess, os, re

BASE = os.path.dirname(os.path.abspath(__file__))
IDF = os.path.join(BASE, "models", "5ZoneAirCooled_summer.idf")
EPW = os.path.join(BASE, "models", "USA_IL_Chicago-OHare.Intl.AP.725300_TMY3.epw")
OUT = os.path.join(BASE, "outputs", "summer_baseline_1d")
exe = r"C:\EnergyPlusV26-1-0\energyplus.exe"

with open(IDF) as f:
    content = f.read()
content = re.sub(r"PythonPlugin:Instance,[^;]+;", "", content)
content = re.sub(r"PythonPlugin:SearchPaths,[^;]+;", "", content)
tmp = os.path.join(BASE, "models", "_bp.idf")
with open(tmp, "w") as f:
    f.write(content)

os.makedirs(OUT, exist_ok=True)
result = subprocess.run(
    [exe, "-d", OUT, "-w", EPW, tmp],
    capture_output=True, text=True, timeout=120
)
os.remove(tmp)

for line in result.stdout.split("\n"):
    if "Run Time" in line or "Completed" in line or "Terminated" in line:
        print(line.strip()[:120])
for line in result.stderr.split("\n"):
    if line.strip():
        print("ERR:", line.strip()[:120])
print("Exit:", result.returncode)
