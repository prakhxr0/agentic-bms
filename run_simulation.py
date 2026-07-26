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
    parser.add_argument("--output-dir", type=str, default=None, help="Custom output directory (overrides default)")
    args = parser.parse_args()

    if args.output_dir:
        out_dir = args.output_dir
    elif args.baseline:
        out_dir = os.path.join(OUTPUTS_DIR, "baseline")
    else:
        out_dir = os.path.join(OUTPUTS_DIR, "override")

    os.makedirs(out_dir, exist_ok=True)

    # Inject EPW path and Groq API key as env vars so plugin/agent can find them
    os.environ["EPW_PATH"] = EPW_PATH
    groq_key = os.environ.get("GROQ_API_KEY")
    if not groq_key:
        groq_key = "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"
        os.environ["GROQ_API_KEY"] = groq_key

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
