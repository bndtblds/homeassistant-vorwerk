"""Tests for the Vorwerk config flow."""
from __future__ import annotations

from copy import deepcopy
from unittest.mock import MagicMock, patch

import pytest
from homeassistant.config_entries import SOURCE_RECONFIGURE, SOURCE_USER
from homeassistant.const import CONF_CODE, CONF_EMAIL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pybotvac.exceptions import NeatoException
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.vorwerk.const import (
    VORWERK_DOMAIN,
    VORWERK_ROBOT_ENDPOINT,
    VORWERK_ROBOT_NAME,
    VORWERK_ROBOT_SECRET,
    VORWERK_ROBOT_SERIAL,
    VORWERK_ROBOT_TRAITS,
    VORWERK_ROBOTS,
)


async def test_user_step(hass: HomeAssistant) -> None:
    """Test the initial user form."""
    result = await hass.config_entries.flow.async_init(
        VORWERK_DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_email_normalization_and_otp(hass: HomeAssistant) -> None:
    """Test normalized unique ID and one-time OTP sending."""
    with patch(
        "custom_components.vorwerk.config_flow.VorwerkSession.send_email_otp"
    ) as send_otp:
        result = await hass.config_entries.flow.async_init(
            VORWERK_DOMAIN,
            context={"source": SOURCE_USER},
            data={CONF_EMAIL: "  Owner@Example.COM "},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "code"
    send_otp.assert_called_once_with("owner@example.com")
    progress = hass.config_entries.flow.async_progress_by_handler(VORWERK_DOMAIN)
    assert progress[0]["context"]["unique_id"] == "owner@example.com"


async def test_already_configured_email(hass: HomeAssistant) -> None:
    """Test aborting a duplicate normalized email."""
    MockConfigEntry(
        domain=VORWERK_DOMAIN,
        unique_id="owner@example.com",
        title="owner@example.com",
        data={},
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        VORWERK_DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_EMAIL: "OWNER@example.com"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_invalid_code_does_not_resend_otp(hass: HomeAssistant) -> None:
    """Test authentication failure without sending another OTP."""
    with (
        patch(
            "custom_components.vorwerk.config_flow.VorwerkSession.send_email_otp"
        ) as send_otp,
        patch(
            "custom_components.vorwerk.config_flow.VorwerkConfigFlow._fetch_robots",
            side_effect=NeatoException("invalid code"),
        ),
    ):
        code_form = await hass.config_entries.flow.async_init(
            VORWERK_DOMAIN,
            context={"source": SOURCE_USER},
            data={CONF_EMAIL: "owner@example.com"},
        )
        result = await hass.config_entries.flow.async_configure(
            code_form["flow_id"],
            {CONF_CODE: "bad-code"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "code"
    assert result["errors"] == {"base": "invalid_auth"}
    send_otp.assert_called_once_with("owner@example.com")


async def test_successful_login_with_multiple_robots(hass: HomeAssistant) -> None:
    """Test successful login and preservation of robot data."""
    robots = [
        {
            "name": "Upstairs",
            "serial": "VR300-1234",
            "secret": "secret-one",
            "traits": ["maps"],
            "endpoint": "https://one.invalid",
        },
        {
            "name": "Downstairs",
            "serial": "VR200-5678",
            "secret": "secret-two",
            "traits": [],
            "endpoint": "https://two.invalid",
        },
    ]
    with (
        patch(
            "custom_components.vorwerk.config_flow.VorwerkSession.send_email_otp"
        ),
        patch(
            "custom_components.vorwerk.config_flow.VorwerkConfigFlow._fetch_robots",
            return_value=robots,
        ) as fetch_robots,
    ):
        code_form = await hass.config_entries.flow.async_init(
            VORWERK_DOMAIN,
            context={"source": SOURCE_USER},
            data={CONF_EMAIL: "owner@example.com"},
        )
        result = await hass.config_entries.flow.async_configure(
            code_form["flow_id"],
            {CONF_CODE: " 123456 "},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "owner@example.com"
    assert result["data"] == {
        CONF_EMAIL: "owner@example.com",
        VORWERK_ROBOTS: robots,
    }
    fetch_robots.assert_called_once_with("owner@example.com", "123456")


def test_fetch_robots_maps_cloud_response() -> None:
    """Test conversion of Vorwerk cloud robot data."""
    from custom_components.vorwerk.config_flow import VorwerkConfigFlow

    flow = VorwerkConfigFlow()
    flow._session = MagicMock()
    flow._session.get.return_value.json.return_value = [
        {
            "name": "Upstairs",
            "serial": "VR300-1234",
            "secret_key": "secret",
            "traits": ["maps"],
            "nucleo_url": "https://example.invalid",
        }
    ]

    assert flow._fetch_robots("owner@example.com", "123456") == [
        {
            "name": "Upstairs",
            "serial": "VR300-1234",
            "secret": "secret",
            "traits": ["maps"],
            "endpoint": "https://example.invalid",
        }
    ]
    flow._session.fetch_token_passwordless.assert_called_once_with(
        "owner@example.com", "123456"
    )


async def test_reconfigure_requires_confirmation_and_sends_one_otp(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test that reconfiguration fixes the email and explicitly requests one OTP."""
    config_entry.add_to_hass(hass)

    with patch(
        "custom_components.vorwerk.config_flow.VorwerkSession.send_email_otp"
    ) as send_otp:
        confirm_form = await hass.config_entries.flow.async_init(
            VORWERK_DOMAIN,
            context={
                "source": SOURCE_RECONFIGURE,
                "entry_id": config_entry.entry_id,
            },
        )

        assert confirm_form["type"] is FlowResultType.FORM
        assert confirm_form["step_id"] == "reconfigure"
        assert confirm_form["description_placeholders"] == {
            "email": "owner@example.com"
        }
        assert list(confirm_form["data_schema"].schema) == []
        send_otp.assert_not_called()

        code_form = await hass.config_entries.flow.async_configure(
            confirm_form["flow_id"], {}
        )

        assert code_form["type"] is FlowResultType.FORM
        assert code_form["step_id"] == "reconfigure_code"
        assert list(code_form["data_schema"].schema) == [CONF_CODE]
        send_otp.assert_called_once_with("owner@example.com")

        shown_again = await hass.config_entries.flow.async_configure(
            code_form["flow_id"]
        )

    assert shown_again["step_id"] == "reconfigure_code"
    send_otp.assert_called_once_with("owner@example.com")


async def test_reconfigure_invalid_code_can_be_retried_without_new_otp(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test retrying an invalid code without modifying data or resending OTP."""
    config_entry.add_to_hass(hass)
    original_data = deepcopy(dict(config_entry.data))

    with (
        patch(
            "custom_components.vorwerk.config_flow.VorwerkSession.send_email_otp"
        ) as send_otp,
        patch(
            "custom_components.vorwerk.config_flow.VorwerkSession.fetch_token_passwordless",
            side_effect=[NeatoException("expired"), None],
        ) as fetch_token,
        patch(
            "custom_components.vorwerk.config_flow.VorwerkConfigFlow._fetch_authenticated_robots",
            return_value=list(config_entry.data[VORWERK_ROBOTS]),
        ),
        patch.object(hass.config_entries, "async_schedule_reload") as reload_entry,
    ):
        confirm_form = await hass.config_entries.flow.async_init(
            VORWERK_DOMAIN,
            context={
                "source": SOURCE_RECONFIGURE,
                "entry_id": config_entry.entry_id,
            },
        )
        code_form = await hass.config_entries.flow.async_configure(
            confirm_form["flow_id"], {}
        )
        invalid_result = await hass.config_entries.flow.async_configure(
            code_form["flow_id"], {CONF_CODE: "expired"}
        )

        assert invalid_result["type"] is FlowResultType.FORM
        assert invalid_result["errors"] == {"base": "invalid_auth"}
        assert dict(config_entry.data) == original_data
        reload_entry.assert_not_called()

        result = await hass.config_entries.flow.async_configure(
            invalid_result["flow_id"], {CONF_CODE: "new-code"}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert fetch_token.call_args_list[0].args == ("owner@example.com", "expired")
    assert fetch_token.call_args_list[1].args == ("owner@example.com", "new-code")
    send_otp.assert_called_once_with("owner@example.com")
    reload_entry.assert_called_once_with(config_entry.entry_id)


async def test_successful_reconfigure_updates_existing_entry(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test replacing robot information and reloading the existing entry once."""
    config_entry.add_to_hass(hass)
    refreshed_robots = [
        {
            VORWERK_ROBOT_NAME: "Renamed upstairs",
            VORWERK_ROBOT_SERIAL: "VR300-1234",
            VORWERK_ROBOT_SECRET: "renewed-secret",
            VORWERK_ROBOT_TRAITS: ["maps", "zones"],
            VORWERK_ROBOT_ENDPOINT: "https://renewed.invalid",
        },
        {
            VORWERK_ROBOT_NAME: "New robot",
            VORWERK_ROBOT_SERIAL: "VR200-5678",
            VORWERK_ROBOT_SECRET: "new-secret",
            VORWERK_ROBOT_TRAITS: [],
            VORWERK_ROBOT_ENDPOINT: "https://new.invalid",
        },
    ]

    with (
        patch(
            "custom_components.vorwerk.config_flow.VorwerkSession.send_email_otp"
        ),
        patch(
            "custom_components.vorwerk.config_flow.VorwerkSession.fetch_token_passwordless"
        ) as fetch_token,
        patch(
            "custom_components.vorwerk.config_flow.VorwerkConfigFlow._fetch_authenticated_robots",
            return_value=refreshed_robots,
        ) as fetch_robots,
        patch.object(hass.config_entries, "async_schedule_reload") as reload_entry,
    ):
        confirm_form = await hass.config_entries.flow.async_init(
            VORWERK_DOMAIN,
            context={
                "source": SOURCE_RECONFIGURE,
                "entry_id": config_entry.entry_id,
            },
        )
        code_form = await hass.config_entries.flow.async_configure(
            confirm_form["flow_id"], {}
        )
        result = await hass.config_entries.flow.async_configure(
            code_form["flow_id"], {CONF_CODE: " 123456 "}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert len(hass.config_entries.async_entries(VORWERK_DOMAIN)) == 1
    assert config_entry.unique_id == "owner@example.com"
    assert config_entry.data[CONF_EMAIL] == "owner@example.com"
    assert config_entry.data[VORWERK_ROBOTS] == refreshed_robots
    assert CONF_CODE not in config_entry.data
    assert "token" not in config_entry.data
    fetch_token.assert_called_once_with("owner@example.com", "123456")
    fetch_robots.assert_called_once_with()
    reload_entry.assert_called_once_with(config_entry.entry_id)


async def test_reconfigure_otp_request_failure_preserves_entry(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test that an OTP request failure leaves the entry unchanged."""
    config_entry.add_to_hass(hass)
    original_data = deepcopy(dict(config_entry.data))

    with patch(
        "custom_components.vorwerk.config_flow.VorwerkSession.send_email_otp",
        side_effect=NeatoException("unavailable"),
    ) as send_otp:
        confirm_form = await hass.config_entries.flow.async_init(
            VORWERK_DOMAIN,
            context={
                "source": SOURCE_RECONFIGURE,
                "entry_id": config_entry.entry_id,
            },
        )
        result = await hass.config_entries.flow.async_configure(
            confirm_form["flow_id"], {}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {"base": "otp_request_failed"}
    assert dict(config_entry.data) == original_data
    send_otp.assert_called_once_with("owner@example.com")


@pytest.mark.parametrize(
    ("robots", "expected_error"),
    [
        ([], "no_robots"),
        (
            [
                {
                    VORWERK_ROBOT_NAME: "Someone else's robot",
                    VORWERK_ROBOT_SERIAL: "UNRELATED-1",
                    VORWERK_ROBOT_SECRET: "other-secret",
                    VORWERK_ROBOT_TRAITS: [],
                    VORWERK_ROBOT_ENDPOINT: "https://other.invalid",
                }
            ],
            "account_mismatch",
        ),
    ],
)
async def test_reconfigure_rejects_unrelated_or_empty_robot_results(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    robots: list[dict[str, object]],
    expected_error: str,
) -> None:
    """Test that missing matching robots cannot replace the existing entry."""
    config_entry.add_to_hass(hass)
    original_data = deepcopy(dict(config_entry.data))

    with (
        patch(
            "custom_components.vorwerk.config_flow.VorwerkSession.send_email_otp"
        ),
        patch(
            "custom_components.vorwerk.config_flow.VorwerkSession.fetch_token_passwordless"
        ),
        patch(
            "custom_components.vorwerk.config_flow.VorwerkConfigFlow._fetch_authenticated_robots",
            return_value=robots,
        ),
        patch.object(hass.config_entries, "async_schedule_reload") as reload_entry,
    ):
        confirm_form = await hass.config_entries.flow.async_init(
            VORWERK_DOMAIN,
            context={
                "source": SOURCE_RECONFIGURE,
                "entry_id": config_entry.entry_id,
            },
        )
        code_form = await hass.config_entries.flow.async_configure(
            confirm_form["flow_id"], {}
        )
        result = await hass.config_entries.flow.async_configure(
            code_form["flow_id"], {CONF_CODE: "123456"}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}
    assert dict(config_entry.data) == original_data
    reload_entry.assert_not_called()
