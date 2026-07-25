import sys
import os

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
    os.makedirs(OUTPUTS_DIR, exist_ok=True)

    api = EnergyPlusAPI()
    register_callbacks(api)

    state = api.state_manager.new_state()

    argv = [
        "-d", OUTPUTS_DIR,
        "-w", EPW_PATH,
        IDF_PATH,
    ]

    exit_code = api.runtime.run_energyplus(state, argv)
    if exit_code != 0:
        print(f"EnergyPlus exited with code {exit_code}")
    else:
        print("Simulation completed successfully.")


if __name__ == "__main__":
    main()