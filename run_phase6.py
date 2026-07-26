"""Phase 6: Baseline vs AI comparison - both via subprocess for clean isolation."""
import sys, os, re, subprocess

EPLUS = r"C:\EnergyPlusV26-1-0"
BASE = os.path.dirname(os.path.abspath(__file__))
IDF = os.path.join(BASE, "models", "5ZoneAirCooled_summer.idf")
EPW = os.path.join(BASE, "models", "USA_IL_Chicago-OHare.Intl.AP.725300_TMY3.epw")
exe = os.path.join(EPLUS, "energyplus.exe")

# === BASELINE: strip PythonPlugin so native schedules run ===
base_out = os.path.join(BASE, "outputs", "summer_baseline_1d")
os.makedirs(base_out, exist_ok=True)
with open(IDF, "r") as f:
    content = f.read()
content = re.sub(r"PythonPlugin:Instance,[^;]+;", "", content)
content = re.sub(r"PythonPlugin:SearchPaths,[^;]+;", "", content)
tmp_idf = IDF.replace(".idf", "_noplugin.idf")
with open(tmp_idf, "w") as f:
    f.write(content)
def run_sim(out_dir, idf_path, extra_env=None):
    os.makedirs(out_dir, exist_ok=True)
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)
    result = subprocess.run([exe, "-d", out_dir, "-w", EPW, idf_path],
                            capture_output=True, text=True, env=env)
    if result.returncode not in (0, 1):
        for line in result.stderr.split("\n")[-5:]:
            if line.strip():
                print(f"  {line.strip()}")
        raise RuntimeError(f"EnergyPlus failed (code {result.returncode})")
    print(f"Done -> {out_dir}")

print("Running BASELINE (no plugin)...")
run_sim(base_out, tmp_idf)
os.remove(tmp_idf)

ai_out = os.path.join(BASE, "outputs", "phase6_ai_1d")
print("Running AI (with plugin)...")
run_sim(ai_out, IDF, extra_env={"EPW_PATH": EPW})
print("AI done.")
