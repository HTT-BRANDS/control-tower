"""Section page routes.

Serves the HTML pages for Costs, Compliance, Resources, and Identity
sections. Data is loaded client-side via HTMX/fetch from the /api/v1/* endpoints.
"""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.core.auth import get_current_user
from app.core.tenant_context import get_brand_context_for_request

router = APIRouter(
    tags=["pages"],
    dependencies=[Depends(get_current_user)],
)
templates = Jinja2Templates(directory="app/templates")
templates.env.globals["app_version"] = __import__("app").__version__


@router.get("/costs", response_class=HTMLResponse)
async def costs_page(request: Request):
    """Cost management dashboard page."""
    brand_context = get_brand_context_for_request(request)
    return templates.TemplateResponse(
        request,
        "pages/costs.html",
        {**brand_context},
    )


@router.get("/compliance", response_class=HTMLResponse)
async def compliance_page(request: Request):
    """Compliance monitoring dashboard page."""
    brand_context = get_brand_context_for_request(request)
    return templates.TemplateResponse(
        request,
        "pages/compliance.html",
        {**brand_context},
    )


@router.get("/resources", response_class=HTMLResponse)
async def resources_page(request: Request):
    """Resource inventory dashboard page."""
    brand_context = get_brand_context_for_request(request)
    return templates.TemplateResponse(
        request,
        "pages/resources.html",
        {**brand_context},
    )


@router.get("/identity", response_class=HTMLResponse)
async def identity_page(request: Request):
    """Identity & access dashboard page."""
    brand_context = get_brand_context_for_request(request)
    return templates.TemplateResponse(
        request,
        "pages/identity.html",
        {**brand_context},
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
