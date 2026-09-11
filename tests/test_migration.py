"""Tests for Vorwerk entity registry migrations."""
from __future__ import annotations

from unittest.mock import MagicMock

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.vorwerk import (
    _async_migrate_schedule_switch_entities,
    _async_reset_entity_display_names,
)


def create_entry(
    registry: er.EntityRegistry,
    config_entry: MockConfigEntry,
    domain: str,
    unique_id: str,
    *,
    name: str | None = None,
) -> er.RegistryEntry:
    """Create an entity registry entry."""
    entry = registry.async_get_or_create(
        domain,
        "vorwerk",
        unique_id,
        config_entry=config_entry,
        suggested_object_id="upstairs",
    )
    if name is not None:
        entry = registry.async_update_entity(entry.entity_id, name=name)
    return entry


async def test_migrate_legacy_schedule_unique_id(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    robot: MagicMock,
) -> None:
    """Test migration of the legacy schedule unique ID and entity ID."""
    config_entry.add_to_hass(hass)
    registry = er.async_get(hass)
    legacy = create_entry(
        registry,
        config_entry,
        "switch",
        "VR300-1234",
        name="Upstairs Schedule",
    )

    await _async_migrate_schedule_switch_entities(
        hass, config_entry, [robot]
    )
    await _async_reset_entity_display_names(hass, config_entry, [robot])

    migrated = registry.async_get(legacy.entity_id + "_schedule")
    assert migrated is not None
    assert migrated.unique_id == "VR300-1234_schedule"
    assert migrated.name is None
    assert registry.async_get(legacy.entity_id) is None


async def test_current_schedule_entry_is_preserved(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    robot: MagicMock,
) -> None:
    """Test that an existing current schedule entry remains the same entry."""
    config_entry.add_to_hass(hass)
    registry = er.async_get(hass)
    current = create_entry(
        registry,
        config_entry,
        "switch",
        "VR300-1234_schedule",
        name="My timetable",
    )

    await _async_migrate_schedule_switch_entities(hass, config_entry, [robot])

    preserved = registry.async_get(current.entity_id + "_schedule")
    assert preserved is not None
    assert preserved.id == current.id
    assert preserved.unique_id == "VR300-1234_schedule"
    assert preserved.name == "My timetable"


async def test_legacy_duplicate_is_removed(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    robot: MagicMock,
) -> None:
    """Test removal of a true legacy duplicate in favor of the current entry."""
    config_entry.add_to_hass(hass)
    registry = er.async_get(hass)
    legacy = create_entry(registry, config_entry, "switch", "VR300-1234")
    current = create_entry(
        registry,
        config_entry,
        "switch",
        "VR300-1234_schedule",
    )

    await _async_migrate_schedule_switch_entities(hass, config_entry, [robot])

    assert registry.async_get(legacy.entity_id) is None
    assert registry.async_get_entity_id(
        "switch", "vorwerk", "VR300-1234_schedule"
    ) is not None
    assert registry.async_get(current.entity_id + "_schedule") is not None


async def test_reset_only_legacy_display_names(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    robot: MagicMock,
) -> None:
    """Test legacy name reset while preserving user-defined names."""
    config_entry.add_to_hass(hass)
    registry = er.async_get(hass)
    schedule = create_entry(
        registry,
        config_entry,
        "switch",
        "VR300-1234_schedule",
        name="Upstairs Zeitplan",
    )
    battery = create_entry(
        registry,
        config_entry,
        "sensor",
        "VR300-1234_battery",
        name="Upstairs Battery",
    )
    custom = create_entry(
        registry,
        config_entry,
        "sensor",
        "VR300-1234_custom",
        name="Keep this name",
    )

    await _async_reset_entity_display_names(hass, config_entry, [robot])

    assert registry.async_get(schedule.entity_id).name is None
    assert registry.async_get(battery.entity_id).name is None
    assert registry.async_get(custom.entity_id).name == "Keep this name"


async def test_custom_schedule_and_battery_names_are_preserved(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    robot: MagicMock,
) -> None:
    """Test protection of user-defined entity names."""
    config_entry.add_to_hass(hass)
    registry = er.async_get(hass)
    schedule = create_entry(
        registry,
        config_entry,
        "switch",
        "VR300-1234_schedule",
        name="Weekday plan",
    )
    battery = create_entry(
        registry,
        config_entry,
        "sensor",
        "VR300-1234_battery",
        name="Charge upstairs",
    )

    await _async_reset_entity_display_names(hass, config_entry, [robot])

    assert registry.async_get(schedule.entity_id).name == "Weekday plan"
    assert registry.async_get(battery.entity_id).name == "Charge upstairs"
