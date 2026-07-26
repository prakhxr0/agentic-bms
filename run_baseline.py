"""Run baseline simulation — strip PythonPlugin for true native behavior."""
import sys, os, re, subprocess

EPLUS = r"C:\EnergyPlusV26-1-0"
BASE = os.path.dirname(os.path.abspath(__file__))
IDF = os.path.join(BASE, "models", "5ZoneAirCooled_summer.idf")
EPW = os.path.join(BASE, "models", "USA_FL_Tampa.Intl.AP.722110_TMY3.epw")
OUT = os.path.join(BASE, "outputs", "summer_baseline")

os.makedirs(OUT, exist_ok=True)

with open(IDF, "r") as f:
    content = f.read()

# Strip all PythonPlugin objects so EnergyPlus runs with native schedules only
content = re.sub(r"PythonPlugin:Instance,[^;]+;", "", content)
content = re.sub(r"PythonPlugin:SearchPaths,[^;]+;", "", content)


tmp_idf = IDF.replace(".idf", "_noplugin.idf")
with open(tmp_idf, "w") as f:
    f.write(content)

exe = os.path.join(EPLUS, "energyplus.exe")
cmd = [exe, "-d", OUT, "-w", EPW, tmp_idf]

print("Running SUMMER BASELINE (Tampa, July 1-7, no plugin)...")
result = subprocess.run(cmd, capture_output=True, text=True)

os.remove(tmp_idf)

if result.returncode == 0:
    print("Baseline complete.")
else:
    print(f"Failed (code {result.returncode})")
    for line in result.stderr.split("\n")[-10:]:
        if line.strip():
            print(f"  {line.strip()}")
