"""Custom compliance rule CRUD routes — CM-002."""

from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.services.custom_rule_service import (
    VALID_CATEGORIES,  # noqa: F401
    VALID_SEVERITIES,  # noqa: F401
    CustomRuleService,
)
from app.core.auth import User, get_current_user
from app.core.database import get_db
from app.core.rate_limit import rate_limit

router = APIRouter(
    prefix="/api/v1/compliance/rules",
    tags=["compliance-rules"],
    dependencies=[Depends(rate_limit("default"))],
)


class CreateRuleRequest(BaseModel):
    tenant_id: str = Field(..., description="Tenant UUID this rule belongs to")
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    category: str = Field(..., description="resource_property | compliance_score | mfa_coverage")
    severity: str = Field(default="medium", description="low | medium | high | critical")
    rule_schema: dict = Field(..., description="JSON Schema definition for this rule")


class UpdateRuleRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    severity: str | None = None
    rule_schema: dict | None = None
    is_enabled: bool | None = None


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_rule(
    body: CreateRuleRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Create a custom compliance rule.

    Rule schemas follow JSON Schema Draft 2020-12. Max size: 64KB.
    Remote $ref URLs are blocked (SSRF prevention).
    """
    svc = CustomRuleService(db)
    rule, errors = svc.create(
        tenant_id=body.tenant_id,
        name=body.name,
        description=body.description,
        category=body.category,
        severity=body.severity,
        rule_schema=body.rule_schema,
        created_by=(getattr(current_user, "email", None) or getattr(current_user, "id", None)),
    )
    if errors:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=errors)
    return rule.to_dict()


@router.get("")
async def list_rules(
    tenant_id: str = Query(..., description="Tenant UUID to list rules for"),
    category: str | None = Query(default=None),
    enabled_only: bool = Query(default=False),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """List custom compliance rules for a tenant."""
    svc = CustomRuleService(db)
    rules = svc.list_rules(
        tenant_id,
        category=category,
        enabled_only=enabled_only,
        limit=limit,
        offset=offset,
    )
    return {
        "rules": [r.to_dict() for r in rules],
        "count": len(rules),
        "tenant_id": tenant_id,
    }


@router.get("/{rule_id}")
async def get_rule(
    rule_id: str = Path(...),
    tenant_id: str = Query(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Get a single custom compliance rule."""
    svc = CustomRuleService(db)
    rule = svc.get(rule_id, tenant_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Rule not found")
    return rule.to_dict()


@router.put("/{rule_id}")
async def update_rule(
    rule_id: str = Path(...),
    tenant_id: str = Query(...),
    body: UpdateRuleRequest = Body(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Update a custom compliance rule."""
    svc = CustomRuleService(db)
    rule, errors = svc.update(
        rule_id,
        tenant_id,
        name=body.name,
        description=body.description,
        severity=body.severity,
        rule_schema=body.rule_schema,
        is_enabled=body.is_enabled,
    )
    if errors:
        code = 404 if "not found" in errors[0].lower() else 422
        raise HTTPException(status_code=code, detail=errors)
    return rule.to_dict()


@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rule(
    rule_id: str = Path(...),
    tenant_id: str = Query(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    """Delete a custom compliance rule."""
    svc = CustomRuleService(db)
    deleted = svc.delete(rule_id, tenant_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Rule not found")
