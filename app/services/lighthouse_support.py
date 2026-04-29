"""Shared helpers for Lighthouse client mixins."""

import sys
from types import ModuleType


def lighthouse_module() -> ModuleType:
    """Return the public lighthouse_client module for patch-compatible lookups."""
    return sys.modules["app.services.lighthouse_client"]
