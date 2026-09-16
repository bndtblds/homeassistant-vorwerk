"""Config flow for the Vorwerk Kobold integration."""
from __future__ import annotations

import logging
import warnings
from typing import Any

with warnings.catch_warnings():
    warnings.filterwarnings(
        "ignore",
        message="pkg_resources is deprecated as an API.*",
        category=UserWarning,
    )
    import pybotvac
    from pybotvac.exceptions import NeatoException

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_CODE, CONF_EMAIL
from homeassistant.data_entry_flow import FlowResult
from requests import HTTPError

from .const import (
    VORWERK_CLIENT_ID,
    VORWERK_DOMAIN,
    VORWERK_ROBOT_ENDPOINT,
    VORWERK_ROBOT_NAME,
    VORWERK_ROBOT_SECRET,
    VORWERK_ROBOT_SERIAL,
    VORWERK_ROBOT_TRAITS,
    VORWERK_ROBOTS,
)
from .diagnostics import timed_cloud_call

_LOGGER = logging.getLogger(__name__)

DOCUMENTATION_URL = "https://github.com/bndtblds/homeassistant-vorwerk"

STEP_USER_SCHEMA = vol.Schema({vol.Required(CONF_EMAIL): str})
STEP_CODE_SCHEMA = vol.Schema({vol.Required(CONF_CODE): str})


class VorwerkConfigFlow(config_entries.ConfigFlow, domain=VORWERK_DOMAIN):
    """Handle a config flow for Vorwerk."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._email: str | None = None
        self._session = VorwerkSession()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is not None:
            self._email = user_input[CONF_EMAIL].strip().lower()
            await self.async_set_unique_id(self._email)
            self._abort_if_unique_id_configured()
            return await self.async_step_code()

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_SCHEMA,
            description_placeholders={"docs_url": DOCUMENTATION_URL},
        )

    async def async_step_code(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the OTP code step."""
        assert self._email is not None

        errors: dict[str, str] = {}
        if user_input is None:
            await self.hass.async_add_executor_job(
                self._send_email_otp,
                self._email,
            )
        else:
            code = user_input[CONF_CODE].strip()
            try:
                robots = await self.hass.async_add_executor_job(
                    self._fetch_robots,
                    self._email,
                    code,
                )
            except (HTTPError, NeatoException):
                errors["base"] = "invalid_auth"
            else:
                return self.async_create_entry(
                    title=self._email,
                    data={CONF_EMAIL: self._email, VORWERK_ROBOTS: robots},
                )

        return self.async_show_form(
            step_id="code",
            data_schema=STEP_CODE_SCHEMA,
            description_placeholders={"docs_url": DOCUMENTATION_URL},
            errors=errors,
        )

    def _fetch_robots(self, email: str, code: str) -> list[dict[str, Any]]:
        """Fetch robots available for the authenticated account."""
        timed_cloud_call(
            _LOGGER,
            "OTP token exchange",
            self._session.fetch_token_passwordless,
            email,
            code,
        )
        response = timed_cloud_call(
            _LOGGER,
            "robot list request",
            self._session.get,
            "users/me/robots",
        )
        return timed_cloud_call(
            _LOGGER,
            "robot list validation",
            self._robots_from_response,
            response,
        )

    def _send_email_otp(self, email: str) -> None:
        """Request an OTP while recording privacy-safe diagnostics."""
        timed_cloud_call(
            _LOGGER,
            "OTP email request",
            self._session.send_email_otp,
            email,
        )

    @staticmethod
    def _robots_from_response(response: Any) -> list[dict[str, Any]]:
        """Validate and map the robot list returned by the cloud."""
        return [
            {
                VORWERK_ROBOT_NAME: robot["name"],
                VORWERK_ROBOT_SERIAL: robot["serial"],
                VORWERK_ROBOT_SECRET: robot["secret_key"],
                VORWERK_ROBOT_TRAITS: robot["traits"],
                VORWERK_ROBOT_ENDPOINT: robot["nucleo_url"],
            }
            for robot in response.json()
        ]


class VorwerkSession(pybotvac.PasswordlessSession):
    """Passwordless pybotvac session for Vorwerk cloud login."""

    def __init__(self) -> None:
        """Initialize the Vorwerk session."""
        super().__init__(client_id=VORWERK_CLIENT_ID, vendor=pybotvac.Vorwerk())
