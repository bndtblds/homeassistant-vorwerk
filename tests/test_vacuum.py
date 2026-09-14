"""Tests for the Vorwerk vacuum platform."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from homeassistant.components.vacuum import StateVacuumEntity, VacuumActivity

from custom_components.vorwerk import VorwerkRobotState
from custom_components.vorwerk.const import (
    ROBOT_ACTION_DOCKING,
    ROBOT_ACTION_EXPLORING_MAP,
    ROBOT_ACTION_HOUSE_CLEANING,
    ROBOT_ACTION_MANUAL_CLEANING,
    ROBOT_ACTION_MAP_CLEANING,
    ROBOT_ACTION_SPOT_CLEANING,
    ROBOT_ACTION_SUSPENDED_CLEANING,
    ROBOT_ACTION_SUSPENDED_EXPLORATION,
    ROBOT_STATE_BUSY,
    ROBOT_STATE_ERROR,
    ROBOT_STATE_IDLE,
    ROBOT_STATE_PAUSE,
)
from custom_components.vorwerk.vacuum import VorwerkVacuumEntity


@pytest.mark.parametrize(
    ("state", "expected_activity"),
    [
        (
            {"state": ROBOT_STATE_IDLE, "details": {"isDocked": True}},
            VacuumActivity.DOCKED,
        ),
        (
            {"state": ROBOT_STATE_IDLE, "details": {"isCharging": True}},
            VacuumActivity.DOCKED,
        ),
        ({"state": ROBOT_STATE_IDLE, "details": {}}, VacuumActivity.IDLE),
        (
            {
                "state": ROBOT_STATE_BUSY,
                "action": ROBOT_ACTION_HOUSE_CLEANING,
                "details": {},
            },
            VacuumActivity.CLEANING,
        ),
        (
            {
                "state": ROBOT_STATE_BUSY,
                "action": ROBOT_ACTION_SPOT_CLEANING,
                "details": {},
            },
            VacuumActivity.CLEANING,
        ),
        (
            {
                "state": ROBOT_STATE_BUSY,
                "action": ROBOT_ACTION_MANUAL_CLEANING,
                "details": {},
            },
            VacuumActivity.CLEANING,
        ),
        (
            {
                "state": ROBOT_STATE_BUSY,
                "action": ROBOT_ACTION_MAP_CLEANING,
                "details": {},
            },
            VacuumActivity.CLEANING,
        ),
        (
            {
                "state": ROBOT_STATE_BUSY,
                "action": ROBOT_ACTION_EXPLORING_MAP,
                "details": {},
            },
            VacuumActivity.CLEANING,
        ),
        (
            {
                "state": ROBOT_STATE_BUSY,
                "action": ROBOT_ACTION_SUSPENDED_CLEANING,
                "details": {},
            },
            VacuumActivity.PAUSED,
        ),
        (
            {
                "state": ROBOT_STATE_BUSY,
                "action": ROBOT_ACTION_SUSPENDED_EXPLORATION,
                "details": {},
            },
            VacuumActivity.PAUSED,
        ),
        (
            {
                "state": ROBOT_STATE_BUSY,
                "action": ROBOT_ACTION_DOCKING,
                "details": {},
            },
            VacuumActivity.RETURNING,
        ),
        ({"state": ROBOT_STATE_PAUSE, "details": {}}, VacuumActivity.PAUSED),
        ({"state": ROBOT_STATE_ERROR, "details": {}}, VacuumActivity.ERROR),
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
    assert "battery_level" not in VorwerkVacuumEntity.__dict__
