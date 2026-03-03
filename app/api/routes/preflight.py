"""Preflight check API routes."""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.core.auth import User, get_current_user, require_roles
from app.core.authorization import (
    TenantAuthorization,
    get_tenant_authorization,
    get_user_tenants,
)
from app.core.database import get_db
from app.preflight.models import (
    CategorySummary,
    CheckCategory,
    PreflightCheckRequest,
    PreflightReport,
    PreflightStatusResponse,
    TenantCheckSummary,
)
from app.preflight.reports import ReportGenerator
from app.preflight.runner import (
    PreflightRunner,
    get_latest_report,
    get_runner,
    set_latest_report,
)
from app.core.tenant_context import get_brand_context_for_request

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/preflight",
    tags=["preflight"],
    dependencies=[Depends(get_current_user)],
)
templates = Jinja2Templates(directory="app/templates")


@router.get("", response_class=HTMLResponse)
async def preflight_page(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """Preflight checks dashboard page."""
    latest = get_latest_report()
    runner = get_runner()
    brand_context = get_brand_context_for_request(request)

    category_summaries = []
    tenant_summaries = []
    results = []

    if latest:
        category_summaries = runner.get_category_summaries(latest)
        tenant_summaries = runner.get_tenant_summaries(latest)
        results = latest.results

    return templates.TemplateResponse(
        "pages/preflight.html",
        {
            "request": request,
            "report": latest,
            "category_summaries": category_summaries,
            "tenant_summaries": tenant_summaries,
            "results": results,
            **brand_context,
        },
    )


@router.get("/status", response_model=PreflightStatusResponse)
async def get_preflight_status():
    """Get the latest preflight check results."""
    latest = get_latest_report()
    runner = get_runner()

    return PreflightStatusResponse(
        latest_report=latest,
        last_run_at=latest.started_at if latest else None,
        is_running=runner.is_running,
    )


@router.post("/run", response_model=PreflightReport)
async def run_preflight_checks(
    request: PreflightCheckRequest = PreflightCheckRequest(),
) -> PreflightReport:
    """Run preflight checks.

    Execute all preflight checks to verify Azure tenant access, GitHub access,
    and system requirements. Results include detailed status for each check
    along with recommendations for any failures.

    Args:
        request: Optional parameters to customize the check run

    Returns:
        Complete PreflightReport with all check results
    """
    runner = get_runner()

    if runner.is_running:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Preflight checks are already running",
        )

    # Create a new runner with the request parameters
    new_runner = PreflightRunner(
        categories=request.categories,
        tenant_ids=request.tenant_ids,
        fail_fast=request.fail_fast,
        timeout_seconds=request.timeout_seconds,
    )

    logger.info(
        f"Starting preflight checks: categories={request.categories}, "
        f"tenant_ids={request.tenant_ids}, fail_fast={request.fail_fast}"
    )

    try:
        report = await new_runner.run_checks(
            categories=request.categories,
            tenant_ids=request.tenant_ids,
        )

        # Store the report globally
        set_latest_report(report)

        logger.info(
            f"Preflight checks completed: {report.passed_count} passed, "
            f"{report.warning_count} warnings, {report.failed_count} failed"
        )

        return report

    except Exception as e:
        logger.error(f"Preflight check run failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Preflight check run failed: {str(e)}",
        )


@router.get("/tenants/{tenant_id}", response_model=PreflightReport)
async def check_tenant_preflight(
    tenant_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    authz: TenantAuthorization = Depends(get_tenant_authorization),
) -> PreflightReport:
    """Run preflight checks for a specific tenant.

    Verifies access and configuration for a single Azure tenant.
    User must have access to the tenant.

    Args:
        tenant_id: The tenant ID to check

    Returns:
        PreflightReport with tenant-specific check results
    """
    # Validate tenant access
    authz.validate_access(tenant_id)

    runner = get_runner()

    if runner.is_running:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Preflight checks are already running",
        )

    new_runner = PreflightRunner(
        tenant_ids=[tenant_id],
        fail_fast=False,
    )

    logger.info(f"Running preflight checks for tenant: {tenant_id}")

    try:
        report = await new_runner.run_checks(tenant_ids=[tenant_id])
        set_latest_report(report)
        return report

    except Exception as e:
        logger.error(f"Tenant preflight check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Tenant preflight check failed: {str(e)}",
        )


@router.get("/github", response_model=PreflightReport)
async def check_github_preflight() -> PreflightReport:
    """Run GitHub-specific preflight checks.

    Verifies GitHub repository access and Actions workflow permissions.

    Returns:
        PreflightReport with GitHub-specific check results
    """
    runner = get_runner()

    if runner.is_running:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Preflight checks are already running",
        )

    new_runner = PreflightRunner(
        categories=[CheckCategory.GITHUB_ACCESS, CheckCategory.GITHUB_ACTIONS],
        fail_fast=False,
    )

    logger.info("Running GitHub preflight checks")

    try:
        report = await new_runner.run_checks(
            categories=[CheckCategory.GITHUB_ACCESS, CheckCategory.GITHUB_ACTIONS]
        )
        set_latest_report(report)
        return report

    except Exception as e:
        logger.error(f"GitHub preflight check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"GitHub preflight check failed: {str(e)}",
        )


@router.get("/report/json")
async def get_report_json():
    """Get the latest preflight report in JSON format."""
    latest = get_latest_report()

    if not latest:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No preflight report available. Run checks first.",
        )

    generator = ReportGenerator(latest)
    return JSONResponse(content=json.loads(generator.to_json()))


@router.get("/report/markdown")
async def get_report_markdown():
    """Get the latest preflight report in Markdown format."""
    latest = get_latest_report()

    if not latest:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No preflight report available. Run checks first.",
        )

    generator = ReportGenerator(latest)
    return {"content": generator.to_markdown()}


@router.get("/summary/tenants", response_model=list[TenantCheckSummary])
async def get_tenant_summaries():
    """Get summaries grouped by tenant from the latest report."""
    latest = get_latest_report()

    if not latest:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No preflight report available. Run checks first.",
        )

    runner = get_runner()
    return runner.get_tenant_summaries(latest)


@router.get("/summary/categories", response_model=list[CategorySummary])
async def get_category_summaries():
    """Get summaries grouped by category from the latest report."""
    latest = get_latest_report()

    if not latest:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No preflight report available. Run checks first.",
        )

    runner = get_runner()
    return runner.get_category_summaries(latest)


@router.post("/clear-cache")
async def clear_preflight_cache():
    """Clear all preflight check caches."""
    PreflightRunner.clear_all_caches()
    return {"message": "Cache cleared successfully"}
