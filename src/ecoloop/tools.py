"""Agent tool functions — zone state, energy, weather, errors.

Each tool emits a tool_call / tool_result event for the live demo TUI so the
EnergyPlus → observation path is visible during a PoC recording.
"""

from __future__ import annotations

from datetime import datetime

from ecoloop.io.event_bus import emit
from ecoloop.io.weather import get_weather_lookahead

# Global EMS context (set by plugin)
_ems_state = None
_exchange = None
_handles: dict = {}
_sim_clock: dict | None = None


def set_ems_context(state, exchange, handles=None):
    """Called by plugin to register EMS handles."""
    global _ems_state, _exchange, _handles
    _ems_state = state
    _exchange = exchange
    if handles:
        _handles.update(handles)


def set_sim_clock(clock: dict | None):
    """Update simulation clock used by weather tool."""
    global _sim_clock
    _sim_clock = clock


def get_sim_clock() -> dict | None:
    return _sim_clock


def _clock_dt() -> datetime | None:
    if not _sim_clock:
        return None
    try:
        return datetime(
            int(_sim_clock.get("year") or 2009),
            int(_sim_clock["month"]),
            int(_sim_clock["day"]),
            int(_sim_clock["hour"]),
        )
    except (KeyError, TypeError, ValueError):
        return None


def get_zone_state(zone_id: str = "SPACE1-1") -> dict:
    """Get current zone temperature and PMV from EnergyPlus EMS sensors."""
    emit("tool_call", tool="get_zone_state", args={"zone_id": zone_id})
    if _exchange is None or not _handles:
        result = {"error": "EMS not initialized"}
        emit("tool_result", tool="get_zone_state", result=result)
        return result

    h_temp = _handles.get(f"{zone_id}_temp")
    h_pmv = _handles.get(f"{zone_id}_pmv")

    if h_temp in (-1, None) or h_pmv in (-1, None):
        result = {"zone": zone_id, "error": "sensor handles not available"}
        emit("tool_result", tool="get_zone_state", result=result)
        return result

    try:
        temp = _exchange.get_variable_value(_ems_state, h_temp)
        pmv = _exchange.get_variable_value(_ems_state, h_pmv)
        result = {
            "zone": zone_id,
            "temperature_c": round(float(temp), 3),
            "pmv": round(float(pmv), 4),
        }
    except Exception as e:
        result = {"zone": zone_id, "error": str(e)}

    emit("tool_result", tool="get_zone_state", result=result)
    return result


def get_energy_metrics() -> dict:
    """Get current electricity meter readings from EnergyPlus."""
    emit("tool_call", tool="get_energy_metrics", args={})
    if _exchange is None or not _handles:
        result = {"cumulative_j": 0.0}
        emit("tool_result", tool="get_energy_metrics", result=result)
        return result

    h_bldg = _handles.get("Electricity:Building")
    h_hvac = _handles.get("Electricity:HVAC")

    if h_bldg in (-1, None) or h_hvac in (-1, None):
        result = {"cumulative_j": 0.0}
        emit("tool_result", tool="get_energy_metrics", result=result)
        return result

    try:
        bldg_val = float(_exchange.get_meter_value(_ems_state, h_bldg))
        hvac_val = float(_exchange.get_meter_value(_ems_state, h_hvac))
        result = {
            "total_w": round(bldg_val + hvac_val, 1),
            "building_w": round(bldg_val, 1),
            "hvac_w": round(hvac_val, 1),
        }
    except Exception as e:
        result = {"error": str(e)}

    emit("tool_result", tool="get_energy_metrics", result=result)
    return result


def check_simulation_errors() -> dict:
    """Check for any simulation errors (placeholder)."""
    emit("tool_call", tool="check_simulation_errors", args={})
    result = {"errors": []}
    emit("tool_result", tool="check_simulation_errors", result=result)
    return result


def get_weather_lookahead_wrapper(hours_ahead: int = 6) -> dict:
    """EPW weather lookahead at the current simulation hour."""
    emit(
        "tool_call",
        tool="get_weather_lookahead",
        args={"hours_ahead": hours_ahead, "sim_clock": _sim_clock},
    )
    ref = _clock_dt()
    result = get_weather_lookahead(hours_ahead, reference_time=ref)
    emit("tool_result", tool="get_weather_lookahead", result=result)
    return result
