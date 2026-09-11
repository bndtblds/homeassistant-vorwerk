"""Tests for the Vorwerk custom cleaning service."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import voluptuous as vol

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from custom_components.vorwerk import CUSTOM_CLEANING_SCHEMA, async_setup
from custom_components.vorwerk.vacuum import VorwerkVacuumEntity


async def test_service_registration(hass: HomeAssistant) -> None:
    """Test vacuum-targeted entity service registration."""
    with patch(
        "custom_components.vorwerk.service.async_register_platform_entity_service"
    ) as register:
        assert await async_setup(hass, {})

    register.assert_called_once()
    assert register.call_args.args[:3] == (hass, "vorwerk", "custom_cleaning")
    assert register.call_args.kwargs["entity_domain"] == "vacuum"
    assert register.call_args.kwargs["func"] == "async_custom_cleaning"


def test_service_schema_defaults_and_optional_zone() -> None:
    """Test custom cleaning defaults and optional zone."""
    assert CUSTOM_CLEANING_SCHEMA({"entity_id": "vacuum.upstairs"}) == {
        "entity_id": ["vacuum.upstairs"],
        "mode": 2,
        "navigation": 1,
        "category": 4,
    }
    assert (
        CUSTOM_CLEANING_SCHEMA(
            {"entity_id": "vacuum.upstairs", "zone": "Kitchen"}
        )["zone"]
        == "Kitchen"
    )


@pytest.mark.parametrize(
    "data",
    [
        {"mode": 3},
        {"navigation": 4},
        {"category": 3},
    ],
)
def test_service_schema_rejects_invalid_values(data: dict) -> None:
    """Test validation of custom cleaning parameters."""
    with pytest.raises(vol.Invalid):
        CUSTOM_CLEANING_SCHEMA({"entity_id": "vacuum.upstairs", **data})


async def test_custom_cleaning_without_zone(coordinator: MagicMock) -> None:
    """Test custom cleaning without loading boundaries."""
    entity = VorwerkVacuumEntity(coordinator)
    entity._async_call_robot_command = AsyncMock()
    entity._async_ensure_boundaries_loaded = AsyncMock()

    await entity.async_custom_cleaning(1, 2, 4)

    entity._async_ensure_boundaries_loaded.assert_not_awaited()
    entity._async_call_robot_command.assert_awaited_once_with(
        entity.robot.start_cleaning,
        1,
        2,
        4,
        None,
    )


async def test_boundary_lookup_is_case_insensitive_and_cached(
    hass: HomeAssistant, coordinator: MagicMock
) -> None:
    """Test boundary lookup, executor use, and caching."""
    entity = VorwerkVacuumEntity(coordinator)
    entity.hass = hass
    entity.robot.get_map_boundaries.return_value.json.return_value = {
        "data": {
            "boundaries": [
                {"id": "zone-1", "name": "Living Room"},
                {"id": "zone-2", "name": "Kitchen"},
            ]
        }
    }
    entity._async_call_robot_command = AsyncMock()
    completed = hass.loop.create_future()
    completed.set_result(entity._load_map_boundaries())

    with patch.object(
        hass,
        "async_add_executor_job",
        return_value=completed,
    ) as executor_job:
        await entity.async_custom_cleaning(2, 1, 4, "LIVING")
        assert await entity._async_resolve_boundary_id("kitchen") == "zone-2"

    executor_job.assert_called_once_with(entity._load_map_boundaries)
    entity._async_call_robot_command.assert_awaited_once_with(
        entity.robot.start_cleaning,
        2,
        1,
        4,
        "zone-1",
    )


async def test_unknown_zone_lists_available_zones(
    hass: HomeAssistant, coordinator: MagicMock
) -> None:
    """Test an unknown named zone."""
    entity = VorwerkVacuumEntity(coordinator)
    entity.hass = hass
    entity._robot_boundaries = [{"id": "zone-1", "name": "Kitchen"}]
    entity._boundaries_loaded = True

    with pytest.raises(ServiceValidationError) as error:
        await entity._async_resolve_boundary_id("Garage")

    assert error.value.translation_key == "zone_not_found"
    assert error.value.translation_placeholders["available_zones"] == "Kitchen"


async def test_no_boundaries(hass: HomeAssistant, coordinator: MagicMock) -> None:
    """Test a robot without map boundaries."""
    entity = VorwerkVacuumEntity(coordinator)
    entity.hass = hass
    entity._boundaries_loaded = True

    with pytest.raises(ServiceValidationError) as error:
        await entity._async_resolve_boundary_id("Kitchen")

    assert error.value.translation_key == "no_map_boundaries"


async def test_boundary_timeout(
    hass: HomeAssistant, coordinator: MagicMock
) -> None:
    """Test a timeout while loading map boundaries."""
    entity = VorwerkVacuumEntity(coordinator)
    entity.hass = hass
    pending = hass.loop.create_future()

    with (
        patch.object(hass, "async_add_executor_job", return_value=pending),
        patch("custom_components.vorwerk.vacuum.ROBOT_API_TIMEOUT", 0.01),
        pytest.raises(HomeAssistantError) as error,
    ):
        await entity._async_ensure_boundaries_loaded()

    assert error.value.translation_key == "load_map_boundaries_failed"


async def test_custom_cleaning_command_error(coordinator: MagicMock) -> None:
    """Test propagation of a robot command error."""
    entity = VorwerkVacuumEntity(coordinator)
    entity._async_call_robot_command = AsyncMock(
        side_effect=HomeAssistantError("command failed")
    )

    with pytest.raises(HomeAssistantError, match="command failed"):
        await entity.async_custom_cleaning(2, 1, 4)
