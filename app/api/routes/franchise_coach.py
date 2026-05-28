"""Franchise-Coach dashboard route (Manager-tier surface).

Read-only cross-brand insights for franchise leadership coaching.
Gated by the ``franchise_coach:read`` permission, which is granted
to the MANAGER role and (via wildcard) to ADMIN.

See:
    - ADR-0012 — Manager role rationale
    - app/api/services/franchise_coach_service.py — data assembly
    - app/templates/pages/franchise_coach.html — view
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session

from app.api.services.franchise_coach_service import build_franchise_coach_view
from app.core.auth import User, get_current_user
from app.core.database import get_db
from app.core.permissions import FRANCHISE_COACH_EXPORT, FRANCHISE_COACH_READ
from app.core.rbac import require_permissions
from app.core.templates import templates

router = APIRouter(
    prefix="/franchise-coach",
    tags=["franchise-coach"],
    dependencies=[Depends(get_current_user)],
)


@router.get("", response_class=HTMLResponse)
async def franchise_coach_dashboard(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_permissions(FRANCHISE_COACH_READ)),
) -> HTMLResponse:
    """Render the franchise-coach dashboard.

    Requires ``franchise_coach:read`` — Manager-tier and above.
    """
    view = build_franchise_coach_view(db)
    return templates.TemplateResponse(
        request,
        "pages/franchise_coach.html",
        {
            "user": user,
            "view": view,
            "page_title": "Franchise Coach",
        },
    )


@router.get("/api", response_class=JSONResponse)
async def franchise_coach_api(
    db: Session = Depends(get_db),
    _user: User = Depends(require_permissions(FRANCHISE_COACH_READ)),
) -> JSONResponse:
    """JSON view of the same data — for HTMX partials and exports."""
    view = build_franchise_coach_view(db)
    return JSONResponse(view.model_dump(mode="json"))


@router.get("/export.csv")
async def franchise_coach_export(
    db: Session = Depends(get_db),
    _user: User = Depends(require_permissions(FRANCHISE_COACH_EXPORT)),
):
    """CSV export — coaching prep packet for a 1:1 with a brand operator.

    Requires ``franchise_coach:export``.
    """
    import csv
    import io

    view = build_franchise_coach_view(db)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "brand",
            "severity",
            "mfa_coverage_pct",
            "stale_30d",
            "compliance_pct",
            "secure_score",
            "non_compliant_resources",
            "headline",
        ]
    )
    for card in view.cards:
        writer.writerow(
            [
                card.brand_name,
                card.overall_severity,
                card.identity.mfa_coverage_percent if card.identity else "",
                card.identity.stale_accounts_30d if card.identity else "",
                card.compliance.overall_compliance_percent if card.compliance else "",
                card.compliance.secure_score if card.compliance else "",
                card.compliance.non_compliant_resource_count if card.compliance else "",
                card.headline,
            ]
        )
    from fastapi.responses import Response

    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=franchise-coach.csv"},
    )
