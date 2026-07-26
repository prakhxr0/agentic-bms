"""Agent tool functions - get zone state, energy, weather, errors."""

from src.ecoloop.io.weather import get_weather_lookahead
from src.ecoloop.io.state_store import read_state


# Global EMS context (set by plugin)
_ems_state = None
_exchange = None
_handles = {}


def set_ems_context(state, exchange, handles=None):
    """Called by plugin to register EMS handles."""
    global _ems_state, _exchange, _handles
    _ems_state = state
    _exchange = exchange
    if handles:
        _handles.update(handles)


def get_zone_state(zone_id: str = "SPACE1-1") -> dict:
    """Get current zone temperature and PMV."""
    if _exchange is None or not _handles:
        return {"error": "EMS not initialized"}

    h_temp = _handles.get(f"{zone_id}_temp")
    h_pmv = _handles.get(f"{zone_id}_pmv")

    if h_temp in (-1, None) or h_pmv in (-1, None):
        return {"zone": zone_id, "error": "sensor handles not available"}

    try:
        temp = _exchange.get_variable_value(_ems_state, h_temp)
        pmv = _exchange.get_variable_value(_ems_state, h_pmv)
        return {"zone": zone_id, "temperature_c": temp, "pmv": pmv}
    except Exception as e:
        return {"zone": zone_id, "error": str(e)}


def get_energy_metrics() -> dict:
    """Get current electricity meter readings."""
    if _exchange is None or not _handles:
        return {"cumulative_j": 0.0}

    h_bldg = _handles.get("Electricity:Building")
    h_hvac = _handles.get("Electricity:HVAC")

    if h_bldg in (-1, None) or h_hvac in (-1, None):
        return {"cumulative_j": 0.0}

    try:
        bldg_val = _exchange.get_meter_value(_ems_state, h_bldg)
        hvac_val = _exchange.get_meter_value(_ems_state, h_hvac)
        total_w = bldg_val + hvac_val
        return {"total_w": total_w, "building_w": bldg_val, "hvac_w": hvac_val}
    except Exception as e:
        return {"error": str(e)}


def check_simulation_errors() -> dict:
    """Check for any simulation errors (placeholder)."""
    # Could read .err file here if needed
    return {"errors": []}


# Module-level wrapper for agent compatibility
def get_weather_lookahead_wrapper(hours_ahead: int = 6) -> dict:
    """Wrapper matching agent.py signature."""
    return get_weather_lookahead(hours_ahead)