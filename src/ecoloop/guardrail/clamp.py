"""Guardrail clamping for LLM-proposed setpoints."""

ASHRAE_COOL_MIN = 22.0
ASHRAE_COOL_MAX = 28.0
ASHRAE_HEAT_MIN = 18.0
ASHRAE_HEAT_MAX = 24.0
DEADBAND_MIN = 2.0


def clamp_setpoints(zone_name: str, proposed: dict) -> dict:
    """
    Clamp proposed heating/cooling setpoints to ASHRAE 55 limits and enforce deadband.

    Args:
        zone_name: Zone identifier (unused, kept for future per-zone limits).
        proposed: Dict with keys 'heating_sp', 'cooling_sp', optionally 'reasoning'.

    Returns:
        Dict with clamped 'heating_sp', 'cooling_sp'.
    """
    heat = proposed.get("heating_sp", ASHRAE_HEAT_MIN)
    cool = proposed.get("cooling_sp", ASHRAE_COOL_MAX)

    # Clamp individual bounds
    heat = max(ASHRAE_HEAT_MIN, min(ASHRAE_HEAT_MAX, heat))
    cool = max(ASHRAE_COOL_MIN, min(ASHRAE_COOL_MAX, cool))

    # Enforce deadband: cooling >= heating + 2
    if cool - heat < DEADBAND_MIN:
        # Shift cooling up if possible, else shift heating down
        if cool + (DEADBAND_MIN - (cool - heat)) <= ASHRAE_COOL_MAX:
            cool = heat + DEADBAND_MIN
        else:
            heat = cool - DEADBAND_MIN
            heat = max(ASHRAE_HEAT_MIN, heat)

    return {"heating_sp": round(heat, 1), "cooling_sp": round(cool, 1)}