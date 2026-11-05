"""Errors for the Zenkit component."""

from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from .const import DOMAIN


class ZenkitException(HomeAssistantError):
    """Base class for Zenkit exceptions."""


class CannotConnectException(ZenkitException):
    """Unable to reach the Zenkit API."""


class CannotLoginException(ZenkitException):
    """Unable to login to the Zenkit API."""


class UpdateFailedException(ZenkitException):
    """Error during update data from Zenkit."""


class InvalidValueException(ZenkitException, ServiceValidationError):
    """A value to write doesn't fit the fields of a list."""

    def __init__(self, translation_key: str, **placeholders: str) -> None:
        """Initialize with a translated message."""
        super().__init__(
            translation_domain=DOMAIN,
            translation_key=translation_key,
            translation_placeholders=placeholders,
        )
