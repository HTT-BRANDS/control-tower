"""
Privacy Service — Manages user consent and privacy preferences
"""

import json
from datetime import UTC, datetime

from fastapi import Request, Response

from app.core.gpc_middleware import get_gpc_status
from app.core.privacy_config import ConsentCategory, ConsentPreferences, PrivacyConfig


class PrivacyService:
    """Service for managing privacy preferences and consent."""

    @staticmethod
    def get_consent_from_cookie(request: Request) -> ConsentPreferences | None:
        """Parse consent preferences from cookie."""
        consent_cookie = request.cookies.get(PrivacyConfig.COOKIE_NAME)
        if consent_cookie:
            try:
                data = json.loads(consent_cookie)
                return ConsentPreferences(**data)
            except (json.JSONDecodeError, ValueError):
                return None
        return None

    @staticmethod
    def save_consent_to_cookie(
        response: Response,
        preferences: ConsentPreferences
    ) -> None:
        """Save consent preferences to cookie."""
        preferences.timestamp = datetime.now(UTC).isoformat()

        response.set_cookie(
            key=PrivacyConfig.COOKIE_NAME,
            value=preferences.model_dump_json(),
            max_age=PrivacyConfig.COOKIE_MAX_AGE,
            httponly=False,  # Must be accessible to JS for consent management
            secure=True,
            samesite="Lax"
        )

    @classmethod
    def get_effective_consent(cls, request: Request) -> ConsentPreferences:
        """
        Get effective consent preferences.
        
        Priority:
        1. GPC signal (if enabled, forces opt-out)
        2. Saved cookie preferences
        3. Default (all opt-out except necessary)
        """
        # Check for GPC signal first
        if get_gpc_status(request):
            prefs = ConsentPreferences()
            return PrivacyConfig.apply_gpc_override(prefs)

        # Check for saved preferences
        saved = cls.get_consent_from_cookie(request)
        if saved:
            return saved

        # Return defaults (opt-out)
        return ConsentPreferences()

    @staticmethod
    def has_consent_for(
        request: Request,
        category: ConsentCategory
    ) -> bool:
        """Check if user has consented to specific category."""
        prefs = PrivacyService.get_effective_consent(request)
        return getattr(prefs, category.value, False)

    @staticmethod
    def can_track(request: Request) -> bool:
        """Check if analytics tracking is allowed."""
        return PrivacyService.has_consent_for(request, ConsentCategory.ANALYTICS)

    @staticmethod
    def can_use_marketing_cookies(request: Request) -> bool:
        """Check if marketing cookies are allowed."""
        return PrivacyService.has_consent_for(request, ConsentCategory.MARKETING)
