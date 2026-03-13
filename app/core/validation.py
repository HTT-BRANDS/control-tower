"""Validation utilities."""

import re


def validate_uuid_param(value: str) -> str:
    """Validate UUID format.

    Args:
        value: The UUID string to validate.

    Returns:
        str: The validated UUID.

    Raises:
        ValueError: If the UUID format is invalid.
    """
    uuid_pattern = r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
    if not re.match(uuid_pattern, value):
        raise ValueError(f"Invalid UUID format: {value}")
    return value.lower()
