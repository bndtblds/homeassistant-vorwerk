"""Config flow for the Vorwerk Kobold integration."""
from __future__ import annotations

import logging
from typing import Any

import pybotvac
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_CODE, CONF_EMAIL
from homeassistant.data_entry_flow import FlowResult
from pybotvac.exceptions import NeatoException
from requests import RequestException

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
from .diagnostics import http_status_from_exception, timed_cloud_call

_LOGGER = logging.getLogger(__name__)

DOCUMENTATION_URL = "https://github.com/bndtblds/homeassistant-vorwerk"

STEP_USER_SCHEMA = vol.Schema({vol.Required(CONF_EMAIL): str})
STEP_CODE_SCHEMA = vol.Schema({vol.Required(CONF_CODE): str})

ROBOT_LIST_ENDPOINT = "users/me/robots"
ROBOT_LIST_FALLBACK_ENDPOINT = "dashboard"


class VorwerkTokenExchangeError(Exception):
    """Raised when an OTP cannot be exchanged for a token."""


class VorwerkTokenResponseError(Exception):
    """Raised when an OTP response does not contain a usable ID token."""


class VorwerkRobotListError(Exception):
    """Raised when the robot list cannot be retrieved."""


class VorwerkRobotListResponseError(Exception):
    """Raised when a robot-list response has an unexpected structure."""


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
            try:
                await self.hass.async_add_executor_job(
                    self._send_email_otp,
                    self._email,
                )
            except (RequestException, NeatoException):
                errors["base"] = "cannot_connect"
        else:
            code = user_input[CONF_CODE].strip()
            try:
                robots = await self.hass.async_add_executor_job(
                    self._fetch_robots,
                    self._email,
                    code,
                )
            except VorwerkTokenExchangeError:
                errors["base"] = "invalid_auth"
            except VorwerkRobotListError:
                errors["base"] = "robot_list_unavailable"
            except VorwerkRobotListResponseError:
                errors["base"] = "invalid_robot_list"
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
        try:
            timed_cloud_call(
                _LOGGER,
                "OTP token exchange",
                self._session.fetch_token_passwordless,
                email,
                code,
            )
            timed_cloud_call(
                _LOGGER,
                "OTP token validation",
                self._session.validate_token,
            )
        except (RequestException, NeatoException, VorwerkTokenResponseError) as err:
            raise VorwerkTokenExchangeError from err

        try:
            return self._session.fetch_robot_list()
        except VorwerkRobotListResponseError:
            raise
        except NeatoException as err:
            raise VorwerkRobotListError from err

    def _send_email_otp(self, email: str) -> None:
        """Request an OTP with safe diagnostics."""
        timed_cloud_call(
            _LOGGER,
            "OTP email request",
            self._session.send_email_otp,
            email,
        )


class VorwerkSession(pybotvac.PasswordlessSession):
    """Passwordless pybotvac session for Vorwerk cloud login."""

    def __init__(self) -> None:
        """Initialize the Vorwerk session."""
        super().__init__(client_id=VORWERK_CLIENT_ID, vendor=pybotvac.Vorwerk())
        self._robot_list_endpoint = ROBOT_LIST_ENDPOINT

    def validate_token(self) -> None:
        """Validate the token type required by the Vorwerk robot API."""
        if not isinstance(self._token, dict):
            raise VorwerkTokenResponseError
        id_token = self._token.get("id_token")
        if not isinstance(id_token, str) or not id_token:
            raise VorwerkTokenResponseError

    def fetch_robot_list(self) -> list[dict[str, Any]]:
        """Fetch and validate robots, falling back only after an HTTP 401."""
        endpoint = self._robot_list_endpoint
        try:
            response = timed_cloud_call(
                _LOGGER,
                "robot list request",
                self.get,
                endpoint,
                warn_on_failure=endpoint != ROBOT_LIST_ENDPOINT,
            )
        except NeatoException as err:
            if (
                endpoint != ROBOT_LIST_ENDPOINT
                or http_status_from_exception(err) != 401
            ):
                status_code = http_status_from_exception(err)
                status = (
                    f", HTTP status {status_code}"
                    if status_code is not None
                    else ""
                )
                _LOGGER.warning(
                    "Vorwerk robot list request failed (%s%s)",
                    type(err).__name__,
                    status,
                )
                raise

            _LOGGER.warning(
                "Vorwerk robot list endpoint returned HTTP 401; using the "
                "compatibility endpoint for this session"
            )
            endpoint = ROBOT_LIST_FALLBACK_ENDPOINT
            response = timed_cloud_call(
                _LOGGER,
                "robot list fallback request",
                self.get,
                endpoint,
            )

        robots = timed_cloud_call(
            _LOGGER,
            "robot list validation",
            self._validate_robot_list_response,
            response,
            endpoint,
        )
        self._robot_list_endpoint = endpoint
        return robots

    @staticmethod
    def _validate_robot_list_response(
        response: Any, endpoint: str
    ) -> list[dict[str, Any]]:
        """Validate both supported response layouts and map stored robot data."""
        try:
            payload = response.json()
        except (TypeError, ValueError) as err:
            raise VorwerkRobotListResponseError from err

        if endpoint == ROBOT_LIST_ENDPOINT:
            cloud_robots = payload
        elif isinstance(payload, dict):
            cloud_robots = payload.get("robots")
        else:
            cloud_robots = None

        if not isinstance(cloud_robots, list):
            raise VorwerkRobotListResponseError

        robots: list[dict[str, Any]] = []
        for robot in cloud_robots:
            if not isinstance(robot, dict):
                raise VorwerkRobotListResponseError
            try:
                name = robot["name"]
                serial = robot["serial"]
                secret = robot["secret_key"]
                traits = robot["traits"]
                robot_endpoint = robot["nucleo_url"]
            except KeyError as err:
                raise VorwerkRobotListResponseError from err

            if not (
                isinstance(name, str)
                and isinstance(serial, str)
                and isinstance(secret, str)
                and isinstance(traits, list)
                and isinstance(robot_endpoint, str)
            ):
                raise VorwerkRobotListResponseError

            robots.append(
                {
                    VORWERK_ROBOT_NAME: name,
                    VORWERK_ROBOT_SERIAL: serial,
                    VORWERK_ROBOT_SECRET: secret,
                    VORWERK_ROBOT_TRAITS: traits,
                    VORWERK_ROBOT_ENDPOINT: robot_endpoint,
                }
            )

        return robots
