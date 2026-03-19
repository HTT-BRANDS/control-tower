"""Custom compliance rule service — CRUD and JSON Schema evaluation (CM-002)."""

from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models.custom_rule import CustomComplianceRule

logger = logging.getLogger(__name__)

# Maximum allowed rule schema size (bytes) — prevents DoS
MAX_RULE_SCHEMA_SIZE = 65_536  # 64 KB

VALID_CATEGORIES = {"resource_property", "compliance_score", "mfa_coverage"}
VALID_SEVERITIES = {"low", "medium", "high", "critical"}


def _validate_schema(rule_schema: dict) -> list[str]:
    """Validate rule_schema content. Returns list of validation error strings."""
    errors = []

    serialized = json.dumps(rule_schema)
    if len(serialized) > MAX_RULE_SCHEMA_SIZE:
        errors.append(f"rule_schema exceeds maximum size of {MAX_RULE_SCHEMA_SIZE} bytes")

    # Block remote $ref URLs (SSRF prevention per ADR-0005 FF-3)
    if '"$ref"' in serialized:
        refs = re.findall(r'"\$ref"\s*:\s*"([^"]*)"', serialized)
        for ref in refs:
            if ref.startswith("http://") or ref.startswith("https://"):
                errors.append(f"Remote $ref URL not allowed: {ref}")

    return errors


class CustomRuleService:
    """CRUD service for tenant-defined compliance rules."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        *,
        tenant_id: str,
        name: str,
        category: str,
        rule_schema: dict,
        description: str | None = None,
        severity: str = "medium",
        created_by: str | None = None,
    ) -> tuple[CustomComplianceRule | None, list[str]]:
        """Create a new custom compliance rule.

        Returns (rule, []) on success, (None, errors) on validation failure.
        """
        errors = []

        if category not in VALID_CATEGORIES:
            errors.append(f"category must be one of {sorted(VALID_CATEGORIES)}")
        if severity not in VALID_SEVERITIES:
            errors.append(f"severity must be one of {sorted(VALID_SEVERITIES)}")
        if not name or not name.strip():
            errors.append("name is required and cannot be blank")

        errors.extend(_validate_schema(rule_schema))

        if errors:
            return None, errors

        rule = CustomComplianceRule(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            name=name.strip(),
            description=description,
            category=category,
            severity=severity,
            rule_schema=rule_schema,
            created_by=created_by,
        )
        try:
            self.db.add(rule)
            self.db.commit()
            self.db.refresh(rule)
            logger.info("Custom rule created: %s (%s)", rule.id, rule.name)
            return rule, []
        except Exception as exc:
            self.db.rollback()
            logger.error("Failed to create custom rule: %s", exc)
            return None, [str(exc)]

    def get(self, rule_id: str, tenant_id: str) -> CustomComplianceRule | None:
        """Fetch a single rule, enforcing tenant isolation."""
        return (
            self.db.query(CustomComplianceRule)
            .filter(
                CustomComplianceRule.id == rule_id,
                CustomComplianceRule.tenant_id == tenant_id,
            )
            .first()
        )

    def list_rules(
        self,
        tenant_id: str,
        *,
        category: str | None = None,
        enabled_only: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> list[CustomComplianceRule]:
        """List rules for a tenant with optional filters."""
        q = self.db.query(CustomComplianceRule).filter(
            CustomComplianceRule.tenant_id == tenant_id
        )
        if category:
            q = q.filter(CustomComplianceRule.category == category)
        if enabled_only:
            q = q.filter(CustomComplianceRule.is_enabled.is_(True))
        return (
            q.order_by(CustomComplianceRule.created_at.desc())
            .offset(offset)
            .limit(min(limit, 500))
            .all()
        )

    def update(
        self,
        rule_id: str,
        tenant_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
        severity: str | None = None,
        rule_schema: dict | None = None,
        is_enabled: bool | None = None,
    ) -> tuple[CustomComplianceRule | None, list[str]]:
        """Update a rule. Returns (updated_rule, []) or (None, errors)."""
        rule = self.get(rule_id, tenant_id)
        if rule is None:
            return None, ["Rule not found or access denied"]

        errors = []
        if severity is not None and severity not in VALID_SEVERITIES:
            errors.append(f"severity must be one of {sorted(VALID_SEVERITIES)}")
        if rule_schema is not None:
            errors.extend(_validate_schema(rule_schema))
        if errors:
            return None, errors

        if name is not None:
            rule.name = name.strip()
        if description is not None:
            rule.description = description
        if severity is not None:
            rule.severity = severity
        if rule_schema is not None:
            rule.rule_schema = rule_schema
        if is_enabled is not None:
            rule.is_enabled = is_enabled
        rule.updated_at = datetime.now(UTC)

        try:
            self.db.commit()
            self.db.refresh(rule)
            return rule, []
        except Exception as exc:
            self.db.rollback()
            return None, [str(exc)]

    def delete(self, rule_id: str, tenant_id: str) -> bool:
        """Delete a rule. Returns True if deleted, False if not found."""
        rule = self.get(rule_id, tenant_id)
        if rule is None:
            return False
        try:
            self.db.delete(rule)
            self.db.commit()
            return True
        except Exception as exc:
            self.db.rollback()
            logger.error("Failed to delete custom rule %s: %s", rule_id, exc)
            return False

    def evaluate(
        self, rule: CustomComplianceRule, resource_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Evaluate a rule's schema against a resource data dict.

        Uses jsonschema Draft 2020-12 for evaluation.
        Returns {passed: bool, errors: [str]}.
        """
        try:
            from jsonschema import ValidationError, validate  # noqa: F401

            validate(instance=resource_data, schema=rule.rule_schema)
            return {"passed": True, "errors": []}
        except ImportError:
            return {"passed": False, "errors": ["jsonschema not installed"]}
        except Exception as exc:
            return {"passed": False, "errors": [str(exc)]}
