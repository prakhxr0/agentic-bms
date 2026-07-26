import sys
import os
import logging

EPLUS_PATH = r"C:\EnergyPlusV26-1-0"
if EPLUS_PATH not in sys.path:
    sys.path.append(EPLUS_PATH)

# Ensure plugin's directory is on Python path for local module imports
PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
if PLUGIN_DIR not in sys.path:
    sys.path.append(PLUGIN_DIR)

from pyenergyplus.api import EnergyPlusAPI
from pyenergyplus.plugin import EnergyPlusPlugin

import guardrail
import state_store
import tools

from agent import agent_decide


class Controller(EnergyPlusPlugin):
    def __init__(self, baseline_mode=False):
        super().__init__()
        self.baseline_mode = baseline_mode
        self.zone_name = "SPACE1-1"
        self.cooling_sp = 24.0
        self.heating_sp = 21.0
        self.last_decision = {'heating_sp': 21.0, 'cooling_sp': 24.0}
        self.decision_memory = []
        self.decision_counter = 0
        
        # Actuator handles for direct schedule value override
        self.h_actuator_cool = -1
        self.h_actuator_heat = -1
        
        # Sensor handles
        self.h_sensor_temp = -1
        self.h_sensor_pmv = -1
        self.h_elec_building = -1
        self.h_elec_hvac = -1
        self.need_handles = True

    def get_handles(self, state):
        if not self.api.exchange.api_data_fully_ready(state):
            print("[DEBUG] get_handles: api_data_fully_ready=False, skipping", flush=True)
            return
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
        # Electricity meters
        self.h_elec_building = self.api.exchange.get_meter_handle(state, "Electricity:Building")
        self.h_elec_hvac = self.api.exchange.get_meter_handle(state, "Electricity:HVAC")
        print(f"[DEBUG] Meter handles: Elec:Building={self.h_elec_building} Elec:HVAC={self.h_elec_hvac}", flush=True)
        
        # Actuator handles for schedule value override (Clg-SetP-Sch, Htg-SetP-Sch are Schedule:Constant)
        self.h_actuator_cool = self.api.exchange.get_actuator_handle(
            state, "Schedule:Constant", "Schedule Value", "Clg-SetP-Sch")
        self.h_actuator_heat = self.api.exchange.get_actuator_handle(
            state, "Schedule:Constant", "Schedule Value", "Htg-SetP-Sch")
        
        print(f"[DEBUG] Actuator handles: cool={self.h_actuator_cool} heat={self.h_actuator_heat}", flush=True)
        print(f"[DEBUG] Sensor handles: temp={self.h_sensor_temp} pmv={self.h_sensor_pmv}", flush=True)
         
        # Set tools context
        handles = {
            f"{self.zone_name}_temp": self.h_sensor_temp,
            f"{self.zone_name}_pmv": self.h_sensor_pmv,
            "Electricity:Building": self.h_elec_building,
            "Electricity:HVAC": self.h_elec_hvac
        }
        tools.set_ems_context(state, self.api.exchange, handles)
        # Keep retrying until ALL critical handles (temperature + PMV) are obtained
        if self.h_sensor_temp != -1 and self.h_sensor_pmv != -1:
            self.need_handles = False

    def on_begin_zone_timestep_before_set_current_weather(self, state):
        if self.baseline_mode:
            # Baseline mode: let IDF's native schedules run; do nothing
            return 0

        # Skip actuation during sizing periods (environment 1=winter design, 2=summer design)
        # Only actuate during weather-file run periods (environment >= 3)
        current_env = self.api.exchange.current_environment_num(state)
        if current_env < 3:
            return 0

        if self.api.exchange.warmup_flag(state):
            return 0
        if self.need_handles:
            self.get_handles(state)
        # Hardcoded test values (26C cooling, 18C heating) for wiring verification
        self.last_decision = {'heating_sp': 18.0, 'cooling_sp': 26.0}
        # Apply current decision via direct schedule actuator override
        if self.h_actuator_cool != -1:
            self.api.exchange.set_actuator_value(state, self.h_actuator_cool, self.last_decision['cooling_sp'])
        if self.h_actuator_heat != -1:
            self.api.exchange.set_actuator_value(state, self.h_actuator_heat, self.last_decision['heating_sp'])
        return 0


_plugin_instance = None
_baseline_mode = False

def register_callbacks(api, baseline_mode=False):
    global _plugin_instance, _baseline_mode
    _baseline_mode = baseline_mode
    _plugin_instance = Controller(baseline_mode=baseline_mode)


if __name__ == "__main__":
    register_callbacks(EnergyPlusAPI())
