import json

try:
    with open("state_history.jsonl") as f:
        lines = f.readlines()
except FileNotFoundError:
    # Check in output directories
    import os
    for path in ["outputs/phase6_ai/state_history.jsonl", "outputs/ai_1day_test/state_history.jsonl", "state_history.jsonl"]:
        if os.path.exists(path):
            with open(path) as f:
                lines = f.readlines()
            break
    else:
        print("No state file found")
        exit()

print("Decisions logged:", len(lines))
if not lines:
    exit()

first = json.loads(lines[0])
last = json.loads(lines[-1])
print("First: heat={} cool={} PMV={:.3f}".format(
    first["decision"]["heating_sp"], first["decision"]["cooling_sp"], first["zone"]["pmv"]))
print("Last:  heat={} cool={} PMV={:.3f}".format(
    last["decision"]["heating_sp"], last["decision"]["cooling_sp"], last["zone"]["pmv"]))

# Show every ~24th decision (1 day apart for 7 days)
print("\nDaily samples:")
for i in range(0, len(lines), 24):
    d = json.loads(lines[i])
    print("  Day {}: heat={} cool={} temp={:.1f} PMV={:.3f}".format(
        i//24 + 1,
        d["decision"]["heating_sp"], d["decision"]["cooling_sp"],
        d["zone"]["temperature_c"], d["zone"]["pmv"]))
