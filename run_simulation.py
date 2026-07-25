import sys
import os
import argparse

EPLUS_PATH = r"C:\EnergyPlusV26-1-0"
if EPLUS_PATH not in sys.path:
    sys.path.append(EPLUS_PATH)

from pyenergyplus.api import EnergyPlusAPI
from plugin import register_callbacks

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR = os.path.join(BASE_DIR, "models")
OUTPUTS_DIR = os.path.join(BASE_DIR, "outputs")

IDF_PATH = os.path.join(MODELS_DIR, "5ZoneAirCooled.idf")
EPW_PATH = os.path.join(MODELS_DIR, "USA_IL_Chicago-OHare.Intl.AP.725300_TMY3.epw")


def main():
    parser = argparse.ArgumentParser(description="Run EnergyPlus simulation")
    parser.add_argument("--baseline", action="store_true", help="Run in baseline mode (no setpoint override)")
    args = parser.parse_args()

    if args.baseline:
        out_dir = os.path.join(OUTPUTS_DIR, "baseline")
    else:
        out_dir = os.path.join(OUTPUTS_DIR, "override")

    os.makedirs(out_dir, exist_ok=True)

    api = EnergyPlusAPI()
    register_callbacks(api, baseline_mode=args.baseline)

    state = api.state_manager.new_state()

    argv = [
        "-d", out_dir,
        "-w", EPW_PATH,
        IDF_PATH,
    ]

    mode_label = "BASELINE" if args.baseline else "OVERRIDE"
    print(f"Running {mode_label} simulation...")
    exit_code = api.runtime.run_energyplus(state, argv)
    if exit_code != 0:
        print(f"EnergyPlus exited with code {exit_code}")
    else:
        print(f"{mode_label} simulation completed successfully.")
        print(f"Output directory: {out_dir}")


if __name__ == "__main__":
    main()
