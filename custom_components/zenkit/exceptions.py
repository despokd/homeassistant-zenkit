"""Errors for the Zenkit component."""

from homeassistant.exceptions import HomeAssistantError


class ZenkitException(HomeAssistantError):
    """Base class for Zenkit exceptions."""


class CannotConnectException(ZenkitException):
    """Unable to reach the Zenkit API."""


class CannotLoginException(ZenkitException):
    """Unable to login to the Zenkit API."""


class UpdateFailedException(ZenkitException):
    """Error during update data from Zenkit."""
