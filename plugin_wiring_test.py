import sys
import os

EPLUS_PATH = r"C:\EnergyPlusV26-1-0"
if EPLUS_PATH not in sys.path:
    sys.path.append(EPLUS_PATH)

PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
if PLUGIN_DIR not in sys.path:
    sys.path.append(PLUGIN_DIR)

from pyenergyplus.api import EnergyPlusAPI
from pyenergyplus.plugin import EnergyPlusPlugin

class WiringTestController(EnergyPlusPlugin):
    def __init__(self):
        super().__init__()
        self.zone_name = "SPACE1-1"
        self.cool_actuator_handle = -1
        self.heat_actuator_handle = -1
        self.h_sensor_temp = -1
        self.h_sensor_pmv = -1
        self.h_electricity = -1
        self.need_handles = True
        self.applied = False

    def get_handles(self, state):
        if not self.api.exchange.api_data_fully_ready(state):
            print("[DEBUG] get_handles: api_data_fully_ready=False, skipping", flush=True)
            return
        
        # Schedule actuators - these are the Schedule:Constant objects Clg-SetP-Sch and Htg-SetP-Sch
        self.cool_actuator_handle = self.api.exchange.get_actuator_handle(
            state, "Schedule:Constant", "Schedule Value", "Clg-SetP-Sch")
        self.heat_actuator_handle = self.api.exchange.get_actuator_handle(
            state, "Schedule:Constant", "Schedule Value", "Htg-SetP-Sch")
        
        # Zone air temperature
        for var_name, var_key in [("Zone Air Temperature", self.zone_name),
                                   ("Zone Mean Air Temperature", self.zone_name)]:
            h = self.api.exchange.get_variable_handle(state, var_name, var_key)
            if h != -1:
                self.h_sensor_temp = h
                break
        
        # PMV
        self.h_sensor_pmv = self.api.exchange.get_variable_handle(
            state, "Zone Thermal Comfort Fanger Model PMV", self.zone_name + " PEOPLE 1")
        
        # Electricity
        self.h_elec_building = self.api.exchange.get_meter_handle(state, "Electricity:Building")
        self.h_elec_hvac = self.api.exchange.get_meter_handle(state, "Electricity:HVAC")
        
        print(f"[DEBUG] Handles: cool_act={self.cool_actuator_handle} heat_act={self.heat_actuator_handle} "
              f"temp={self.h_sensor_temp} pmv={self.h_sensor_pmv} "
              f"elec_b={self.h_elec_building} elec_hvac={self.h_elec_hvac}", flush=True)
        
        if self.h_sensor_temp != -1 and self.h_sensor_pmv != -1:
            self.need_handles = False

    def on_begin_zone_timestep_before_set_current_weather(self, state):
        # Debug: write to EnergyPlus error file
        self.api.runtime.issue_text(state, "WiringTest: callback invoked")
        
        # Skip actuation during sizing periods (environment 1=winter design, 2=summer design)
        # Only actuate during weather-file run periods (environment >= 3)
        env_num = self.api.exchange.current_environment_num(state)
        if env_num < 3:
            self.api.runtime.issue_text(state, f"WiringTest: skipping, env_num={env_num}")
            return 0

        if self.api.exchange.warmup_flag(state):
            self.api.runtime.issue_text(state, "WiringTest: warmup_flag=True, skipping")
            return 0
            
        if self.need_handles:
            self.get_handles(state)
            if self.need_handles:
                return 0
        
        # Apply hardcoded test values (26C cooling, 18C heating) ONCE after warmup
        if not self.applied and self.cool_actuator_handle != -1 and self.heat_actuator_handle != -1:
            self.api.exchange.set_actuator_value(state, self.cool_actuator_handle, 26.0)
            self.api.exchange.set_actuator_value(state, self.heat_actuator_handle, 18.0)
            self.api.runtime.issue_text(state, f"WiringTest: APPLIED hardcoded values: Clg-SetP-Sch=26.0, Htg-SetP-Sch=18.0")
            self.applied = True
        
        # Log values for verification
        if self.h_sensor_temp != -1:
            temp = self.api.exchange.get_variable_value(state, self.h_sensor_temp)
            self.api.runtime.issue_text(state, f"WiringTest: Zone temp: {temp:.2f}C")
        
        return 0

_plugin_instance = None

def register_callbacks(api):
    global _plugin_instance
    _plugin_instance = WiringTestController()

if __name__ == "__main__":
    register_callbacks(EnergyPlusAPI())