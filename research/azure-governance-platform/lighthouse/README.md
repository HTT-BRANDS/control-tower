# Azure Lighthouse Integration Research

**Research Date:** 2025-03-02
**Topic:** Multi-tenant management for Azure Governance Platforms

---

## Executive Summary

Azure Lighthouse enables multi-tenant management by allowing service providers to manage customer Azure resources from their own tenant. This is the recommended approach for the Azure Governance Platform, eliminating the need for per-tenant credential management.

### Key Findings

1. **Lighthouse is the Gold Standard**: Microsoft-recommended for MSPs and governance platforms
2. **No Credential Storage**: Customer tenants delegate access, no secrets stored
3. **Unified Security**: Service provider controls access policies
4. **Cost Visibility**: Cross-tenant cost aggregation supported
5. **JIT Access**: Privileged Identity Integration for elevated permissions

---

## 1. Azure Lighthouse Architecture

### 1.1 Core Concepts

```
┌─────────────────────────────────────────────────────────────────────┐
│                    SERVICE PROVIDER TENANT                           │
│  (Your Azure AD - Azure Governance Platform)                         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │              Azure Governance Platform                         │  │
│  │                                                                │  │
│  │  ┌─────────────────┐    ┌──────────────────────────────┐     │  │
│  │  │  App Service    │───▶│  Managed Identity            │     │  │
│  │  │  (FastAPI)      │    │  (No credentials stored)     │     │  │
│  │  └─────────────────┘    └──────────────────────────────┘     │  │
│  │           │                                    │               │  │
│  │           ▼                                    ▼               │  │
│  │  ┌─────────────────────────────────────────────────────────┐  │  │
│  │  │              Azure APIs (ARM, Graph, Cost)               │  │  │
│  │  │              ↓ Calls made via Lighthouse delegation      │  │  │
│  │  └─────────────────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                     ┌──────────────┼──────────────┐
                     │              │              │
        ┌────────────▼────┐  ┌─────▼──────┐  ┌────▼─────┐
        │  Delegated Sub  │  │ Delegated  │  │Delegated │
        │  (Reader Role)  │  │  Sub       │  │   Sub    │
        │                 │  │ (Reader)   │  │ (Reader) │
        │  Customer A     │  │ Customer B │  │Customer C│
        │  Tenant         │  │  Tenant    │  │  Tenant  │
        └─────────────────┘  └────────────┘  └──────────┘
```

### 1.2 Delegation Components

| Component | Purpose | Managed By |
|-----------|---------|------------|
| **Managed Service Offer** | Defines what you offer | Service Provider |
| **Registration Definition** | Maps roles to customer subscriptions | Service Provider |
| **Registration Assignment** | Customer accepts the offer | Customer |
| **Service Principal** | Identity used for delegated access | Azure AD |
| **Role Assignments** | RBAC permissions on customer resources | Service Provider |

---

## 2. Implementation Patterns

### Pattern 1: ARM Template Delegation (Recommended)

```json
{
  "$schema": "https://schema.management.azure.com/schemas/2019-08-01/subscriptionDeploymentTemplate.json#",
  "contentVersion": "1.0.0.0",
  "parameters": {
    "mspOfferName": {
      "type": "string",
      "defaultValue": "Azure Governance Platform"
    },
    "mspOfferDescription": {
      "type": "string",
      "defaultValue": "Multi-tenant governance and compliance management"
    },
    "managedByTenantId": {
      "type": "string",
      "defaultValue": "YOUR-SERVICE-PROVIDER-TENANT-ID"
    },
    "authorizations": {
      "type": "array",
      "defaultValue": [
        {
          "principalId": "YOUR-MANAGED-IDENTITY-OBJECT-ID",
          "principalIdDisplayName": "Governance Platform",
          "roleDefinitionId": "b24988ac-6180-42a0-ab88-20f7382dd24c",
          "roleDisplayName": "Contributor"
        },
        {
          "principalId": "YOUR-MANAGED-IDENTITY-OBJECT-ID",
          "principalIdDisplayName": "Governance Platform - Cost Management",
          "roleDefinitionId": "72fafb9e-0641-4937-9268-a91bfd8191a3",
          "roleDisplayName": "Cost Management Reader"
        },
        {
          "principalId": "YOUR-MANAGED-IDENTITY-OBJECT-ID",
          "principalIdDisplayName": "Governance Platform - Security",
          "roleDefinitionId": "39bc4728-0917-49c7-9d2c-d95423bc2eb4",
          "roleDisplayName": "Security Reader"
        }
      ]
    }
  },
  "resources": [
    {
      "type": "Microsoft.ManagedServices/registrationDefinitions",
      "apiVersion": "2022-10-01",
      "name": "[guid(parameters('mspOfferName'))]",
      "properties": {
        "registrationDefinitionName": "[parameters('mspOfferName')]",
        "description": "[parameters('mspOfferDescription')]",
        "managedByTenantId": "[parameters('managedByTenantId')]",
        "authorizations": "[parameters('authorizations')]"
      }
    },
    {
      "type": "Microsoft.ManagedServices/registrationAssignments",
      "apiVersion": "2022-10-01",
      "name": "[guid(parameters('mspOfferName'))]",
      "dependsOn": [
        "[resourceId('Microsoft.ManagedServices/registrationDefinitions', guid(parameters('mspOfferName')))]"
      ],
      "properties": {
        "registrationDefinitionId": "[resourceId('Microsoft.ManagedServices/registrationDefinitions', guid(parameters('mspOfferName')))]"
      }
    }
  ]
}
```

### Pattern 2: Marketplace Offer (For External Customers)

```
┌─────────────────────────────────────────────────────────────────┐
│              Azure Marketplace                                   │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │  Managed Service Offer                                       ││
│  │  - Logo & description                                        ││
│  │  - Pricing (if applicable)                                   ││
│  │  - ARM template reference                                    ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
                              │
              Customer browses and accepts
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    CUSTOMER TENANT                               │
│  Subscription automatically enrolled in your management          │
└─────────────────────────────────────────────────────────────────┘
```

### Pattern 3: Programmatic Onboarding

```python
# app/services/lighthouse_service.py
from azure.identity import DefaultAzureCredential
from azure.mgmt.managedservices import ManagedServicesClient
from azure.mgmt.managedservices.models import (
    RegistrationDefinition,
    RegistrationAssignment,
    Authorization
)

class LighthouseService:
    def __init__(self):
        self.credential = DefaultAzureCredential()
        
    async def create_registration_definition(
        self,
        customer_subscription_id: str,
        offer_name: str,
        managed_identity_principal_id: str
    ):
        """Create registration definition for customer onboarding"""
        
        client = ManagedServicesClient(self.credential)
        
        # Define authorizations (permissions)
        authorizations = [
            Authorization(
                principal_id=managed_identity_principal_id,
                principal_id_display_name="Governance Platform - Reader",
                role_definition_id="acdd72a7-3385-48ef-bd42-f606fba81ae7"  # Reader
            ),
            Authorization(
                principal_id=managed_identity_principal_id,
                principal_id_display_name="Governance Platform - Cost",
                role_definition_id="72fafb9e-0641-4937-9268-a91bfd8191a3"  # Cost Mgmt Reader
            ),
            Authorization(
                principal_id=managed_identity_principal_id,
                principal_id_display_name="Governance Platform - Security",
                role_definition_id="39bc4728-0917-49c7-9d2c-d95423bc2eb4"  # Security Reader
            )
        ]
        
        registration = RegistrationDefinition(
            registration_definition_name=offer_name,
            description=f"Azure Governance Platform management for {customer_subscription_id}",
            managed_by_tenant_id=self.service_provider_tenant_id,
            authorizations=authorizations
        )
        
        return client.registration_definitions.create_or_update(
            scope=f"/subscriptions/{customer_subscription_id}",
            registration_definition_id=offer_name,
            properties=registration
        )
```

---

## 3. Service Provider Access Patterns

### 3.1 Required Roles for Governance Platform

| Role | Purpose | Scope |
|------|---------|-------|
| **Reader** | Resource inventory, compliance state | Subscription |
| **Cost Management Reader** | Cost data, budgets, recommendations | Subscription |
| **Security Reader** | Secure Score, security alerts | Subscription |
| **Monitoring Reader** | Metrics, logs, diagnostics | Subscription |
| **Managed Identity Operator** | Service principal management | Subscription |

### 3.2 Role Assignment Structure

```python
# app/models/lighthouse.py
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from enum import Enum

class DelegationRole(str, Enum):
    READER = "acdd72a7-3385-48ef-bd42-f606fba81ae7"
    CONTRIBUTOR = "b24988ac-6180-42a0-ab88-20f7382dd24c"
    COST_READER = "72fafb9e-0641-4937-9268-a91bfd8191a3"
    SECURITY_READER = "39bc4728-0917-49c7-9d2c-d95423bc2eb4"
    MONITORING_READER = "43d0d8ad-25c7-4714-9337-8ba259a9fe05"

class LighthouseAuthorization(BaseModel):
    principal_id: str
    principal_display_name: str
    role_definition_id: str
    role_name: str
    delegated_role_definition_ids: Optional[List[str]] = None

class TenantDelegation(BaseModel):
    tenant_id: str
    tenant_name: str
    subscription_id: str
    subscription_name: str
    registration_definition_id: str
    registration_assignment_id: str
    authorizations: List[LighthouseAuthorization]
    onboarded_at: datetime
    last_synced_at: Optional[datetime]
    is_active: bool
```

### 3.3 Cross-Tenant API Access

```python
# app/services/azure_client.py
from azure.identity import DefaultAzureCredential
from azure.mgmt.resource import SubscriptionClient, ResourceManagementClient
from azure.mgmt.costmanagement import CostManagementClient
from azure.mgmt.security import SecurityCenter

class AzureMultiTenantClient:
    def __init__(self):
        # Uses Managed Identity in Azure, or Azure CLI locally
        self.credential = DefaultAzureCredential()
        
    async def get_delegated_subscriptions(self) -> List[Dict]:
        """Get all subscriptions accessible via Lighthouse"""
        client = SubscriptionClient(self.credential)
        
        subscriptions = []
        for sub in client.subscriptions.list():
            # Includes both home tenant and delegated subscriptions
            subscriptions.append({
                "subscription_id": sub.subscription_id,
                "display_name": sub.display_name,
                "state": sub.state,
                "tenant_id": sub.tenant_id,
                "is_delegated": self._is_delegated(sub)
            })
        
        return subscriptions
    
    async def get_cost_data(
        self,
        subscription_id: str,
        start_date: str,
        end_date: str
    ) -> Dict:
        """Get cost data for a delegated subscription"""
        
        client = CostManagementClient(self.credential)
        
        scope = f"/subscriptions/{subscription_id}"
        
        query = {
            "type": "Usage",
            "timeframe": "Custom",
            "timePeriod": {
                "from": start_date,
                "to": end_date
            },
            "dataset": {
                "granularity": "Daily",
                "aggregation": {
                    "totalCost": {
                        "name": "PreTaxCost",
                        "function": "Sum"
                    }
                },
                "grouping": [
                    {"type": "Dimension", "name": "ServiceName"},
                    {"type": "Dimension", "name": "ResourceGroup"}
                ]
            }
        }
        
        result = client.query.usage(scope, query)
        return self._parse_cost_result(result)
    
    async def get_security_score(self, subscription_id: str) -> Dict:
        """Get Azure Security Center secure score"""
        client = SecurityCenter(
            self.credential,
            subscription_id,
            asc_location="centralus"  # Required parameter
        )
        
        scores = list(client.secure_scores.list())
        return {
            "subscription_id": subscription_id,
            "secure_score": scores[0].score if scores else None,
            "max_score": scores[0].max if scores else None,
            "percentage": (scores[0].score / scores[0].max * 100) if scores else 0
        }
```

---

## 4. Security Considerations

### 4.1 Threat Model

```
┌─────────────────────────────────────────────────────────────────────┐
│                      THREAT MODEL                                    │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Threat: Unauthorized access to customer data                       │
│  Mitigation: Strict RBAC, JIT access, audit logging                 │
│                                                                      │
│  Threat: Privilege escalation in customer tenant                    │
│  Mitigation: Least privilege, no Contributor/Owner roles            │
│                                                                      │
│  Threat: Service provider tenant compromise                         │
│  Mitigation: MFA enforcement, conditional access, monitoring        │
│                                                                      │
│  Threat: Data exfiltration across tenants                           │
│  Mitigation: Data loss prevention, egress controls                  │
│                                                                      │
│  Threat: Insider threat                                             │
│  Mitigation: Audit logs, activity alerts, regular access reviews    │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 4.2 Security Best Practices

```python
# app/core/security.py
from functools import wraps
from fastapi import HTTPException, Depends
from azure.identity import DefaultAzureCredential

class LighthouseSecurity:
    def __init__(self):
        self.credential = DefaultAzureCredential()
    
    async def verify_delegation_scope(self, subscription_id: str) -> bool:
        """Verify subscription is properly delegated via Lighthouse"""
        client = SubscriptionClient(self.credential)
        
        try:
            sub = client.subscriptions.get(subscription_id)
            # Verify it's a delegated subscription
            return self._is_lighthouse_delegation(sub)
        except Exception:
            return False
    
    async def enforce_jit_access(self, subscription_id: str, action: str):
        """Enforce Just-In-Time access for privileged actions"""
        # Integration with Azure PIM
        from azure.mgmt.authorization import AuthorizationManagementClient
        
        client = AuthorizationManagementClient(
            self.credential,
            subscription_id
        )
        
        # Check for active PIM elevation
        role_assignments = list(client.role_assignments.list())
        # Verify elevated role is active
        
        return self._validate_elevation(role_assignments)

# Decorator for protected endpoints
def require_lighthouse_scope(subscription_id_param: str = "subscription_id"):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            security = LighthouseSecurity()
            sub_id = kwargs.get(subscription_id_param)
            
            if not await security.verify_delegation_scope(sub_id):
                raise HTTPException(
                    status_code=403,
                    detail="Subscription not accessible via Lighthouse delegation"
                )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator
```

### 4.3 Audit Logging

```python
# app/services/audit_service.py
from datetime import datetime
from typing import Dict, Any

class AuditService:
    def __init__(self):
        self.credential = DefaultAzureCredential()
    
    async def log_cross_tenant_access(
        self,
        customer_tenant_id: str,
        subscription_id: str,
        action: str,
        user_id: str,
        resource_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Log all cross-tenant access for compliance"""
        
        audit_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "service_provider_tenant": self.sp_tenant_id,
            "customer_tenant_id": customer_tenant_id,
            "subscription_id": subscription_id,
            "action": action,
            "user_id": user_id,
            "resource_id": resource_id,
            "metadata": metadata or {},
            "ip_address": self._get_client_ip(),
            "user_agent": self._get_user_agent()
        }
        
        # Write to audit log
        await self._write_audit_log(audit_entry)
        
        # Alert on suspicious patterns
        await self._check_suspicious_activity(audit_entry)
```

---

## 5. Cost Tracking Across Tenants

### 5.1 Multi-Tenant Cost Aggregation

```python
# app/services/cost_service.py
from azure.mgmt.costmanagement import CostManagementClient
from azure.mgmt.costmanagement.models import QueryDefinition
from typing import List, Dict
import asyncio

class MultiTenantCostService:
    def __init__(self):
        self.credential = DefaultAzureCredential()
    
    async def get_all_tenants_costs(
        self,
        start_date: str,
        end_date: str
    ) -> Dict:
        """Aggregate costs across all delegated subscriptions"""
        
        # Get all delegated subscriptions
        delegated_subs = await self._get_delegated_subscriptions()
        
        # Fetch costs in parallel
        tasks = [
            self._get_subscription_cost(sub, start_date, end_date)
            for sub in delegated_subs
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Aggregate results
        total_cost = sum(r["cost"] for r in results if not isinstance(r, Exception))
        
        return {
            "total_cost": total_cost,
            "currency": "USD",
            "start_date": start_date,
            "end_date": end_date,
            "tenant_breakdown": [
                {
                    "tenant_id": sub["tenant_id"],
                    "subscription_id": sub["subscription_id"],
                    "cost": result.get("cost", 0),
                    "currency": result.get("currency", "USD")
                }
                for sub, result in zip(delegated_subs, results)
                if not isinstance(result, Exception)
            ]
        }
    
    async def _get_subscription_cost(
        self,
        subscription: Dict,
        start_date: str,
        end_date: str
    ) -> Dict:
        """Get cost for a single subscription"""
        
        client = CostManagementClient(self.credential)
        scope = f"/subscriptions/{subscription['subscription_id']}"
        
        query = QueryDefinition(
            type="Usage",
            timeframe="Custom",
            time_period={"from": start_date, "to": end_date},
            dataset={
                "granularity": "None",
                "aggregation": {
                    "totalCost": {"name": "PreTaxCost", "function": "Sum"}
                }
            }
        )
        
        try:
            result = client.query.usage(scope, query)
            return {
                "cost": float(result.rows[0][0]) if result.rows else 0,
                "currency": result.rows[0][1] if result.rows and len(result.rows[0]) > 1 else "USD"
            }
        except Exception as e:
            logger.error(f"Failed to get cost for {subscription['subscription_id']}: {e}")
            return {"cost": 0, "currency": "USD", "error": str(e)}
```

### 5.2 Cost Allocation Tags

```python
# Track cost allocation across tenants
COST_ALLOCATION_TAGS = {
    "tenant_id": "Maps cost to specific customer tenant",
    "environment": "Production, Staging, Development",
    "cost_center": "Internal cost allocation",
    "governance_managed": "True/False - indicates Lighthouse management"
}

async def get_tagged_cost_breakdown(
    self,
    subscription_id: str,
    tag_name: str = "tenant_id"
) -> Dict:
    """Get cost breakdown by tag value"""
    
    client = CostManagementClient(self.credential)
    scope = f"/subscriptions/{subscription_id}"
    
    query = {
        "type": "Usage",
        "timeframe": "MonthToDate",
        "dataset": {
            "granularity": "None",
            "aggregation": {
                "totalCost": {"name": "PreTaxCost", "function": "Sum"}
            },
            "grouping": [
                {"type": "TagKey", "name": tag_name}
            ]
        }
    }
    
    result = client.query.usage(scope, query)
    return self._parse_tagged_results(result)
```

---

## 6. Best Practices & Recommendations

### 6.1 Onboarding Workflow

```python
# app/workflows/onboarding.py
class TenantOnboardingWorkflow:
    async def onboard_tenant(self, tenant_info: TenantOnboardingRequest):
        """
        1. Validate tenant exists
        2. Generate ARM template
        3. Create registration definition
        4. Verify access
        5. Initial data sync
        6. Send confirmation
        """
        
        # Step 1: Validate
        await self._validate_tenant(tenant_info.tenant_id)
        
        # Step 2: Generate ARM template
        arm_template = self._generate_arm_template(tenant_info)
        
        # Step 3: Create registration
        registration = await self.lighthouse_service.create_registration(
            tenant_info.subscription_id,
            arm_template
        )
        
        # Step 4: Verify access
        await self._verify_delegated_access(tenant_info.subscription_id)
        
        # Step 5: Initial sync
        await self.sync_service.sync_tenant(tenant_info.tenant_id)
        
        # Step 6: Notify
        await self.notification_service.send_onboarding_confirmation(
            tenant_info
        )
        
        return OnboardingResult(
            success=True,
            registration_id=registration.id,
            message="Tenant successfully onboarded"
        )
```

### 6.2 Access Review Schedule

| Review Type | Frequency | Responsible |
|-------------|-----------|-------------|
| **Delegated access review** | Quarterly | Customer admin |
| **Service provider role audit** | Monthly | Security team |
| **Privileged access review** | Weekly | PIM + automation |
| **Anomaly detection** | Real-time | Automated |

### 6.3 Monitoring & Alerting

```python
# Monitor for unusual cross-tenant activity
UNUSUAL_PATTERNS = {
    "high_volume_access": {
        "threshold": 1000,  # requests per hour
        "action": "alert_security_team"
    },
    "after_hours_access": {
        "time_window": "22:00-06:00",
        "action": "require_justification"
    },
    "new_resource_types": {
        "action": "log_and_review"
    }
}
```

---

## 7. Implementation Checklist

### Phase 1: Foundation
- [ ] Set up service provider tenant with proper Azure AD configuration
- [ ] Create managed identity for Governance Platform
- [ ] Document required RBAC roles
- [ ] Create ARM template for delegation

### Phase 2: Customer Onboarding
- [ ] Build customer onboarding workflow
- [ ] Create customer-facing documentation
- [ ] Set up automated verification
- [ ] Implement error handling for failed delegations

### Phase 3: Security & Compliance
- [ ] Implement audit logging
- [ ] Set up access reviews
- [ ] Configure alerts for suspicious activity
- [ ] Document security procedures

### Phase 4: Optimization
- [ ] Implement parallel API calls for performance
- [ ] Set up caching for frequently accessed data
- [ ] Optimize cost aggregation queries
- [ ] Monitor and tune API rate limits

---

## 8. Cost Implications

| Component | Cost | Notes |
|-----------|------|-------|
| **Lighthouse Delegation** | Free | No additional cost |
| **Cross-tenant API Calls** | Free | Standard ARM API rates |
| **Audit Logging** | ~$0.03/GB | Log Analytics workspace |
| **Cost Management API** | Free | Included with subscription |
| **Azure AD B2B** | Free | Included with Azure AD |

**Total Lighthouse overhead: $0-5/month** (depending on audit log volume)

---

## 9. Comparison: Lighthouse vs. Per-Tenant Auth

| Aspect | Lighthouse | Per-Tenant SP |
|--------|------------|---------------|
| **Setup Complexity** | Low (one-time ARM template) | High (per-tenant registration) |
| **Credential Management** | None (delegated) | Complex (secrets rotation) |
| **Security Posture** | Centralized, auditable | Distributed, harder to audit |
| **Onboarding Time** | Minutes | Hours-days |
| **Revocation** | Instant | Requires secret rotation |
| **Customer Perception** | Professional, modern | Legacy approach |
| **Microsoft Recommendation** | ✅ Yes | ⚠️ Legacy |
| **Cost** | Free | Free + management overhead |

**Recommendation:** Azure Lighthouse is the clear choice for this use case.

---

*Research conducted by web-puppy-318eac*
*Last Updated: 2025-03-02*
