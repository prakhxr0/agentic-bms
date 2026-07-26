"""Regression test for sizing-period guard (current_environment_num < 3)."""

import sys
from unittest.mock import MagicMock, patch

# Add src to path
sys.path.insert(0, "src")

from ecoloop.sim.environment import is_sizing_period


def test_is_sizing_period():
    """Test that env 1 and 2 are recognized as sizing periods."""
    mock_api = MagicMock()

    # env 1 = winter design day
    mock_state = MagicMock()
    mock_api.exchange.current_environment_num.return_value = 1
    assert is_sizing_period(mock_state, mock_api) == True, "Env 1 should be sizing"

    # env 2 = summer design day
    mock_api.exchange.current_environment_num.return_value = 2
    assert is_sizing_period(mock_state, mock_api) == True, "Env 2 should be sizing"

    # env 3 = first weather run period
    mock_api.exchange.current_environment_num.return_value = 3
    assert is_sizing_period(mock_state, mock_api) == False, "Env 3 should be run period"

    # env 4 = second weather run period
    mock_api.exchange.current_environment_num.return_value = 4
    assert is_sizing_period(mock_state, mock_api) == False, "Env 4 should be run period"

    print("All sizing guard tests passed!")


if __name__ == "__main__":
    test_is_sizing_period()