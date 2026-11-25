"""Tests for Vorwerk config entry setup and runtime data."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from pybotvac.exceptions import NeatoException, NeatoRobotException
from pytest_homeassistant_custom_component.common import MockConfigEntry
from requests import Timeout

from custom_components.vorwerk import (
    PLATFORMS,
    VorwerkRobotRuntime,
    VorwerkRobotState,
    VorwerkRuntimeData,
    _async_create_robots,
)
from custom_components.vorwerk.const import VORWERK_ROBOTS
from custom_components.vorwerk.coordinator import VorwerkDataUpdateCoordinator


async def test_config_entry_lifecycle(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test setup, runtime data, initial refresh, and unloading."""
    config_entry.add_to_hass(hass)
    robot = MagicMock()
    robot.name = "Upstairs"
    robot.serial = "VR300-1234"
    robot.state = {
        "state": 1,
        "details": {"charge": 80, "isDocked": True},
    }
    robot.get_general_info.return_value.json.return_value = {
        "data": {"model": "VR300", "firmware": "4.6.3"}
    }

    with (
        patch(
            "custom_components.vorwerk._async_create_robots",
            new=AsyncMock(return_value=[robot]),
        ),
        patch.object(
            hass.config_entries,
            "async_forward_entry_setups",
            new=AsyncMock(),
        ) as forward_setups,
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)

    forward_setups.assert_awaited_once_with(config_entry, PLATFORMS)
    assert isinstance(config_entry.runtime_data, VorwerkRuntimeData)
    assert len(config_entry.runtime_data.robots) == 1

    runtime = config_entry.runtime_data.robots[0]
    assert isinstance(runtime, VorwerkRobotRuntime)
    assert runtime.state.robot is robot
    assert runtime.coordinator.data is runtime.state
    assert runtime.coordinator.last_update_success
    assert runtime.state.robot_info == {"model": "VR300", "firmware": "4.6.3"}
    assert config_entry.state is ConfigEntryState.LOADED

    with patch.object(
        hass.config_entries,
        "async_unload_platforms",
        new=AsyncMock(return_value=True),
    ) as unload_platforms:
        assert await hass.config_entries.async_unload(config_entry.entry_id)
    unload_platforms.assert_awaited_once_with(config_entry, PLATFORMS)
    assert config_entry.state is ConfigEntryState.NOT_LOADED


async def test_robot_initialization_failure_is_isolated(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test that an unavailable robot is retained for later retries."""
    robot_configs = [
        config_entry.data[VORWERK_ROBOTS][0],
        {
            **config_entry.data[VORWERK_ROBOTS][0],
            "name": "Downstairs",
            "serial": "VR300-5678",
        },
    ]
    response = MagicMock()
    response.json.return_value = {"availableServices": {"houseCleaning": "basic-3"}}

    with patch(
        "pybotvac.robot.Robot.get_robot_state",
        side_effect=[NeatoRobotException("HTTP 404"), response],
    ):
        robots = await _async_create_robots(hass, robot_configs)

    assert [robot.serial for robot in robots] == ["VR300-1234", "VR300-5678"]


async def test_robot_initialization_timeout_is_isolated(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test that a request timeout does not abort robot creation."""
    with patch("pybotvac.robot.Robot.get_robot_state", side_effect=Timeout):
        robots = await _async_create_robots(
            hass, config_entry.data[VORWERK_ROBOTS]
        )

    assert len(robots) == 1
    assert robots[0].serial == "VR300-1234"


async def test_account_error_still_defers_config_entry(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test that a non-robot account error remains config-entry-wide."""
    with (
        patch("pybotvac.robot.Robot.__init__", side_effect=NeatoException("auth")),
        pytest.raises(ConfigEntryNotReady, match="Unable to connect"),
    ):
        await _async_create_robots(hass, config_entry.data[VORWERK_ROBOTS])


async def test_setup_keeps_available_robot_running(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test that one failed initial refresh does not block another robot."""
    available = MagicMock(name="available")
    available.name = "Upstairs"
    available.serial = "VR300-1234"
    available.state = {"state": 1, "details": {}}
    available.get_general_info.return_value.json.return_value = {"data": {}}

    unavailable = MagicMock(name="unavailable")
    unavailable.name = "Downstairs"
    unavailable.serial = "VR300-5678"
    type(unavailable).state = PropertyMock(side_effect=NeatoRobotException("HTTP 404"))
    unavailable.get_general_info.side_effect = NeatoRobotException("offline")
    config_entry.add_to_hass(hass)

    with (
        patch(
            "custom_components.vorwerk._async_create_robots",
            new=AsyncMock(return_value=[available, unavailable]),
        ),
        patch.object(
            hass.config_entries, "async_forward_entry_setups", new=AsyncMock()
        ),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)

    assert config_entry.state is ConfigEntryState.LOADED
    first, second = config_entry.runtime_data.robots
    assert first.coordinator.last_update_success
    assert first.state.available
    assert not second.coordinator.last_update_success
    assert not second.state.available


async def test_slow_robot_does_not_block_other_update(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test that per-robot coordinator refreshes execute concurrently."""
    slow_robot = MagicMock()
    slow_robot.serial = "slow"
    slow_state = VorwerkRobotState(slow_robot)
    fast_robot = MagicMock()
    fast_robot.serial = "fast"
    fast_state = VorwerkRobotState(fast_robot)
    slow = VorwerkDataUpdateCoordinator(hass, config_entry, slow_state)
    fast = VorwerkDataUpdateCoordinator(hass, config_entry, fast_state)
    release = asyncio.Event()
    fast_finished = asyncio.Event()

    async def slow_update() -> VorwerkRobotState:
        await release.wait()
        return slow_state

    async def fast_update() -> VorwerkRobotState:
        fast_finished.set()
        return fast_state

    with (
        patch.object(slow, "_async_update_data", side_effect=slow_update),
        patch.object(fast, "_async_update_data", side_effect=fast_update),
    ):
        refreshes = asyncio.gather(slow.async_refresh(), fast.async_refresh())
        await fast_finished.wait()
        assert not refreshes.done()
        assert fast.last_update_success
        release.set()
        await refreshes


def test_device_info(robot: MagicMock) -> None:
    """Test stable device information."""
    from custom_components.vorwerk import VorwerkRobotState

    robot_state = VorwerkRobotState(robot)
    robot_state.robot_info = {"model": "VR300", "firmware": "4.6.3"}

    assert robot_state.device_info == {
        "identifiers": {("vorwerk", "VR300-1234")},
        "manufacturer": "Vorwerk",
        "model": "VR300",
        "name": "Upstairs",
        "sw_version": "4.6.3",
    }
