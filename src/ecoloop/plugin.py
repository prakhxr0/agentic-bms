"""EnergyPlus Python Plugin - thin wrapper delegating to static_controller."""

import sys
from pathlib import Path

# Ensure EnergyPlus API on path
EPLUS_PATH = r"C:\EnergyPlusV26-1-0"
if EPLUS_PATH not in sys.path:
    sys.path.append(EPLUS_PATH)

PLUGIN_DIR = Path(__file__).resolve().parents[3]  # project root
if str(PLUGIN_DIR) not in sys.path:
    sys.path.append(str(PLUGIN_DIR))

from pyenergyplus.plugin import EnergyPlusPlugin

from src.ecoloop.control.static_controller import apply_static_test_setpoints
from src.ecoloop.tools import set_ems_context


class Controller(EnergyPlusPlugin):
    """Minimal plugin - delegates all logic to static_controller."""

    def __init__(self):
        super().__init__()
        self.handles_initialized = False
        self.zone_name = "SPACE1-1"

    def on_begin_zone_timestep_before_set_current_weather(self, state):
        # Initialize EMS handles on first call after API ready
        if not self.handles_initialized:
            if self.api.exchange.api_data_fully_ready(state):
                # Zone air temperature
                h_temp = self.api.exchange.get_variable_handle(
                    state, "Zone Air Temperature", self.zone_name)
                # PMV
                h_pmv = self.api.exchange.get_variable_handle(
                    state, "Zone Thermal Comfort Fanger Model PMV",
                    f"{self.zone_name} PEOPLE 1")
                # Electricity meters
                h_bldg = self.api.exchange.get_meter_handle(state, "Electricity:Building")
                h_hvac = self.api.exchange.get_meter_handle(state, "Electricity:HVAC")

                handles = {
                    f"{self.zone_name}_temp": h_temp,
                    f"{self.zone_name}_pmv": h_pmv,
                    "Electricity:Building": h_bldg,
                    "Electricity:HVAC": h_hvac,
                }
                set_ems_context(state, self.api.exchange, handles)
                self.handles_initialized = True

        # Apply hardcoded test setpoints (26°C / 18°C)
        apply_static_test_setpoints(state, self.api)
        return 0


# Plugin entry point
_plugin_instance = None


def register_callbacks(api):
    global _plugin_instance
    _plugin_instance = Controller()