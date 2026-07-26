"""Launch AI simulation in background, log to file."""
import subprocess, os, time, sys

BASE = os.path.dirname(os.path.abspath(__file__))
IDF = os.path.join(BASE, "models", "5ZoneAirCooled_summer.idf")
EPW = os.path.join(BASE, "models", "USA_IL_Chicago-OHare.Intl.AP.725300_TMY3.epw")
OUT = os.path.join(BASE, "outputs", "phase6_ai_1d")
LOG = os.path.join(BASE, "ai_run.log")
PID_FILE = os.path.join(BASE, "ai_run.pid")

os.makedirs(OUT, exist_ok=True)
env = os.environ.copy()
env["EPW_PATH"] = EPW

exe = r"C:\EnergyPlusV26-1-0\energyplus.exe"
log_f = open(LOG, "w")

proc = subprocess.Popen(
    [exe, "-d", OUT, "-w", EPW, IDF],
    stdout=log_f, stderr=subprocess.STDOUT, env=env
)

with open(PID_FILE, "w") as pf:
    pf.write(str(proc.pid))

print(f"AI simulation launched (PID {proc.pid}). Log: {LOG}")
print("Waiting up to 15 minutes...")
try:
    rc = proc.wait(timeout=900)
    print(f"Exit code: {rc}")
    with open(LOG) as lf:
        for line in lf.readlines()[-5:]:
            if line.strip():
                print(f"  {line.strip()[:120]}")
except subprocess.TimeoutExpired:
    proc.kill()
    print("TIMEOUT after 15 min")
finally:
    log_f.close()
    if os.path.exists(PID_FILE):
        os.remove(PID_FILE)
