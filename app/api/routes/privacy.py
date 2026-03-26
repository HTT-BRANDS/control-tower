"""
Privacy API Routes

Endpoints for consent management and privacy preferences.
"""

from fastapi import APIRouter, Request, Response

from app.api.services.privacy_service import PrivacyService
from app.core.privacy_config import ConsentPreferences, PrivacyConfig

router = APIRouter(prefix="/api/v1/privacy", tags=["privacy"])


@router.get("/consent/categories")
async def get_consent_categories():
    """Get all available consent categories with descriptions."""
    return {
        "categories": PrivacyConfig.CATEGORIES,
        "cookie_name": PrivacyConfig.COOKIE_NAME,
        "version": "1.0"
    }


@router.get("/consent/preferences")
async def get_consent_preferences(request: Request):
    """Get current user's consent preferences."""
    preferences = PrivacyService.get_effective_consent(request)
    return preferences.model_dump()


@router.post("/consent/preferences")
async def save_consent_preferences(
    request: Request,
    response: Response,
    preferences: ConsentPreferences
):
    """Save user's consent preferences."""
    # Ensure necessary is always True
    preferences.necessary = True

    PrivacyService.save_consent_to_cookie(response, preferences)

    return {
        "status": "saved",
        "preferences": preferences.model_dump()
    }


@router.post("/consent/accept-all")
async def accept_all_cookies(request: Request, response: Response):
    """Accept all cookie categories."""
    preferences = ConsentPreferences(
        necessary=True,
        functional=True,
        analytics=True,
        marketing=True
    )

    PrivacyService.save_consent_to_cookie(response, preferences)

    return {
        "status": "accepted_all",
        "preferences": preferences.model_dump()
    }


@router.post("/consent/reject-all")
async def reject_all_cookies(request: Request, response: Response):
    """Reject all non-essential cookies."""
    preferences = ConsentPreferences(
        necessary=True,  # Required
        functional=False,
        analytics=False,
        marketing=False
    )

    PrivacyService.save_consent_to_cookie(response, preferences)

    return {
        "status": "rejected_non_essential",
        "preferences": preferences.model_dump()
    }


@router.get("/consent/status")
async def get_consent_status(request: Request):
    """Get quick consent status for frontend checks."""
    prefs = PrivacyService.get_effective_consent(request)

    return {
        "has_consented": prefs.timestamp is not None,
        "gpc_override": prefs.gpc_override,
        "categories": {
            "necessary": prefs.necessary,
            "functional": prefs.functional,
            "analytics": prefs.analytics,
            "marketing": prefs.marketing
        }
    }
