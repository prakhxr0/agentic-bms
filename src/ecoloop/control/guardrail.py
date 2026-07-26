"""Guardrail/clamping logic for HVAC setpoints."""

from ecoloop.config import (
    HEAT_SETPOINT_MIN, HEAT_SETPOINT_MAX,
    COOL_SETPOINT_MIN, COOL_SETPOINT_MAX,
    DEADBAND_MIN
)


def clamp_setpoints(zone_id: str, proposed: dict) -> dict:
    """
    Enforce hard comfort/safety bounds on setpoints.
    proposed = {'heating_sp': float, 'cooling_sp': float}
    Returns clamped dict.
    """
    heat = proposed.get("heating_sp", HEAT_SETPOINT_MIN)
    cool = proposed.get("cooling_sp", COOL_SETPOINT_MAX)

    # Clamp individual bounds first
    heat = max(HEAT_SETPOINT_MIN, min(HEAT_SETPOINT_MAX, heat))
    cool = max(COOL_SETPOINT_MIN, min(COOL_SETPOINT_MAX, cool))

    # Enforce deadband: cooling >= heating + DEADBAND_MIN
    if cool - heat < DEADBAND_MIN:
        if heat + DEADBAND_MIN <= COOL_SETPOINT_MAX:
            cool = heat + DEADBAND_MIN
        else:
            heat = cool - DEADBAND_MIN
            heat = max(HEAT_SETPOINT_MIN, heat)

    return {"heating_sp": round(heat, 1), "cooling_sp": round(cool, 1)}