"""Guardrail/clamping logic for HVAC setpoints."""

from src.ecoloop.config import (
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
    clamped = proposed.copy()

    # Cooling setpoint must always be >= heating setpoint + deadband
    if clamped['cooling_sp'] < clamped['heating_sp'] + DEADBAND_MIN:
        clamped['cooling_sp'] = clamped['heating_sp'] + DEADBAND_MIN

    # Clamp individual values
    clamped['heating_sp'] = max(HEAT_SETPOINT_MIN, min(HEAT_SETPOINT_MAX, clamped['heating_sp']))
    clamped['cooling_sp'] = max(COOL_SETPOINT_MIN, min(COOL_SETPOINT_MAX, clamped['cooling_sp']))

    return clamped