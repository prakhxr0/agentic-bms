import logging

# ASHRAE Standard 55 - recommended bounds for occupied spaces
MIN_HEATING_SP = 18.0  # °C
MAX_HEATING_SP = 24.0  # °C (relaxed to give LLM headroom to reach PMV 0)
MIN_COOLING_SP = 22.0  # °C
MAX_COOLING_SP = 28.0  # °C (relaxed to maintain deadband with MAX_HEATING_SP)

def clamp_setpoints(zone_id: str, proposed: dict) -> dict:
    """
    Enforce hard comfort/safety bounds on setpoints.
    proposed = {'heating_sp': float, 'cooling_sp': float}
    Returns clamped dict and logs any adjustments.
    """
    clamped = proposed.copy()
    
    # Cooling setpoint must always be >= heating setpoint (deadband)
    if clamped['cooling_sp'] < clamped['heating_sp'] + 2.0:
        logging.warning(f"{zone_id}: Deadband violation. Adjusting.")
        clamped['cooling_sp'] = clamped['heating_sp'] + 2.0
    
    # Clamp individual values
    if clamped['heating_sp'] < MIN_HEATING_SP:
        clamped['heating_sp'] = MIN_HEATING_SP
    if clamped['heating_sp'] > MAX_HEATING_SP:
        clamped['heating_sp'] = MAX_HEATING_SP
    if clamped['cooling_sp'] < MIN_COOLING_SP:
        clamped['cooling_sp'] = MIN_COOLING_SP
    if clamped['cooling_sp'] > MAX_COOLING_SP:
        clamped['cooling_sp'] = MAX_COOLING_SP
        
    return clamped