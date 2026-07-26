"""EnergyPlus environment/sizing helpers."""

def is_sizing_period(state, api) -> bool:
    """
    Return True if currently in a sizing/design-day environment.
    EnergyPlus environment numbering:
    - 1 = Winter design day
    - 2 = Summer design day
    - >=3 = Weather file run periods
    """
    env_num = api.exchange.current_environment_num(state)
    return env_num < 3


def is_weather_run_period(state, api) -> bool:
    """Return True if in a weather-file run period (not sizing)."""
    return not is_sizing_period(state, api)