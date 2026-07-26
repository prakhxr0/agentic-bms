"""EnergyPlus Python Plugin - LLM agent controller with static-test fallback."""

import sys
import os
from pathlib import Path

# Ensure EnergyPlus API on path
EPLUS_PATH = r"C:\EnergyPlusV26-1-0"
if EPLUS_PATH not in sys.path:
    sys.path.append(EPLUS_PATH)

from pyenergyplus.plugin import EnergyPlusPlugin

from ecoloop.config import COOL_SCHEDULE_NAME, HEAT_SCHEDULE_NAME, ZONE_NAME
from ecoloop.sim.environment import is_sizing_period
from ecoloop.tools import (
    set_ems_context, get_zone_state, get_energy_metrics,
    check_simulation_errors, get_weather_lookahead_wrapper,
)
from ecoloop.io.state_store import write_state


# Control mode read from environment variable
_control_mode = os.environ.get("ECOLOOP_CONTROL_MODE", "static_test")


class Controller(EnergyPlusPlugin):
    """Plugin controller - delegates to LLM agent or static setpoints."""

    def __init__(self):
        super().__init__()
        self.handles_initialized = False
        self.zone_name = ZONE_NAME

        # Actuator handles
        self.h_cool_actuator = -1
        self.h_heat_actuator = -1

        # Agent state (used in AI mode only)
        self.decision_memory = []
        self.last_good = {"heating_sp": 21.0, "cooling_sp": 24.0}
        self.decision_counter = 0
        self.last_decision_day = -1
        self.last_decision_hour = -1

    def _init_handles(self, state):
        """Initialize EMS sensor + actuator handles once API is ready."""
        if not self.api.exchange.api_data_fully_ready(state):
            return

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

        # Actuator handles for schedule override
        self.h_cool_actuator = self.api.exchange.get_actuator_handle(
            state, "Schedule:Constant", "Schedule Value", COOL_SCHEDULE_NAME)
        self.h_heat_actuator = self.api.exchange.get_actuator_handle(
            state, "Schedule:Constant", "Schedule Value", HEAT_SCHEDULE_NAME)

        # Register sensor handles for tools module
        handles = {
            f"{self.zone_name}_temp": h_temp,
            f"{self.zone_name}_pmv": h_pmv,
            "Electricity:Building": h_bldg,
            "Electricity:HVAC": h_hvac,
        }
        set_ems_context(state, self.api.exchange, handles)
        self.handles_initialized = True

        print(f"[PLUGIN] Handles initialized. cool_actuator={self.h_cool_actuator}, "
              f"heat_actuator={self.h_heat_actuator}", flush=True)

    def on_begin_zone_timestep_before_set_current_weather(self, state):
        # Skip during sizing periods (env 1, 2)
        if is_sizing_period(state, self.api):
            return 0

        # Skip during warmup
        if self.api.exchange.warmup_flag(state):
            return 0

        # Initialize handles on first valid call
        if not self.handles_initialized:
            self._init_handles(state)
            if not self.handles_initialized:
                return 0  # API not ready yet

        if _control_mode == "ai":
            current_hour = self.api.exchange.hour(state)
            current_day = self.api.exchange.day_of_month(state)

            # Hourly gating: call LLM agent only when simulation hour changes
            if (current_day, current_hour) != (self.last_decision_day, self.last_decision_hour):
                self.last_decision_day = current_day
                self.last_decision_hour = current_hour
                self._apply_ai_decision(state)
            else:
                # Re-apply current setpoints on intermediate 15-min timesteps
                if self.h_cool_actuator != -1:
                    self.api.exchange.set_actuator_value(state, self.h_cool_actuator, self.last_good["cooling_sp"])
                if self.h_heat_actuator != -1:
                    self.api.exchange.set_actuator_value(state, self.h_heat_actuator, self.last_good["heating_sp"])
        else:
            self._apply_static_setpoints(state)

        return 0

    def _apply_static_setpoints(self, state):
        """Hardcoded 26/18°C for wiring verification."""
        if self.h_cool_actuator != -1:
            self.api.exchange.set_actuator_value(state, self.h_cool_actuator, 26.0)
        if self.h_heat_actuator != -1:
            self.api.exchange.set_actuator_value(state, self.h_heat_actuator, 18.0)

    def _apply_ai_decision(self, state):
        """Query LLM agent, clamp, actuate, log."""
        from ecoloop.control.agent import agent_decide
        from ecoloop.control.guardrail import clamp_setpoints

        self.decision_counter += 1

        # 1. Gather observations via tools
        zone_data = get_zone_state(self.zone_name)
        energy_data = get_energy_metrics()
        weather_data = get_weather_lookahead_wrapper(hours_ahead=6)
        errors = check_simulation_errors()

        # 2. Call LLM agent (has built-in retry + fallback to last_good)
        raw_decision = agent_decide(
            zone_data=zone_data,
            energy_data=energy_data,
            weather_data=weather_data,
            errors=errors,
            memory=self.decision_memory,
            last_good=self.last_good,
        )

        # 3. Clamp to ASHRAE 55 bounds + deadband
        clamped = clamp_setpoints(self.zone_name, raw_decision)
        cool_sp = clamped["cooling_sp"]
        heat_sp = clamped["heating_sp"]

        # 4. Actuate
        if self.h_cool_actuator != -1:
            self.api.exchange.set_actuator_value(state, self.h_cool_actuator, cool_sp)
        if self.h_heat_actuator != -1:
            self.api.exchange.set_actuator_value(state, self.h_heat_actuator, heat_sp)

        # 5. Update memory
        memory_entry = {
            "heating_sp": heat_sp,
            "cooling_sp": cool_sp,
            "pmv": zone_data.get("pmv"),
            "temp": zone_data.get("temperature_c"),
            "reasoning": raw_decision.get("reasoning", ""),
        }
        self.decision_memory.append(memory_entry)
        self.last_good = {"heating_sp": heat_sp, "cooling_sp": cool_sp}

        # 6. Log to state_history.jsonl
        log_entry = {
            "decision_num": self.decision_counter,
            "zone": self.zone_name,
            "zone_data": zone_data,
            "energy_data": energy_data,
            "weather_data": weather_data,
            "raw_decision": raw_decision,
            "clamped": clamped,
            "applied_cooling_sp": cool_sp,
            "applied_heating_sp": heat_sp,
        }
        write_state(log_entry)

        if self.decision_counter % 10 == 1:
            print(f"[PLUGIN] Decision #{self.decision_counter}: "
                  f"heat={heat_sp}°C cool={cool_sp}°C "
                  f"PMV={zone_data.get('pmv', '?'):.2f} "
                  f"reason={raw_decision.get('reasoning', '')[:80]}",
                  flush=True)


# Plugin entry point
_plugin_instance = None


def register_callbacks(api):
    global _plugin_instance
    _plugin_instance = Controller()