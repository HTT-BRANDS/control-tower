"""Resource Provisioning Standards service (RM-008).

Loads and validates resource provisioning standards from YAML config.
Evaluates resources against naming conventions, allowed regions,
required tags, SKU restrictions, and network/encryption standards.

Traces: RM-008 (Resource provisioning standards)
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

CONFIG_PATH = Path("config/provisioning_standards.yaml")


class ValidationResult(BaseModel):
    """Result of validating a resource against provisioning standards."""

    resource_id: str
    resource_name: str
    resource_type: str
    is_compliant: bool = True
    violations: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[dict[str, Any]] = Field(default_factory=list)

    @property
    def violation_count(self) -> int:
        return len(self.violations)

    @property
    def warning_count(self) -> int:
        return len(self.warnings)


class ProvisioningStandardsSummary(BaseModel):
    """Summary of provisioning standards compliance across resources."""

    total_resources: int = 0
    compliant_resources: int = 0
    non_compliant_resources: int = 0
    compliance_percentage: float = 0.0
    violation_breakdown: dict[str, int] = Field(default_factory=dict)
    top_violations: list[dict[str, Any]] = Field(default_factory=list)


class ProvisioningStandards:
    """Loaded provisioning standards from YAML config."""

    def __init__(self, config: dict[str, Any]) -> None:
        self._config = config
        self.version = config.get("version", "unknown")
        self.naming = config.get("naming_conventions", {})
        self.allowed_regions = config.get("allowed_regions", {})
        self.required_tags = config.get("required_tags", {})
        self.sku_restrictions = config.get("sku_restrictions", {})
        self.network_standards = config.get("network_standards", {})
        self.encryption_standards = config.get("encryption_standards", {})

    def to_dict(self) -> dict[str, Any]:
        """Return the full standards configuration as a dictionary."""
        return self._config


class ProvisioningStandardsService:
    """Service for evaluating resources against provisioning standards.

    Loads standards from config/provisioning_standards.yaml and provides
    validation methods for individual resources and tenant-wide summaries.
    """

    def __init__(self, config_path: Path | None = None) -> None:
        self._config_path = config_path or CONFIG_PATH
        self._standards: ProvisioningStandards | None = None

    def _load_standards(self) -> ProvisioningStandards:
        """Load standards from YAML config, caching the result."""
        if self._standards is not None:
            return self._standards

        if not self._config_path.exists():
            logger.warning(
                "Provisioning standards config not found at %s; using empty defaults",
                self._config_path,
            )
            self._standards = ProvisioningStandards({})
            return self._standards

        with open(self._config_path) as f:
            config = yaml.safe_load(f) or {}

        self._standards = ProvisioningStandards(config)
        logger.info(
            "Loaded provisioning standards v%s from %s",
            self._standards.version,
            self._config_path,
        )
        return self._standards

    def get_standards(self) -> dict[str, Any]:
        """Return the full provisioning standards configuration."""
        standards = self._load_standards()
        return standards.to_dict()

    def validate_resource_name(self, name: str) -> list[dict[str, Any]]:
        """Validate a resource name against naming conventions.

        Args:
            name: The resource name to validate.

        Returns:
            List of violation dicts. Empty list means compliant.
        """
        standards = self._load_standards()
        naming = standards.naming
        violations: list[dict[str, Any]] = []

        if not naming:
            return violations

        max_length = naming.get("max_length", 63)
        if len(name) > max_length:
            violations.append(
                {
                    "rule": "naming_length",
                    "message": f"Resource name exceeds {max_length} characters ({len(name)})",
                    "severity": "error",
                }
            )

        allowed_chars = naming.get("allowed_characters", "a-z0-9-")
        pattern = f"^[{allowed_chars}]+$"
        if not re.match(pattern, name):
            violations.append(
                {
                    "rule": "naming_characters",
                    "message": f"Resource name contains characters outside allowed set ({allowed_chars})",
                    "severity": "error",
                }
            )

        return violations

    def validate_region(self, region: str) -> list[dict[str, Any]]:
        """Validate a resource region against allowed regions.

        Args:
            region: The Azure region to validate.

        Returns:
            List of violation dicts. Empty list means compliant.
        """
        standards = self._load_standards()
        allowed = standards.allowed_regions
        violations: list[dict[str, Any]] = []

        if not allowed:
            return violations

        all_allowed = allowed.get("all_allowed", [])
        if all_allowed and region not in all_allowed:
            violations.append(
                {
                    "rule": "region_not_allowed",
                    "message": f"Region '{region}' is not in allowed list: {all_allowed}",
                    "severity": "error",
                }
            )

        restricted = allowed.get("restricted", [])
        for restriction in restricted:
            excluded = restriction.get("excluded_regions", [])
            if region in excluded:
                violations.append(
                    {
                        "rule": "region_restricted",
                        "message": f"Region '{region}' is restricted: {restriction.get('reason', 'N/A')}",
                        "severity": "error",
                    }
                )

        return violations

    def validate_tags(
        self,
        tags: dict[str, str],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Validate resource tags against required tag standards.

        Args:
            tags: Dictionary of tag key-value pairs on the resource.

        Returns:
            Tuple of (violations, warnings). Violations are for mandatory tags,
            warnings are for recommended tags.
        """
        standards = self._load_standards()
        required = standards.required_tags
        violations: list[dict[str, Any]] = []
        warnings: list[dict[str, Any]] = []

        if not required:
            return violations, warnings

        mandatory = required.get("mandatory", [])
        for tag_spec in mandatory:
            key = tag_spec["key"]
            if key not in tags:
                violations.append(
                    {
                        "rule": "missing_mandatory_tag",
                        "message": f"Missing mandatory tag: '{key}' — {tag_spec.get('description', '')}",
                        "severity": "error",
                        "tag_key": key,
                    }
                )
                continue

            value = tags[key]
            allowed_values = tag_spec.get("allowed_values")
            if allowed_values and value not in allowed_values:
                violations.append(
                    {
                        "rule": "invalid_tag_value",
                        "message": f"Tag '{key}' has invalid value '{value}'. Allowed: {allowed_values}",
                        "severity": "error",
                        "tag_key": key,
                    }
                )

            tag_pattern = tag_spec.get("pattern")
            if tag_pattern and not re.match(tag_pattern, value):
                violations.append(
                    {
                        "rule": "invalid_tag_pattern",
                        "message": f"Tag '{key}' value '{value}' does not match pattern '{tag_pattern}'",
                        "severity": "error",
                        "tag_key": key,
                    }
                )

        recommended = required.get("recommended", [])
        for tag_spec in recommended:
            key = tag_spec["key"]
            if key not in tags:
                warnings.append(
                    {
                        "rule": "missing_recommended_tag",
                        "message": f"Missing recommended tag: '{key}' — {tag_spec.get('description', '')}",
                        "severity": "warning",
                        "tag_key": key,
                    }
                )

        return violations, warnings

    def validate_sku(self, resource_type: str, sku: str) -> list[dict[str, Any]]:
        """Validate a resource SKU against restrictions.

        Args:
            resource_type: The Azure resource type category (e.g., 'virtual_machines').
            sku: The SKU name to validate.

        Returns:
            List of violation dicts. Empty list means compliant.
        """
        standards = self._load_standards()
        restrictions = standards.sku_restrictions
        violations: list[dict[str, Any]] = []

        if not restrictions:
            return violations

        type_restrictions = restrictions.get(resource_type, {})
        if not type_restrictions:
            return violations

        blocked = (
            type_restrictions.get("blocked_skus", [])
            + type_restrictions.get("blocked_tiers", [])
            + type_restrictions.get("blocked_redundancy", [])
        )
        for blocked_item in blocked:
            if blocked_item.lower() in sku.lower():
                violations.append(
                    {
                        "rule": "blocked_sku",
                        "message": (
                            f"SKU '{sku}' is blocked for {resource_type}: "
                            f"{type_restrictions.get('reason', 'N/A')}"
                        ),
                        "severity": "error",
                    }
                )
                break

        return violations

    def validate_resource(
        self,
        resource_id: str,
        resource_name: str,
        resource_type: str,
        region: str = "",
        tags: dict[str, str] | None = None,
        sku: str = "",
    ) -> ValidationResult:
        """Validate a resource against all provisioning standards.

        Args:
            resource_id: Azure resource ID.
            resource_name: Resource display name.
            resource_type: Azure resource type.
            region: Azure region/location.
            tags: Resource tag dictionary.
            sku: Resource SKU name.

        Returns:
            ValidationResult with all violations and warnings.
        """
        result = ValidationResult(
            resource_id=resource_id,
            resource_name=resource_name,
            resource_type=resource_type,
        )

        # Validate naming
        name_violations = self.validate_resource_name(resource_name)
        result.violations.extend(name_violations)

        # Validate region
        if region:
            region_violations = self.validate_region(region)
            result.violations.extend(region_violations)

        # Validate tags
        if tags is not None:
            tag_violations, tag_warnings = self.validate_tags(tags)
            result.violations.extend(tag_violations)
            result.warnings.extend(tag_warnings)

        # Validate SKU
        if sku:
            sku_type = self._map_resource_type_to_sku_category(resource_type)
            if sku_type:
                sku_violations = self.validate_sku(sku_type, sku)
                result.violations.extend(sku_violations)

        result.is_compliant = len(result.violations) == 0
        return result

    def generate_summary(
        self,
        results: list[ValidationResult],
    ) -> ProvisioningStandardsSummary:
        """Generate a summary from a list of validation results.

        Args:
            results: List of ValidationResult objects.

        Returns:
            ProvisioningStandardsSummary with aggregate metrics.
        """
        total = len(results)
        compliant = sum(1 for r in results if r.is_compliant)
        non_compliant = total - compliant

        violation_breakdown: dict[str, int] = {}
        for r in results:
            for v in r.violations:
                rule = v.get("rule", "unknown")
                violation_breakdown[rule] = violation_breakdown.get(rule, 0) + 1

        top_violations = sorted(
            [{"rule": k, "count": v} for k, v in violation_breakdown.items()],
            key=lambda x: x["count"],
            reverse=True,
        )[:10]

        return ProvisioningStandardsSummary(
            total_resources=total,
            compliant_resources=compliant,
            non_compliant_resources=non_compliant,
            compliance_percentage=round(compliant / total * 100, 2) if total > 0 else 0.0,
            violation_breakdown=violation_breakdown,
            top_violations=top_violations,
        )

    @staticmethod
    def _map_resource_type_to_sku_category(resource_type: str) -> str | None:
        """Map an Azure resource type to a SKU restriction category."""
        mapping = {
            "microsoft.compute/virtualmachines": "virtual_machines",
            "microsoft.storage/storageaccounts": "storage_accounts",
            "microsoft.web/serverfarms": "app_service_plans",
        }
        return mapping.get(resource_type.lower())


# Singleton
_provisioning_standards_service: ProvisioningStandardsService | None = None


def get_provisioning_standards_service() -> ProvisioningStandardsService:
    """Get the ProvisioningStandardsService singleton instance."""
    global _provisioning_standards_service
    if _provisioning_standards_service is None:
        _provisioning_standards_service = ProvisioningStandardsService()
    return _provisioning_standards_service
