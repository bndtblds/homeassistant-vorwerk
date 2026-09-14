"""Tests for Vorwerk robot state normalization and platform setup."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from homeassistant.components.vacuum import VacuumActivity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from pybotvac.exceptions import NeatoException, NeatoRobotException
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.vorwerk import (
    VorwerkRobotRuntime,
    VorwerkRobotState,
    VorwerkRuntimeData,
    _async_create_robots,
)
from custom_components.vorwerk.const import (
    ROBOT_ACTION_SUSPENDED_CLEANING,
    ROBOT_STATE_BUSY,
)
from custom_components.vorwerk.coordinator import VorwerkDataUpdateCoordinator
from custom_components.vorwerk.sensor import async_setup_entry as setup_sensor
from custom_components.vorwerk.switch import (
    VorwerkScheduleSwitch,
)
from custom_components.vorwerk.switch import (
    async_setup_entry as setup_switch,
)
from custom_components.vorwerk.vacuum import (
    VorwerkVacuumEntity,
)
from custom_components.vorwerk.vacuum import (
    async_setup_entry as setup_vacuum,
)


def test_robot_state_update_and_static_info_cache(
    robot: MagicMock, robot_state: VorwerkRobotState
) -> None:
    """Test state updates and one-time static information retrieval."""
    robot.get_general_info.return_value.json.return_value = {
        "data": {"model": "VR300", "firmware": "4.6.3"}
    }
    robot.state = {"state": 1, "details": {"charge": 80}}

    robot_state.update()
    robot_state.update()

    assert robot_state.robot_info == {"model": "VR300", "firmware": "4.6.3"}
    assert robot_state.robot_state == robot.state
    robot.get_general_info.assert_called_once_with()


def test_robot_info_and_state_error_handling(
    robot: MagicMock, robot_state: VorwerkRobotState
) -> None:
    """Test pybotvac errors while retrieving robot data."""
    robot.get_general_info.side_effect = NeatoRobotException("info unavailable")
    robot.state = {"state": 1}
    robot_state.update()
    assert robot_state.robot_info == {}

    type(robot).state = property(
        lambda self: (_ for _ in ()).throw(NeatoRobotException("offline"))
    )
    with pytest.raises(NeatoRobotException):
        robot_state._update_robot_state()
    assert robot_state.robot_state == {}


def test_non_mapping_robot_data_is_ignored(
    robot: MagicMock, robot_state: VorwerkRobotState
) -> None:
    """Test malformed pybotvac responses."""
    robot.get_general_info.return_value.json.return_value = {"data": []}
    robot.state = "invalid"

    robot_state.update()

    assert robot_state.robot_info == {}
    assert robot_state.robot_state == {}


@pytest.mark.parametrize(
    ("state", "expected_status"),
    [
        ({}, None),
        ({"state": 1, "details": {"isCharging": True}}, "Charging"),
        ({"state": 1, "details": {"isDocked": True}}, "Docked"),
        ({"state": 1, "details": {}}, "Stopped"),
        ({"state": 3, "details": {}}, "Paused"),
        ({"state": 2, "action": 4, "details": {}}, "Returning"),
        ({"state": 4, "error": "maint_brush_stuck", "details": {}}, "Brush stuck"),
        ({"state": 4, "error": "new_error", "details": {}}, "new_error"),
        ({"state": 4, "details": {}}, None),
        (
            {"state": 1, "alert": "ui_alert_dust_bin_full", "details": {}},
            "Please empty dust bin",
        ),
        ({"state": 1, "alert": "new_alert", "details": {}}, "new_alert"),
        (
            {
                "state": 2,
                "action": 11,
                "details": {},
                "cleaning": {"mode": 1, "boundary": {"name": "Kitchen"}},
            },
            "Eco Map cleaning Kitchen",
        ),
        ({"state": 99, "details": {}}, None),
    ],
)
def test_robot_status(
    robot_state: VorwerkRobotState,
    state: dict,
    expected_status: str | None,
) -> None:
    """Test human-readable robot status generation."""
    robot_state.robot_state = state
    assert robot_state.status == expected_status


def test_robot_optional_properties(robot_state: VorwerkRobotState) -> None:
    """Test unavailable and available optional robot properties."""
    assert robot_state.docked is None
    assert robot_state.charging is None
    assert robot_state.alert is None
    assert robot_state.schedule_enabled is None

    robot_state.robot_state = {
        "state": 1,
        "details": {"isScheduleEnabled": True},
    }
    assert robot_state.docked is False
    assert robot_state.charging is False
    assert robot_state.alert is None
    assert robot_state.schedule_enabled is True


@pytest.mark.parametrize("setup", [setup_vacuum, setup_sensor, setup_switch])
async def test_platform_setup(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    robot_state: VorwerkRobotState,
    setup,
) -> None:
    """Test creation of one entity on each platform."""
    coordinator = MagicMock(spec=VorwerkDataUpdateCoordinator)
    coordinator.robot_state = robot_state
    config_entry.runtime_data = VorwerkRuntimeData(
        robots=[VorwerkRobotRuntime(state=robot_state, coordinator=coordinator)]
    )
    add_entities = MagicMock()

    await setup(hass, config_entry, add_entities)

    entities = add_entities.call_args.args[0]
    assert len(entities) == 1
    assert entities[0].unique_id in {
        "VR300-1234",
        "VR300-1234_battery",
        "VR300-1234_schedule",
    }


def test_schedule_switch_state(
    coordinator: MagicMock, robot_state: VorwerkRobotState
) -> None:
    """Test schedule switch state conversion."""
    entity = VorwerkScheduleSwitch(coordinator)
    assert entity.is_on is False
    robot_state.robot_state = {
        "state": 1,
        "details": {"isScheduleEnabled": True},
    }
    assert entity.is_on is True


def test_vacuum_status_attribute(
    coordinator: MagicMock, robot_state: VorwerkRobotState
) -> None:
    """Test optional vacuum status attributes."""
    entity = VorwerkVacuumEntity(coordinator)
    assert entity.extra_state_attributes == {}
    robot_state.robot_state = {"state": 3, "details": {}}
    assert entity.extra_state_attributes == {"status": "Paused"}


@pytest.mark.parametrize("charge", [1, 99])
def test_vr200_suspended_cleaning_status_is_independent_of_charge(
    coordinator: MagicMock,
    robot_state: VorwerkRobotState,
    charge: int,
) -> None:
    """Test the observed VR200 suspended-cleaning state and detail status."""
    robot_state.robot.serial = "VR200-1234"
    robot_state.robot_state = {
        "state": ROBOT_STATE_BUSY,
        "action": ROBOT_ACTION_SUSPENDED_CLEANING,
        "cleaning": {"mode": 2},
        "details": {
            "charge": charge,
            "isDocked": False,
            "isCharging": False,
        },
    }
    entity = VorwerkVacuumEntity(coordinator)

    assert entity.activity is VacuumActivity.PAUSED
    assert entity.extra_state_attributes == {"status": "Turbo Suspended Cleaning"}


async def test_create_robot_error(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test conversion of robot creation errors."""
    failed = hass.loop.create_future()
    failed.set_exception(NeatoException("offline"))
    with (
        patch.object(hass, "async_add_executor_job", return_value=failed),
        pytest.raises(ConfigEntryNotReady, match="Unable to connect"),
    ):
        await _async_create_robots(hass, config_entry.data["robots"])


async def test_boundary_load_error_and_malformed_response(
    hass: HomeAssistant, coordinator: MagicMock
) -> None:
    """Test boundary API error and malformed boundary data."""
    entity = VorwerkVacuumEntity(coordinator)
    entity.hass = hass
    failed = hass.loop.create_future()
    failed.set_exception(RuntimeError("offline"))
    with (
        patch.object(hass, "async_add_executor_job", return_value=failed),
        pytest.raises(HomeAssistantError),
    ):
        await entity._async_ensure_boundaries_loaded()

    entity.robot.get_map_boundaries.return_value.json.return_value = {
        "data": {"boundaries": "invalid"}
    }
    assert entity._load_map_boundaries() == []


def test_cancelled_update_future_callback(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    robot_state: VorwerkRobotState,
) -> None:
    """Test cleanup of a cancelled executor future."""
    coordinator = VorwerkDataUpdateCoordinator(
        hass, config_entry=config_entry, robot_state=robot_state
    )
    future = hass.loop.create_future()
    coordinator._update_future = future
    future.cancel()

    coordinator._async_clear_update_future(future)

    assert coordinator._update_future is None
