"""Tests for the Vorwerk config flow."""
from __future__ import annotations

import logging
from unittest.mock import MagicMock, call, patch

import pytest
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_CODE, CONF_EMAIL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pybotvac.exceptions import NeatoException
from pytest_homeassistant_custom_component.common import MockConfigEntry
from requests import HTTPError

from custom_components.vorwerk.config_flow import (
    ROBOT_LIST_FALLBACK_ENDPOINT,
    VorwerkRobotListError,
    VorwerkRobotListResponseError,
    VorwerkSession,
    VorwerkTokenExchangeError,
    VorwerkTokenResponseError,
)
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
            side_effect=VorwerkTokenExchangeError,
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
    flow._session.fetch_robot_list.return_value = [
        {
            "name": "Upstairs",
            "serial": "VR300-1234",
            "secret": "secret",
            "traits": ["maps"],
            "endpoint": "https://example.invalid",
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
    flow._session.validate_token.assert_called_once_with()
    flow._session.fetch_robot_list.assert_called_once_with()


def _robot_payload() -> dict[str, object]:
    """Return a representative robot-list item."""
    return {
        "name": "Upstairs",
        "serial": "VR300-1234",
        "secret_key": "secret",
        "traits": ["maps"],
        "nucleo_url": "https://example.invalid",
    }


def _http_neato_error(status_code: int) -> NeatoException:
    """Return a pybotvac error with a chained HTTP status."""
    http_error = HTTPError(response=MagicMock(status_code=status_code))
    error = NeatoException("private response")
    error.__cause__ = http_error
    return error


@pytest.mark.parametrize("token", [None, {}, {"id_token": None}, {"id_token": ""}])
def test_token_response_is_validated(token: object) -> None:
    """Test that only a non-empty ID token can be used for robot requests."""
    session = VorwerkSession()
    session._token = token

    with pytest.raises(VorwerkTokenResponseError):
        session.validate_token()


def test_valid_id_token_is_accepted() -> None:
    """Test the token type used by pybotvac's Auth0Bearer header."""
    session = VorwerkSession()
    session._token = {"id_token": "not-a-real-token", "access_token": "unused"}

    session.validate_token()


def test_robot_list_falls_back_on_401_and_caches_endpoint(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the compatibility endpoint and its session-level caching."""
    session = VorwerkSession()
    fallback_response = MagicMock()
    fallback_response.json.return_value = {"robots": [_robot_payload()]}
    cached_response = MagicMock()
    cached_response.json.return_value = {"robots": [_robot_payload()]}

    with (
        patch.object(
            session,
            "get",
            side_effect=[
                _http_neato_error(401),
                fallback_response,
                cached_response,
            ],
        ) as get,
        caplog.at_level(logging.DEBUG, logger="custom_components.vorwerk.config_flow"),
    ):
        first = session.fetch_robot_list()
        second = session.fetch_robot_list()

    assert first == second
    assert session._robot_list_endpoint == ROBOT_LIST_FALLBACK_ENDPOINT
    assert get.call_args_list == [
        call("users/me/robots"),
        call("dashboard"),
        call("dashboard"),
    ]
    assert "using the compatibility endpoint for this session" in caplog.text
    assert "private response" not in caplog.text


def test_robot_list_does_not_fall_back_on_other_errors(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that only an HTTP 401 selects the compatibility endpoint."""
    session = VorwerkSession()

    with (
        caplog.at_level(
            logging.DEBUG, logger="custom_components.vorwerk.config_flow"
        ),
        patch.object(session, "get", side_effect=_http_neato_error(503)) as get,
        pytest.raises(NeatoException),
    ):
        session.fetch_robot_list()

    get.assert_called_once_with("users/me/robots")
    warning = next(record for record in caplog.records if record.levelno == logging.WARNING)
    assert warning.message == (
        "Vorwerk robot list request failed (NeatoException, HTTP status 503)"
    )
    assert "private response" not in caplog.text


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"robots": {}},
        {"robots": ["not-a-robot"]},
        {"robots": [{"name": "Missing fields"}]},
    ],
)
def test_dashboard_response_is_validated(payload: object) -> None:
    """Test strict validation of the dashboard response shape."""
    session = VorwerkSession()
    session._robot_list_endpoint = ROBOT_LIST_FALLBACK_ENDPOINT
    response = MagicMock()
    response.json.return_value = payload

    with (
        patch.object(session, "get", return_value=response),
        pytest.raises(VorwerkRobotListResponseError),
    ):
        session.fetch_robot_list()


def test_token_and_robot_list_failures_are_logged_separately(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test privacy-safe diagnostics for the two authentication phases."""
    from custom_components.vorwerk.config_flow import VorwerkConfigFlow

    flow = VorwerkConfigFlow()
    flow._session = MagicMock()
    flow._session.fetch_robot_list.side_effect = _http_neato_error(503)

    with (
        caplog.at_level(logging.DEBUG, logger="custom_components.vorwerk.config_flow"),
        pytest.raises(VorwerkRobotListError),
    ):
        flow._fetch_robots("owner@example.com", "123456")

    assert "Finished Vorwerk OTP token exchange" in caplog.text
    assert "owner@example.com" not in caplog.text
    assert "123456" not in caplog.text
    assert "private response" not in caplog.text
