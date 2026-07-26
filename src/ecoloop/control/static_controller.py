"""Static controller - hardcoded 26°C/18°C test setpoints for wiring verification."""

from src.ecoloop.sim.environment import is_sizing_period
from src.ecoloop.config import COOL_SCHEDULE_NAME, HEAT_SCHEDULE_NAME


def apply_static_test_setpoints(state, api) -> bool:
    """
    Apply hardcoded test setpoints (26°C cooling, 18°C heating) via actuators.

    Returns:
        True if actuators were written, False if skipped (sizing period).
    """
    # Skip during sizing periods (env 1, 2)
    if is_sizing_period(state, api):
        return False

    # Skip during warmup
    if api.exchange.warmup_flag(state):
        return False

    # Get actuator handles for schedule value override
    cool_handle = api.exchange.get_actuator_handle(
        state, "Schedule:Constant", "Schedule Value", COOL_SCHEDULE_NAME)
    heat_handle = api.exchange.get_actuator_handle(
        state, "Schedule:Constant", "Schedule Value", HEAT_SCHEDULE_NAME)

    if cool_handle == -1 or heat_handle == -1:
        return False

    # Hardcoded test values
    api.exchange.set_actuator_value(state, cool_handle, 26.0)
    api.exchange.set_actuator_value(state, heat_handle, 18.0)
    return True