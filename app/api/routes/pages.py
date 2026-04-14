"""Section page routes.

Serves the HTML pages for Costs, Compliance, Resources, and Identity
sections. Data is loaded client-side via HTMX/fetch from the /api/v1/* endpoints.

Persona gating: each page specifies its `page_key` (matching keys in
`config/personas.yaml`). `_persona_context` resolves the set of visible
nav keys for the current user and enforces access when the user has an
assigned persona that does not include this page. Users with no persona
assignment see everything (soft rollout).
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.api.services.admin_service import AdminService
from app.core.auth import User, get_current_user
from app.core.database import get_db
from app.core.permissions import has_permission
from app.core.personas import can_view_page, pages_for_personas
from app.core.templates import templates
from app.core.tenant_context import get_brand_context_for_request

router = APIRouter(
    tags=["pages"],
    dependencies=[Depends(get_current_user)],
)


def _persona_context(user: User, page_key: str) -> dict[str, Any]:
    """Build template context for persona-aware nav + enforce access.

    - Raises 403 if the user has personas assigned and none grant this page.
    - Returns {"visible_pages": set, "user_personas": list, "page_key": key}.
    - Admins always have access and see "*".
    """
    if not can_view_page(user, page_key):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Persona does not grant access to '{page_key}'",
        )

    personas = list(getattr(user, "personas", None) or [])
    if "admin" in user.roles:
        visible: set[str] = {"*"}
    elif not personas:
        visible = {"*"}  # soft default — no persona assigned yet
    else:
        visible = pages_for_personas(personas)

    return {
        "visible_pages": visible,
        "user_personas": personas,
        "page_key": page_key,
    }


@router.get("/costs", response_class=HTMLResponse)
async def costs_page(request: Request, user: User = Depends(get_current_user)):
    """Cost management dashboard page."""
    brand_context = get_brand_context_for_request(request)
    return templates.TemplateResponse(
        request,
        "pages/costs.html",
        {**brand_context, **_persona_context(user, "costs")},
    )


@router.get("/compliance", response_class=HTMLResponse)
async def compliance_page(request: Request, user: User = Depends(get_current_user)):
    """Compliance monitoring dashboard page."""
    brand_context = get_brand_context_for_request(request)
    return templates.TemplateResponse(
        request,
        "pages/compliance.html",
        {**brand_context, **_persona_context(user, "compliance")},
    )


@router.get("/resources", response_class=HTMLResponse)
async def resources_page(request: Request, user: User = Depends(get_current_user)):
    """Resource inventory dashboard page."""
    brand_context = get_brand_context_for_request(request)
    return templates.TemplateResponse(
        request,
        "pages/resources.html",
        {**brand_context, **_persona_context(user, "resources")},
    )


@router.get("/identity", response_class=HTMLResponse)
async def identity_page(request: Request, user: User = Depends(get_current_user)):
    """Identity & access dashboard page."""
    brand_context = get_brand_context_for_request(request)
    return templates.TemplateResponse(
        request,
        "pages/identity.html",
        {**brand_context, **_persona_context(user, "identity")},
    )


@router.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request, user: User = Depends(get_current_user)):
    """Admin dashboard — user management, role assignment, platform stats."""
    if not has_permission(user.roles, "system:admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    brand_context = get_brand_context_for_request(request)
    return templates.TemplateResponse(
        request,
        "pages/admin_dashboard.html",
        {
            **brand_context,
            "visible_pages": {"*"},
            "page_key": "admin",
            "user": user,
        },
    )


@router.get("/admin/partials/users-table", response_class=HTMLResponse)
async def admin_users_table_partial(
    request: Request,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=50),
    search: str = Query("", max_length=100),
    role: str = Query("", max_length=50),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """HTMX partial: admin users table body rows."""
    if not has_permission(user.roles, "system:admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    svc = AdminService(db)
    result = svc.get_users(
        page=page,
        per_page=per_page,
        search=search or None,
        role_filter=role or None,
    )
    return templates.TemplateResponse(
        request,
        "partials/admin_users_table_body.html",
        {
            "users": result["items"],
            "total": result["total"],
            "page": result["page"],
            "pages": result["pages"],
        },
    )


@router.get("/privacy", response_class=HTMLResponse)
async def privacy_page(request: Request):
    """Privacy policy page."""
    brand_context = get_brand_context_for_request(request)
    return templates.TemplateResponse(
        request,
        "pages/privacy.html",
        {**brand_context},
    )
