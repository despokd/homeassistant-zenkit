"""Lookup of the elements (fields) of a list, see docs/zenkit/zenkit-todo.md."""

from .const import COMPLETED_COLOR

TEXT_ELEMENT = 1
DATE_ELEMENT = 4
CATEGORIES_ELEMENT = 6


def title_element(elements: list[dict]) -> dict | None:
    """Get the title element of a list."""
    return _role_element(elements, "title") or next(
        (element for element in elements if element.get("isPrimary")), None
    )


def notes_element(elements: list[dict]) -> dict | None:
    """Get the description element of a list."""
    return _role_element(elements, "notes") or _unused_element(elements, TEXT_ELEMENT)


def due_element(elements: list[dict]) -> dict | None:
    """Get the due date element of a list."""
    return _role_element(elements, "dueDate") or _unused_element(elements, DATE_ELEMENT)


def stage_element(elements: list[dict]) -> dict | None:
    """Get the status element of a list."""
    stage = _role_element(elements, "stage")
    if stage is not None:
        return stage
    # Fallback for lists without roles: categories element with a "done" colored option
    for element in elements:
        if element.get("elementcategory") == CATEGORIES_ELEMENT and any(
            option.get("colorHex") == COMPLETED_COLOR
            for option in _status_options(element)
        ):
            return element
    return None


def status_option(element: dict, completed: bool) -> dict | None:
    """Get the option for the completed or open status of a status element."""
    options = _status_options(element)
    role = "done" if completed else "todo"
    for option in options:
        if option.get("resourceRole") == role:
            return option
    if completed:
        for option in options:
            if option.get("colorHex") == COMPLETED_COLOR:
                return option
    return None


def _role_element(elements: list[dict], role: str) -> dict | None:
    """Get the element with a role."""
    for element in elements:
        if element.get("resourceRole") == role:
            return element
    return None


def _unused_element(elements: list[dict], category: int) -> dict | None:
    """Get the first element of a category which is neither the title nor has a role."""
    title = title_element(elements)
    for element in elements:
        if (
            element.get("elementcategory") == category
            and element.get("resourceRole") is None
            and element is not title
        ):
            return element
    return None


def _status_options(element: dict) -> list[dict]:
    """Get the selectable options of a categories element."""
    return (element.get("elementData") or {}).get("predefinedCategories") or []
