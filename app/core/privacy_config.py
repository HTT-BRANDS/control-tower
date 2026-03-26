"""
Privacy and Consent Configuration

Manages cookie consent categories and user preferences.
"""

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class ConsentCategory(str, Enum):
    """Consent categories per GDPR/CCPA requirements."""
    NECESSARY = "necessary"      # Essential for site function
    FUNCTIONAL = "functional"    # Preferences, settings
    ANALYTICS = "analytics"      # Usage tracking, metrics
    MARKETING = "marketing"      # Ads, retargeting, personalization


class ConsentPreferences(BaseModel):
    """User consent preferences for each category."""

    necessary: bool = Field(default=True, description="Always required for site function")
    functional: bool = Field(default=False)
    analytics: bool = Field(default=False)
    marketing: bool = Field(default=False)

    # Metadata
    timestamp: str | None = None
    gpc_override: bool = Field(default=False, description="GPC signal forced opt-out")
    version: str = Field(default="1.0")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "necessary": True,
                "functional": True,
                "analytics": False,
                "marketing": False,
                "timestamp": "2026-03-26T15:45:00Z",
                "gpc_override": False,
                "version": "1.0"
            }
        }
    )


class PrivacyConfig:
    """Privacy configuration and consent management."""

    COOKIE_NAME = "consent_preferences"
    COOKIE_MAX_AGE = 365 * 24 * 60 * 60  # 1 year

    CATEGORIES = {
        ConsentCategory.NECESSARY: {
            "name": "Necessary",
            "description": "Essential cookies required for the website to function properly. These cannot be disabled.",
            "required": True,
            "cookies": ["session", "csrf", "auth"]
        },
        ConsentCategory.FUNCTIONAL: {
            "name": "Functional",
            "description": "Cookies that remember your preferences and settings to enhance your experience.",
            "required": False,
            "cookies": ["theme", "language", "settings"]
        },
        ConsentCategory.ANALYTICS: {
            "name": "Analytics",
            "description": "Cookies that help us understand how visitors interact with our website by collecting anonymous data.",
            "required": False,
            "cookies": ["_ga", "_gid", "_gat"]
        },
        ConsentCategory.MARKETING: {
            "name": "Marketing",
            "description": "Cookies used to deliver personalized advertisements and track campaign performance.",
            "required": False,
            "cookies": ["_fbp", "_gcl_au", "ads"]
        }
    }

    @classmethod
    def get_categories(cls) -> dict:
        """Get all consent categories with metadata."""
        return cls.CATEGORIES

    @classmethod
    def apply_gpc_override(cls, preferences: ConsentPreferences) -> ConsentPreferences:
        """Apply GPC signal to opt out of analytics and marketing."""
        preferences.analytics = False
        preferences.marketing = False
        preferences.gpc_override = True
        return preferences
