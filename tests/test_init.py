"""Tests for Vorwerk config entry setup and runtime data."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.vorwerk import (
    PLATFORMS,
    VorwerkRobotRuntime,
    VorwerkRuntimeData,
)


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
        patch("custom_components.vorwerk.Robot", return_value=robot) as robot_class,
        patch.object(
            hass.config_entries,
            "async_forward_entry_setups",
            new=AsyncMock(),
        ) as forward_setups,
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)

    robot_class.assert_called_once_with(
        serial="VR300-1234",
        secret="not-a-real-secret",
        traits=["maps"],
        vendor=robot_class.call_args.kwargs["vendor"],
        name="Upstairs",
        endpoint="https://example.invalid",
    )
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
