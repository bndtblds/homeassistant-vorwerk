"""Tests for the Vorwerk vacuum platform."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from homeassistant.components.vacuum import StateVacuumEntity, VacuumActivity

from custom_components.vorwerk import VorwerkRobotState
from custom_components.vorwerk.vacuum import VorwerkVacuumEntity


@pytest.mark.parametrize(
    ("state", "expected_activity"),
    [
        ({"state": 1, "details": {"isDocked": True}}, VacuumActivity.DOCKED),
        ({"state": 1, "details": {}}, VacuumActivity.IDLE),
        ({"state": 2, "action": 1, "details": {}}, VacuumActivity.CLEANING),
        ({"state": 3, "details": {}}, VacuumActivity.PAUSED),
        ({"state": 2, "action": 4, "details": {}}, VacuumActivity.RETURNING),
        ({"state": 4, "details": {}}, VacuumActivity.ERROR),
    ],
)
def test_vacuum_activity_and_state(
    coordinator: MagicMock,
    robot_state: VorwerkRobotState,
    state: dict,
    expected_activity: VacuumActivity,
) -> None:
    """Test activity mapping and the state derived by Home Assistant."""
    robot_state.robot_state = state
    entity = VorwerkVacuumEntity(coordinator)

    assert entity.activity is expected_activity
    assert entity.state is expected_activity
    assert "state" not in VorwerkVacuumEntity.__dict__
    assert StateVacuumEntity.state.fget is not None


def test_vacuum_unavailable_data(
    coordinator: MagicMock, robot_state: VorwerkRobotState
) -> None:
    """Test unavailable robot data."""
    entity = VorwerkVacuumEntity(coordinator)

    assert entity.activity is None
    assert entity.state is None
    assert entity.available is False


def test_vacuum_has_no_battery_level(coordinator: MagicMock) -> None:
    """Test that battery data is not duplicated on the vacuum entity."""
    entity = VorwerkVacuumEntity(coordinator)

    assert "battery_level" not in VorwerkVacuumEntity.__dict__
