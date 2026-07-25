import sys
import os

EPLUS_PATH = r"C:\EnergyPlusV26-1-0"
if EPLUS_PATH not in sys.path:
    sys.path.append(EPLUS_PATH)

from pyenergyplus.api import EnergyPlusAPI
from pyenergyplus.plugin import EnergyPlusPlugin


class Controller(EnergyPlusPlugin):
    def __init__(self):
        super().__init__()
        self.cooling_sp = 24.0
        self.heating_sp = 21.0
        self.zone_name = "SPACE1-1"
        self.h_sensor = -1
        self.h_pvar_cool = -1
        self.h_pvar_heat = -1
        self.h_ems_cool = -1
        self.h_ems_heat = -1
        self.need_handles = True
        self.step_count = 0

    def get_handles(self, state):
        sensor_candidates = [
            ("Zone Air Temperature", self.zone_name),
            ("Zone Mean Air Temperature", self.zone_name),
        ]
        for var_name, var_key in sensor_candidates:
            h = self.api.exchange.get_variable_handle(state, var_name, var_key)
            if h != -1:
                self.h_sensor = h
                break

        self.h_pvar_cool = self.api.exchange.get_global_handle(state, "CoolingSetpoint")
        self.h_pvar_heat = self.api.exchange.get_global_handle(state, "HeatingSetpoint")

        self.h_ems_cool = self.api.exchange.get_ems_global_handle(state, "EMS_CoolingSetpoint")
        self.h_ems_heat = self.api.exchange.get_ems_global_handle(state, "EMS_HeatingSetpoint")

        self.need_handles = False

    def on_begin_zone_timestep_before_set_current_weather(self, state):
        if self.api.exchange.warmup_flag(state):
            return 0
        if self.need_handles:
            self.get_handles(state)

        self.step_count += 1

        if self.h_pvar_cool != -1:
            self.api.exchange.set_global_value(state, self.h_pvar_cool, self.cooling_sp)
        if self.h_pvar_heat != -1:
            self.api.exchange.set_global_value(state, self.h_pvar_heat, self.heating_sp)

        if self.h_ems_cool != -1:
            self.api.exchange.set_ems_global_value(state, self.h_ems_cool, self.cooling_sp)
        if self.h_ems_heat != -1:
            self.api.exchange.set_ems_global_value(state, self.h_ems_heat, self.heating_sp)

        if self.h_sensor != -1:
            temp = self.api.exchange.get_variable_value(state, self.h_sensor)
            if self.step_count % 24 == 1:
                print(
                    f"Step {self.step_count}: Zone {self.zone_name} temp={temp:.2f}C, "
                    f"Cooling SP={self.cooling_sp}C, Heating SP={self.heating_sp}C"
                )

        return 0


_plugin_instance = None


def register_callbacks(api):
    global _plugin_instance
    _plugin_instance = Controller()


if __name__ == "__main__":
    register_callbacks(EnergyPlusAPI())
