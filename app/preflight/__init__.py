"""Preflight check module for Azure Governance Platform.

This module provides comprehensive preflight checks for validating Azure
tenant connectivity, permissions, and API access before operations.

Two API styles are available:

1. **Class-based checks** (for PreflightRunner integration):
   >>> from app.preflight import AzureAuthCheck, AzureSubscriptionsCheck
   >>> check = AzureAuthCheck()
   >>> result = await check.run(tenant_id="12345678-1234-1234-1234-123456789012")

2. **Function-based checks** (for direct use):
   >>> from app.preflight import check_azure_authentication, run_all_azure_checks
   >>> results = await run_all_azure_checks("12345678-1234-1234-1234-123456789012")

Multi-tenant orchestration:
   >>> from app.preflight import check_all_tenants
   >>> all_results = await check_all_tenants()

Riverside checks:
   >>> from app.preflight import RiversideDatabaseCheck, run_all_riverside_checks
   >>> results = await run_all_riverside_checks()
"""

# Base and models
# Class-based Azure checks
# Function-based Azure checks
from app.preflight.azure_checks import (
    AzureAuthCheck,
    AzureCostManagementCheck,
    AzureGraphCheck,
    AzurePolicyCheck,
    AzureRBACCheck,
    AzureResourcesCheck,
    AzureSecurityCheck,
    AzureSubscriptionsCheck,
    check_azure_authentication,
    check_azure_subscriptions,
    check_cost_management_access,
    check_graph_api_access,
    check_policy_access,
    check_rbac_permissions,
    check_resource_manager_access,
    check_security_center_access,
    run_all_azure_checks,
)
from app.preflight.base import BasePreflightCheck
from app.preflight.models import (
    CheckCategory,
    CheckResult,
    CheckStatus,
    PreflightReport,
)

# Riverside checks
from app.preflight.riverside_checks import (
    RiversideAPIEndpointCheck,
    RiversideAzureADPermissionsCheck,
    RiversideDatabaseCheck,
    RiversideMFADataSourceCheck,
    RiversideSchedulerCheck,
    check_riverside_api_endpoints,
    check_riverside_azure_ad_permissions,
    check_riverside_database,
    check_riverside_mfa_data_source,
    check_riverside_scheduler,
    get_riverside_checks,
    run_all_riverside_checks,
)

# Tenant orchestration
from app.preflight.tenant_checks import (
    check_all_tenants,
    check_single_tenant,
    check_tenant_connectivity,
    check_tenants_quick,
    format_check_results,
)

__all__ = [
    # Base classes
    "BasePreflightCheck",
    # Models
    "CheckCategory",
    "CheckResult",
    "CheckStatus",
    "PreflightReport",
    # Class-based Azure checks
    "AzureAuthCheck",
    "AzureSubscriptionsCheck",
    "AzureCostManagementCheck",
    "AzureGraphCheck",
    "AzurePolicyCheck",
    "AzureResourcesCheck",
    "AzureSecurityCheck",
    "AzureRBACCheck",
    # Class-based Riverside checks
    "RiversideDatabaseCheck",
    "RiversideAPIEndpointCheck",
    "RiversideSchedulerCheck",
    "RiversideAzureADPermissionsCheck",
    "RiversideMFADataSourceCheck",
    # Function-based Azure checks
    "check_azure_authentication",
    "check_azure_subscriptions",
    "check_cost_management_access",
    "check_graph_api_access",
    "check_policy_access",
    "check_resource_manager_access",
    "check_rbac_permissions",
    "check_security_center_access",
    "run_all_azure_checks",
    # Function-based Riverside checks
    "check_riverside_database",
    "check_riverside_api_endpoints",
    "check_riverside_scheduler",
    "check_riverside_azure_ad_permissions",
    "check_riverside_mfa_data_source",
    "run_all_riverside_checks",
    "get_riverside_checks",
    # Tenant orchestration
    "check_all_tenants",
    "check_single_tenant",
    "check_tenant_connectivity",
    "check_tenants_quick",
    "format_check_results",
]
