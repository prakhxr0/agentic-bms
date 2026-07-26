"""Step 1: Run July 1-7 baseline (no plugin), extract metrics."""
import subprocess, os, re, shutil

BASE = os.path.dirname(os.path.abspath(__file__))
IDF = os.path.join(BASE, "models", "5ZoneAirCooled_summer.idf")
EPW = os.path.join(BASE, "models", "USA_IL_Chicago-OHare.Intl.AP.725300_TMY3.epw")
OUT = os.path.join(BASE, "outputs", "summer_baseline")
exe = r"C:\EnergyPlusV26-1-0\energyplus.exe"

# Strip plugin
with open(IDF) as f:
    content = f.read()
content = re.sub(r"PythonPlugin:Instance,[^;]+;", "", content)
content = re.sub(r"PythonPlugin:SearchPaths,[^;]+;", "", content)
tmp = os.path.join(BASE, "models", "_tmp_baseline.idf")
with open(tmp, "w") as f:
    f.write(content)

os.makedirs(OUT, exist_ok=True)
print("Running baseline (July 1-7)...")
result = subprocess.run([exe, "-d", OUT, "-w", EPW, tmp], capture_output=True, text=True, timeout=120)
os.remove(tmp)

for line in result.stdout.split("\n"):
    if "Run Time" in line or "Completed" in line or "Terminated" in line:
        print(line.strip()[:120])
print(f"Exit: {result.returncode}")

# Extract metrics
print("\nExtracting metrics...")
subprocess.run([
    "python", "extract_baseline_metrics.py",
    "--output-dir", "outputs/summer_baseline",
    "--output-json", "summer_baseline_metrics.json"
], cwd=BASE, timeout=30)

import json
with open(os.path.join(BASE, "summer_baseline_metrics.json")) as f:
    m = json.load(f)
print(f"\nBaseline Metrics:")
print(f"  Total Energy: {m['total_kwh']} kWh")
print(f"  Peak: {m['peak_kw']} kW")
print(f"  Avg PMV: {m['avg_pmv']}")
print(f"  Comfort: {m['pmv_comfort_pct']}%")
