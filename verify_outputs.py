import sys
import os
import re

EPLUS_PATH = r"C:\EnergyPlusV26-1-0"
if EPLUS_PATH not in sys.path:
    sys.path.append(EPLUS_PATH)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUTS_DIR = os.path.join(BASE_DIR, "outputs")
LOG_PATH = os.path.join(OUTPUTS_DIR, "sim_log.txt")
ESO_PATH = os.path.join(OUTPUTS_DIR, "eplusout.eso")

EXPECTED_COOLING_SP = 24.0
EXPECTED_HEATING_SP = 21.0
ZONE = "SPACE1-1"


def parse_eso(eso_path):
    metadata = {}
    data = {}

    with open(eso_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if line.startswith("Program Version"):
                continue

            if re.match(r"^\d+,\d+,", line):
                parts = line.split(",", 4)
                if len(parts) >= 4:
                    idx = parts[0].strip()
                    freq = parts[1].strip()
                    key = parts[2].strip()
                    name = parts[3].strip().split("!")[0].strip()
                    metadata[idx] = {"key": key, "name": name, "freq": freq}
            else:
                parts = line.split(",", 1)
                if len(parts) == 2:
                    idx = parts[0].strip()
                    val_str = parts[1].strip()
                    if idx in metadata:
                        try:
                            val = float(val_str)
                            if idx not in data:
                                data[idx] = []
                            data[idx].append(val)
                        except ValueError:
                            pass

    return metadata, data


def verify_simulation():
    print("=" * 60)
    print("1. Verifying simulation completed without fatal errors...")
    print("=" * 60)

    if not os.path.exists(LOG_PATH):
        print("FAIL: sim_log.txt not found")
        return False

    with open(LOG_PATH, "r") as f:
        content = f.read()

    if "Fatal" in content:
        print("FAIL: Simulation had fatal errors")
        for line in content.split("\n"):
            if "Fatal" in line:
                print(f"  {line.strip()}")
        return False

    if "Step" in content:
        step_lines = [l for l in content.split("\n") if l.startswith("Step ")]
        print(f"PASS: Simulation completed, plugin logged {len(step_lines)} timesteps")
        if step_lines:
            print(f"  First: {step_lines[0].strip()}")
            print(f"  Last:  {step_lines[-1].strip()}")
    else:
        print("PASS: Simulation completed")

    return True


def verify_eso():
    print("\n" + "=" * 60)
    print("2. Verifying eplusout.eso for setpoint overrides...")
    print("=" * 60)

    if not os.path.exists(ESO_PATH):
        print("FAIL: eplusout.eso not found")
        return False

    metadata, data = parse_eso(ESO_PATH)
    print(f"Total variables in ESO: {len(metadata)}")

    zone_vars = {idx: info for idx, info in metadata.items() if info["key"] == ZONE}
    print(f"Variables for {ZONE}: {len(zone_vars)}")
    for idx, info in sorted(zone_vars.items()):
        vals = data.get(idx, [])
        print(f"  [{idx}] {info['name']} - {len(vals)} values")

    cooling_idx = None
    heating_idx = None
    temp_idx = None

    for idx, info in zone_vars.items():
        if "Cooling Setpoint" in info["name"]:
            cooling_idx = idx
        elif "Heating Setpoint" in info["name"]:
            heating_idx = idx
        elif "Air Temperature" in info["name"] and "Dewpoint" not in info["name"]:
            temp_idx = idx

    passed = True

    if cooling_idx:
        values = data.get(cooling_idx, [])
        unique_vals = sorted(set(values))
        print(f"\nCooling setpoint unique values: {unique_vals}")
        has_override = any(abs(v - EXPECTED_COOLING_SP) < 0.01 for v in unique_vals)
        if has_override:
            print(f"PASS: Cooling setpoint override ({EXPECTED_COOLING_SP}C) confirmed in ESO")
        else:
            print(f"INFO: Expected {EXPECTED_COOLING_SP}C not found")
            passed = False
    else:
        print("\nFAIL: Cooling setpoint variable not found")
        passed = False

    if heating_idx:
        values = data.get(heating_idx, [])
        unique_vals = sorted(set(values))
        print(f"Heating setpoint unique values: {unique_vals}")
        has_override = any(abs(v - EXPECTED_HEATING_SP) < 0.01 for v in unique_vals)
        if has_override:
            print(f"PASS: Heating setpoint override ({EXPECTED_HEATING_SP}C) confirmed in ESO")
        else:
            print(f"INFO: Expected {EXPECTED_HEATING_SP}C not found")
            passed = False
    else:
        print("FAIL: Heating setpoint variable not found")
        passed = False

    if temp_idx:
        values = data.get(temp_idx, [])
        if values:
            print(f"\nZone temp range: {min(values):.2f} - {max(values):.2f} C")
            print(f"Zone temp mean: {sum(values)/len(values):.2f} C")
            print("PASS: Zone temperature data present")
        else:
            print("INFO: No zone temperature data")
    else:
        print("INFO: Zone temperature variable not found")

    return passed


def main():
    sim_ok = verify_simulation()
    eso_ok = verify_eso()

    print("\n" + "=" * 60)
    if sim_ok and eso_ok:
        print("ALL VERIFICATIONS PASSED")
    else:
        print("SOME CHECKS FAILED - see above")
    print("=" * 60)


if __name__ == "__main__":
    main()
