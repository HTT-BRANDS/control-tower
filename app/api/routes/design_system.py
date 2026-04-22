"""Design system showcase route.

Renders /design-system, a single page that exercises every macro in
`app/templates/macros/ds.html` × every variant. Used for:
  - visual QA when iterating on tokens
  - screenshot baselines (docs/design-system/)
  - the eventual Phase 6 visual regression suite

Auth-gated to match the rest of the app's web routes. Logged-in users only.

See: docs/decisions/adr-0005-design-system-overhaul.md (Phase 2)
     bd issue azure-governance-platform-oxfd
"""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from app.core.auth import User, get_current_user
from app.core.templates import templates
from app.core.tenant_context import get_brand_context_for_request

router = APIRouter(
    tags=["design-system"],
    dependencies=[Depends(get_current_user)],
)


@router.get("/design-system", response_class=HTMLResponse)
async def design_system_showcase(
    request: Request,
    user: User = Depends(get_current_user),
):
    """Render every ds-template macro variant on one page.

    No data dependencies — this page is intentionally static so it stays
    boot-fast and safe to render even when downstream services are flaky.
    """
    brand_context = get_brand_context_for_request(request)
    return templates.TemplateResponse(
        request,
        "pages/design_system.html",
        {**brand_context},
    )
