"""EnergyPlus Python Plugin - LLM agent controller with static-test fallback."""

from __future__ import annotations

import os
import sys

# Ensure EnergyPlus API on path
EPLUS_PATH = r"C:\EnergyPlusV26-1-0"
if EPLUS_PATH not in sys.path:
    sys.path.append(EPLUS_PATH)

from pyenergyplus.plugin import EnergyPlusPlugin

from ecoloop.config import COOL_SCHEDULE_NAME, HEAT_SCHEDULE_NAME, ZONE_NAME
from ecoloop.io.event_bus import emit
from ecoloop.io.state_store import write_state
from ecoloop.sim.environment import is_sizing_period
from ecoloop.tools import (
    check_simulation_errors,
    get_energy_metrics,
    get_weather_lookahead_wrapper,
    get_zone_state,
    set_ems_context,
    set_sim_clock,
)

# Control mode read from environment variable
_control_mode = os.environ.get("ECOLOOP_CONTROL_MODE", "static_test")
# Optional cap for short PoC recordings (0 = unlimited)
try:
    _max_decisions = int(os.environ.get("ECOLOOP_MAX_DECISIONS", "0"))
except ValueError:
    _max_decisions = 0


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
        self._announced = False

    def _init_handles(self, state):
        """Initialize EMS sensor + actuator handles once API is ready."""
        if not self.api.exchange.api_data_fully_ready(state):
            return

        # Zone air temperature
        h_temp = self.api.exchange.get_variable_handle(
            state, "Zone Air Temperature", self.zone_name
        )
        # PMV
        h_pmv = self.api.exchange.get_variable_handle(
            state,
            "Zone Thermal Comfort Fanger Model PMV",
            f"{self.zone_name} PEOPLE 1",
        )
        # Electricity meters
        h_bldg = self.api.exchange.get_meter_handle(state, "Electricity:Building")
        h_hvac = self.api.exchange.get_meter_handle(state, "Electricity:HVAC")

        # Actuator handles for schedule override
        self.h_cool_actuator = self.api.exchange.get_actuator_handle(
            state, "Schedule:Constant", "Schedule Value", COOL_SCHEDULE_NAME
        )
        self.h_heat_actuator = self.api.exchange.get_actuator_handle(
            state, "Schedule:Constant", "Schedule Value", HEAT_SCHEDULE_NAME
        )

        # Register sensor handles for tools module
        handles = {
            f"{self.zone_name}_temp": h_temp,
            f"{self.zone_name}_pmv": h_pmv,
            "Electricity:Building": h_bldg,
            "Electricity:HVAC": h_hvac,
        }
        set_ems_context(state, self.api.exchange, handles)
        self.handles_initialized = True

        msg = (
            f"[PLUGIN] Handles initialized. cool_actuator={self.h_cool_actuator}, "
            f"heat_actuator={self.h_heat_actuator}"
        )
        print(msg, flush=True)
        emit(
            "status",
            message="EMS handles ready",
            cool_actuator=self.h_cool_actuator,
            heat_actuator=self.h_heat_actuator,
            control_mode=_control_mode,
        )

    def _read_sim_clock(self, state) -> dict:
        year = 2009
        try:
            year = int(self.api.exchange.year(state))
        except Exception:
            pass
        clock = {
            "year": year,
            "month": int(self.api.exchange.month(state)),
            "day": int(self.api.exchange.day_of_month(state)),
            "hour": int(self.api.exchange.hour(state)),
            "minute": int(self.api.exchange.minutes(state)),
        }
        set_sim_clock(clock)
        return clock

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

        if not self._announced:
            self._announced = True
            emit("status", message=f"Control loop active (mode={_control_mode})")

        clock = self._read_sim_clock(state)

        if _control_mode == "ai":
            current_hour = clock["hour"]
            current_day = clock["day"]

            # Hourly gating: call LLM agent only when simulation hour changes
            if (current_day, current_hour) != (
                self.last_decision_day,
                self.last_decision_hour,
            ):
                self.last_decision_day = current_day
                self.last_decision_hour = current_hour
                emit("sim_clock", **clock, event="hour_gate")
                # Short demo: after N LLM decisions, hold last-good setpoints only
                if _max_decisions > 0 and self.decision_counter >= _max_decisions:
                    self._actuate(
                        state,
                        self.last_good["cooling_sp"],
                        self.last_good["heating_sp"],
                        reapply=True,
                    )
                else:
                    self._apply_ai_decision(state, clock)
            else:
                # Re-apply current setpoints on intermediate 15-min timesteps
                self._actuate(
                    state,
                    self.last_good["cooling_sp"],
                    self.last_good["heating_sp"],
                    reapply=True,
                )
        else:
            self._apply_static_setpoints(state)

        return 0

    def _actuate(self, state, cool_sp: float, heat_sp: float, reapply: bool = False):
        if self.h_cool_actuator != -1:
            self.api.exchange.set_actuator_value(state, self.h_cool_actuator, cool_sp)
        if self.h_heat_actuator != -1:
            self.api.exchange.set_actuator_value(state, self.h_heat_actuator, heat_sp)
        if not reapply:
            emit(
                "actuate",
                cooling_sp=cool_sp,
                heating_sp=heat_sp,
                cool_handle=self.h_cool_actuator,
                heat_handle=self.h_heat_actuator,
                schedule_cool=COOL_SCHEDULE_NAME,
                schedule_heat=HEAT_SCHEDULE_NAME,
            )

    def _apply_static_setpoints(self, state):
        """Hardcoded 26/18°C for wiring verification."""
        self._actuate(state, 26.0, 18.0)

    def _apply_ai_decision(self, state, clock: dict):
        """Query LLM agent, clamp, actuate, log."""
        from ecoloop.control.agent import agent_decide
        from ecoloop.control.guardrail import clamp_setpoints

        self.decision_counter += 1
        dnum = self.decision_counter

        emit(
            "decision",
            phase="start",
            decision_num=dnum,
            sim_clock=clock,
            zone=self.zone_name,
        )

        # 1. Gather observations via tools (each tool emits tool_call/result)
        zone_data = get_zone_state(self.zone_name)
        energy_data = get_energy_metrics()
        weather_data = get_weather_lookahead_wrapper(hours_ahead=6)
        errors = check_simulation_errors()

        emit(
            "status",
            message="Observations ready → calling LLM",
            decision_num=dnum,
            zone_data=zone_data,
            energy_data=energy_data,
            weather_data=weather_data,
        )

        # 2. Call LLM agent (has built-in retry + fallback to last_good)
        raw_decision = agent_decide(
            zone_data=zone_data,
            energy_data=energy_data,
            weather_data=weather_data,
            errors=errors,
            memory=self.decision_memory,
            last_good=self.last_good,
            decision_num=dnum,
            sim_clock=clock,
        )

        # 3. Clamp to ASHRAE 55 bounds + deadband
        clamped = clamp_setpoints(self.zone_name, raw_decision)
        cool_sp = clamped["cooling_sp"]
        heat_sp = clamped["heating_sp"]
        emit(
            "guardrail",
            decision_num=dnum,
            raw=raw_decision,
            clamped=clamped,
            changed=(
                float(raw_decision.get("heating_sp", heat_sp)) != heat_sp
                or float(raw_decision.get("cooling_sp", cool_sp)) != cool_sp
            ),
        )

        # 4. Actuate EnergyPlus schedules
        self._actuate(state, cool_sp, heat_sp)

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
            "decision_num": dnum,
            "sim_clock": clock,
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

        emit(
            "decision",
            phase="complete",
            decision_num=dnum,
            sim_clock=clock,
            zone_data=zone_data,
            energy_data=energy_data,
            weather_data=weather_data,
            raw_decision=raw_decision,
            clamped=clamped,
            applied_cooling_sp=cool_sp,
            applied_heating_sp=heat_sp,
            source=raw_decision.get("source"),
            thinking=raw_decision.get("thinking", ""),
            reasoning=raw_decision.get("reasoning", ""),
        )

        print(
            f"[PLUGIN] Decision #{dnum}: "
            f"sim={clock['month']:02d}/{clock['day']:02d} {clock['hour']:02d}:00 "
            f"heat={heat_sp}°C cool={cool_sp}°C "
            f"PMV={zone_data.get('pmv', '?')} "
            f"src={raw_decision.get('source', '?')} "
            f"reason={str(raw_decision.get('reasoning', ''))[:80]}",
            flush=True,
        )


# Plugin entry point
_plugin_instance = None


def register_callbacks(api):
    global _plugin_instance
    _plugin_instance = Controller()
