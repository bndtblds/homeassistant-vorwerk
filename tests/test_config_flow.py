"""Tests for the Vorwerk config flow."""
from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

import pytest
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_CODE, CONF_EMAIL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pybotvac.exceptions import NeatoException
from pytest_homeassistant_custom_component.common import MockConfigEntry
from requests import HTTPError

from custom_components.vorwerk.const import VORWERK_DOMAIN, VORWERK_ROBOTS


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


def test_fetch_robots_logs_token_exchange_failure_safely(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that token failures identify the step without exposing credentials."""
    from custom_components.vorwerk.config_flow import VorwerkConfigFlow

    flow = VorwerkConfigFlow()
    flow._session = MagicMock()
    response = MagicMock(status_code=403)
    flow._session.fetch_token_passwordless.side_effect = HTTPError(
        "response containing sensitive details",
        response=response,
    )

    with (
        caplog.at_level(logging.DEBUG, logger="custom_components.vorwerk.config_flow"),
        pytest.raises(HTTPError),
    ):
        flow._fetch_robots("owner@example.com", "123456")

    assert "Vorwerk OTP token exchange failed" in caplog.text
    assert "HTTPError, HTTP status 403" in caplog.text
    assert "owner@example.com" not in caplog.text
    assert "123456" not in caplog.text
    assert "sensitive details" not in caplog.text
    flow._session.get.assert_not_called()


def test_fetch_robots_logs_robot_list_failure_safely(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that robot-list failures are distinct from rejected OTP codes."""
    from custom_components.vorwerk.config_flow import VorwerkConfigFlow

    flow = VorwerkConfigFlow()
    flow._session = MagicMock()
    response = MagicMock(status_code=503)
    http_error = HTTPError("private response", response=response)
    neato_error = NeatoException("generic cloud error")
    neato_error.__cause__ = http_error
    flow._session.get.side_effect = neato_error

    with (
        caplog.at_level(logging.DEBUG, logger="custom_components.vorwerk.config_flow"),
        pytest.raises(NeatoException),
    ):
        flow._fetch_robots("owner@example.com", "123456")

    assert "Finished Vorwerk OTP token exchange" in caplog.text
    assert "Vorwerk robot list request failed" in caplog.text
    assert "NeatoException, HTTP status 503" in caplog.text
    assert "owner@example.com" not in caplog.text
    assert "123456" not in caplog.text
    assert "private response" not in caplog.text


def test_fetch_robots_logs_response_validation_failure_safely(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that malformed robot data identifies the validation step only."""
    from custom_components.vorwerk.config_flow import VorwerkConfigFlow

    flow = VorwerkConfigFlow()
    flow._session = MagicMock()
    flow._session.get.return_value.json.return_value = [
        {"name": "Private robot name"}
    ]

    with (
        caplog.at_level(logging.DEBUG, logger="custom_components.vorwerk.config_flow"),
        pytest.raises(KeyError, match="serial"),
    ):
        flow._fetch_robots("owner@example.com", "123456")

    assert "Vorwerk robot list validation failed" in caplog.text
    assert "KeyError" in caplog.text
    assert "Private robot name" not in caplog.text
    assert "owner@example.com" not in caplog.text
    assert "123456" not in caplog.text
