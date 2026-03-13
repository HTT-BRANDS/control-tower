"""Riverside Company test data fixtures.

Comprehensive test data for Riverside Company's 5 tenants:
- HTT (Headquarters)
- BCC (Beach Cities Cloud)
- FN (First Nations)
- TLL (Tenant Label)
- DCE (Standalone - DCE Office)

All data relates to the July 8, 2026 compliance deadline with $4M financial risk.
"""

from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.models.riverside import (
    RequirementCategory,
    RequirementPriority,
    RequirementStatus,
    RiversideCompliance,
    RiversideDeviceCompliance,
    RiversideMFA,
    RiversideRequirement,
    RiversideThreatData,
)
from app.models.tenant import Tenant

# =============================================================================
# TENANT CONFIGURATION
# =============================================================================

RIVERSIDE_TENANTS: list[dict[str, Any]] = [
    {
        "id": "11111111-1111-1111-1111-111111111111",
        "name": "HTT",
        "tenant_id": "htt-tenant-001",
        "description": "Headquarters - Main corporate tenant",
        "is_active": True,
        "use_lighthouse": True,
    },
    {
        "id": "22222222-2222-2222-2222-222222222222",
        "name": "BCC",
        "tenant_id": "bcc-tenant-002",
        "description": "Beach Cities Cloud - Regional operations",
        "is_active": True,
        "use_lighthouse": True,
    },
    {
        "id": "33333333-3333-3333-3333-333333333333",
        "name": "FN",
        "tenant_id": "fn-tenant-003",
        "description": "First Nations - Indigenous community services",
        "is_active": True,
        "use_lighthouse": True,
    },
    {
        "id": "44444444-4444-4444-4444-444444444444",
        "name": "TLL",
        "tenant_id": "tll-tenant-004",
        "description": "Tenant Label - Specialized division",
        "is_active": True,
        "use_lighthouse": True,
    },
    {
        "id": "55555555-5555-5555-5555-555555555555",
        "name": "DCE",
        "tenant_id": "dce-tenant-005",
        "description": "DCE Office - Standalone administrative tenant",
        "is_active": True,
        "use_lighthouse": False,  # Standalone, no Lighthouse
    },
]

# =============================================================================
# REQUIREMENT DEFINITIONS
# =============================================================================

RIVERSIDE_REQUIREMENTS: list[dict[str, Any]] = [
    # IAM Requirements (P0 - Critical)
    {
        "requirement_id": "IAM-001",
        "title": "Admin MFA Enforcement",
        "description": "Require multi-factor authentication for all administrative accounts",
        "category": RequirementCategory.IAM,
        "priority": RequirementPriority.P0,
    },
    {
        "requirement_id": "IAM-002",
        "title": "MFA for All Users",
        "description": "Enforce MFA for all user accounts accessing corporate resources",
        "category": RequirementCategory.IAM,
        "priority": RequirementPriority.P0,
    },
    {
        "requirement_id": "IAM-003",
        "title": "Privileged Access Management",
        "description": "Deploy PAM solution for privileged account management",
        "category": RequirementCategory.IAM,
        "priority": RequirementPriority.P0,
    },
    {
        "requirement_id": "IAM-004",
        "title": "Password Policy Enhancement",
        "description": "Implement strong password policies with complexity requirements",
        "category": RequirementCategory.IAM,
        "priority": RequirementPriority.P0,
    },
    {
        "requirement_id": "IAM-005",
        "title": "Identity Protection",
        "description": "Enable Azure AD Identity Protection for risk-based policies",
        "category": RequirementCategory.IAM,
        "priority": RequirementPriority.P0,
    },
    {
        "requirement_id": "IAM-006",
        "title": "Conditional Access Policies",
        "description": "Implement risk-based conditional access policies",
        "category": RequirementCategory.IAM,
        "priority": RequirementPriority.P1,
    },
    {
        "requirement_id": "IAM-007",
        "title": "Access Reviews",
        "description": "Quarterly access reviews for all privileged roles",
        "category": RequirementCategory.IAM,
        "priority": RequirementPriority.P1,
    },
    {
        "requirement_id": "IAM-008",
        "title": "Service Account Governance",
        "description": "Inventory and secure all service accounts",
        "category": RequirementCategory.IAM,
        "priority": RequirementPriority.P1,
    },
    # Group Security Requirements (P0)
    {
        "requirement_id": "RC-001",
        "title": "Group Naming Convention",
        "description": "Implement standardized naming conventions for all security groups",
        "category": RequirementCategory.GS,
        "priority": RequirementPriority.P0,
    },
    {
        "requirement_id": "RC-002",
        "title": "Dynamic Group Membership",
        "description": "Implement dynamic group membership based on attributes",
        "category": RequirementCategory.GS,
        "priority": RequirementPriority.P0,
    },
    {
        "requirement_id": "RC-003",
        "title": "Privileged Group Protection",
        "description": "Protect privileged groups with PIM and approval workflows",
        "category": RequirementCategory.GS,
        "priority": RequirementPriority.P0,
    },
    {
        "requirement_id": "RC-004",
        "title": "Guest Access Controls",
        "description": "Implement guest access lifecycle management",
        "category": RequirementCategory.GS,
        "priority": RequirementPriority.P1,
    },
    {
        "requirement_id": "RC-005",
        "title": "Group-Based Licensing",
        "description": "Implement group-based licensing for all users",
        "category": RequirementCategory.GS,
        "priority": RequirementPriority.P1,
    },
    # Domain Security Requirements (P0)
    {
        "requirement_id": "RC-006",
        "title": "Custom Domain Verification",
        "description": "Verify and secure all custom domains",
        "category": RequirementCategory.DS,
        "priority": RequirementPriority.P0,
    },
    {
        "requirement_id": "RC-007",
        "title": "DNS Security Configuration",
        "description": "Implement DNS security records (SPF, DKIM, DMARC)",
        "category": RequirementCategory.DS,
        "priority": RequirementPriority.P0,
    },
    {
        "requirement_id": "RC-008",
        "title": "Domain Federation Security",
        "description": "Review and secure federation trust relationships",
        "category": RequirementCategory.DS,
        "priority": RequirementPriority.P0,
    },
    {
        "requirement_id": "RC-009",
        "title": "Email Authentication",
        "description": "Implement comprehensive email authentication policies",
        "category": RequirementCategory.DS,
        "priority": RequirementPriority.P1,
    },
    {
        "requirement_id": "RC-010",
        "title": "Domain Monitoring",
        "description": "Monitor for domain impersonation and typosquatting",
        "category": RequirementCategory.DS,
        "priority": RequirementPriority.P2,
    },
]

# =============================================================================
# COMPLIANCE DATA CONFIGURATION (per tenant)
# =============================================================================

TENANT_COMPLIANCE_CONFIG: dict[str, dict[str, Any]] = {
    "HTT": {
        "overall_maturity_score": 2.8,
        "target_maturity_score": 3.0,
        "critical_gaps_count": 3,
        "requirements_completed": 12,
        "requirements_total": 18,
    },
    "BCC": {
        "overall_maturity_score": 2.5,
        "target_maturity_score": 3.0,
        "critical_gaps_count": 5,
        "requirements_completed": 10,
        "requirements_total": 18,
    },
    "FN": {
        "overall_maturity_score": 2.2,
        "target_maturity_score": 3.0,
        "critical_gaps_count": 7,
        "requirements_completed": 8,
        "requirements_total": 18,
    },
    "TLL": {
        "overall_maturity_score": 2.6,
        "target_maturity_score": 3.0,
        "critical_gaps_count": 4,
        "requirements_completed": 11,
        "requirements_total": 18,
    },
    "DCE": {
        "overall_maturity_score": 1.9,
        "target_maturity_score": 3.0,
        "critical_gaps_count": 8,
        "requirements_completed": 6,
        "requirements_total": 18,
    },
}

# =============================================================================
# MFA DATA CONFIGURATION (per tenant)
# =============================================================================

TENANT_MFA_CONFIG: dict[str, dict[str, Any]] = {
    "HTT": {
        "total_users": 450,
        "mfa_enrolled_users": 380,
        "admin_accounts_total": 25,
        "admin_accounts_mfa": 25,  # 100% admin MFA
    },
    "BCC": {
        "total_users": 320,
        "mfa_enrolled_users": 240,
        "admin_accounts_total": 18,
        "admin_accounts_mfa": 16,  # 89% admin MFA
    },
    "FN": {
        "total_users": 180,
        "mfa_enrolled_users": 120,
        "admin_accounts_total": 12,
        "admin_accounts_mfa": 10,  # 83% admin MFA
    },
    "TLL": {
        "total_users": 280,
        "mfa_enrolled_users": 220,
        "admin_accounts_total": 15,
        "admin_accounts_mfa": 15,  # 100% admin MFA
    },
    "DCE": {
        "total_users": 85,
        "mfa_enrolled_users": 45,
        "admin_accounts_total": 6,
        "admin_accounts_mfa": 4,  # 67% admin MFA
    },
}

# =============================================================================
# DEVICE COMPLIANCE CONFIGURATION (per tenant)
# =============================================================================

TENANT_DEVICE_CONFIG: dict[str, dict[str, Any]] = {
    "HTT": {
        "total_devices": 520,
        "mdm_enrolled": 480,
        "edr_covered": 500,
        "encrypted_devices": 475,
        "compliant_devices": 455,
    },
    "BCC": {
        "total_devices": 380,
        "mdm_enrolled": 320,
        "edr_covered": 350,
        "encrypted_devices": 310,
        "compliant_devices": 295,
    },
    "FN": {
        "total_devices": 210,
        "mdm_enrolled": 165,
        "edr_covered": 180,
        "encrypted_devices": 160,
        "compliant_devices": 145,
    },
    "TLL": {
        "total_devices": 340,
        "mdm_enrolled": 300,
        "edr_covered": 320,
        "encrypted_devices": 295,
        "compliant_devices": 280,
    },
    "DCE": {
        "total_devices": 95,
        "mdm_enrolled": 65,
        "edr_covered": 70,
        "encrypted_devices": 60,
        "compliant_devices": 52,
    },
}

# =============================================================================
# THREAT DATA CONFIGURATION (per tenant)
# =============================================================================

TENANT_THREAT_CONFIG: dict[str, dict[str, Any]] = {
    "HTT": {
        "threat_score": 28.5,
        "vulnerability_count": 12,
        "malicious_domain_alerts": 2,
        "peer_comparison_percentile": 72,
    },
    "BCC": {
        "threat_score": 35.2,
        "vulnerability_count": 18,
        "malicious_domain_alerts": 4,
        "peer_comparison_percentile": 58,
    },
    "FN": {
        "threat_score": 42.8,
        "vulnerability_count": 25,
        "malicious_domain_alerts": 6,
        "peer_comparison_percentile": 45,
    },
    "TLL": {
        "threat_score": 31.0,
        "vulnerability_count": 15,
        "malicious_domain_alerts": 3,
        "peer_comparison_percentile": 65,
    },
    "DCE": {
        "threat_score": 48.5,
        "vulnerability_count": 32,
        "malicious_domain_alerts": 8,
        "peer_comparison_percentile": 38,
    },
}

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def _calculate_mfa_percentages(config: dict[str, Any]) -> dict[str, Any]:
    """Calculate MFA coverage percentages."""
    total_users = config["total_users"]
    mfa_enrolled = config["mfa_enrolled_users"]
    admin_total = config["admin_accounts_total"]
    admin_mfa = config["admin_accounts_mfa"]

    return {
        "mfa_coverage_percentage": round((mfa_enrolled / total_users * 100), 2)
        if total_users > 0
        else 0.0,
        "admin_mfa_percentage": round((admin_mfa / admin_total * 100), 2)
        if admin_total > 0
        else 0.0,
        "unprotected_users": total_users - mfa_enrolled,
    }


def _calculate_device_percentage(config: dict[str, Any]) -> float:
    """Calculate device compliance percentage."""
    total = config["total_devices"]
    compliant = config["compliant_devices"]
    return round((compliant / total * 100), 2) if total > 0 else 0.0


def _get_requirement_status(tenant_name: str, req_index: int, total_reqs: int) -> RequirementStatus:
    """Determine requirement status based on tenant maturity and index."""
    maturity = TENANT_COMPLIANCE_CONFIG[tenant_name]["overall_maturity_score"]
    completed = TENANT_COMPLIANCE_CONFIG[tenant_name]["requirements_completed"]

    # Distribute completed requirements across the list
    if req_index < completed:
        # Some completed, some in progress based on maturity
        if req_index < completed - 2:
            return RequirementStatus.COMPLETED
        else:
            return RequirementStatus.IN_PROGRESS
    elif req_index == completed:
        return RequirementStatus.IN_PROGRESS
    elif maturity < 2.0 and req_index > completed + 3:
        return RequirementStatus.BLOCKED
    else:
        return RequirementStatus.NOT_STARTED


def _get_requirement_owner(category: RequirementCategory) -> str:
    """Get owner based on requirement category."""
    owners = {
        RequirementCategory.IAM: "Alice Johnson (Identity Team)",
        RequirementCategory.GS: "Bob Smith (Security Team)",
        RequirementCategory.DS: "Carol Williams (Infrastructure Team)",
    }
    return owners.get(category, "Security Operations Team")


# =============================================================================
# MAIN FIXTURE CREATION FUNCTIONS
# =============================================================================


def create_riverside_tenants(db: Session) -> dict[str, Tenant]:
    """Create Riverside tenant records.

    Args:
        db: Database session

    Returns:
        Dictionary mapping tenant names to Tenant objects
    """
    tenants: dict[str, Tenant] = {}

    for tenant_data in RIVERSIDE_TENANTS:
        tenant = Tenant(**tenant_data)
        db.add(tenant)
        tenants[tenant_data["name"]] = tenant

    db.commit()
    return tenants


def create_riverside_compliance_data(db: Session, tenants: dict[str, Tenant]) -> None:
    """Create Riverside compliance records.

    Args:
        db: Database session
        tenants: Dictionary of tenant name to Tenant objects
    """
    deadline = date(2026, 7, 8)
    assessment_date = datetime(2025, 1, 15, 10, 0, 0)

    for tenant_name, config in TENANT_COMPLIANCE_CONFIG.items():
        tenant = tenants[tenant_name]

        compliance = RiversideCompliance(
            tenant_id=tenant.id,
            overall_maturity_score=config["overall_maturity_score"],
            target_maturity_score=config["target_maturity_score"],
            deadline_date=deadline,
            financial_risk="$4M",
            critical_gaps_count=config["critical_gaps_count"],
            requirements_completed=config["requirements_completed"],
            requirements_total=config["requirements_total"],
            last_assessment_date=assessment_date,
        )
        db.add(compliance)

    db.commit()


def create_riverside_mfa_data(db: Session, tenants: dict[str, Tenant]) -> None:
    """Create Riverside MFA tracking records.

    Args:
        db: Database session
        tenants: Dictionary of tenant name to Tenant objects
    """
    snapshot_date = datetime(2025, 1, 15, 0, 0, 0)

    for tenant_name, config in TENANT_MFA_CONFIG.items():
        tenant = tenants[tenant_name]
        percentages = _calculate_mfa_percentages(config)

        mfa = RiversideMFA(
            tenant_id=tenant.id,
            total_users=config["total_users"],
            mfa_enrolled_users=config["mfa_enrolled_users"],
            mfa_coverage_percentage=percentages["mfa_coverage_percentage"],
            admin_accounts_total=config["admin_accounts_total"],
            admin_accounts_mfa=config["admin_accounts_mfa"],
            admin_mfa_percentage=percentages["admin_mfa_percentage"],
            unprotected_users=percentages["unprotected_users"],
            snapshot_date=snapshot_date,
        )
        db.add(mfa)

    db.commit()


def create_riverside_requirements(db: Session, tenants: dict[str, Tenant]) -> None:
    """Create Riverside requirement records.

    Args:
        db: Database session
        tenants: Dictionary of tenant name to Tenant objects
    """
    deadline = date(2026, 7, 8)
    total_reqs = len(RIVERSIDE_REQUIREMENTS)

    for tenant_name, tenant in tenants.items():
        for idx, req_def in enumerate(RIVERSIDE_REQUIREMENTS):
            status = _get_requirement_status(tenant_name, idx, total_reqs)

            # Calculate completed date if status is completed
            completed_date = None
            if status == RequirementStatus.COMPLETED:
                # Completed between 30-90 days ago
                days_ago = 30 + (idx * 5) % 60
                completed_date = deadline - timedelta(days=180 + days_ago)

            # Set due date based on priority
            if req_def["priority"] == RequirementPriority.P0:
                due_date = deadline - timedelta(days=90)  # Due 3 months before
            elif req_def["priority"] == RequirementPriority.P1:
                due_date = deadline - timedelta(days=30)  # Due 1 month before
            else:
                due_date = deadline  # Due on deadline

            requirement = RiversideRequirement(
                tenant_id=tenant.id,
                requirement_id=req_def["requirement_id"],
                title=req_def["title"],
                description=req_def["description"],
                category=req_def["category"].value,
                priority=req_def["priority"].value,
                status=status.value,
                evidence_url=None
                if status != RequirementStatus.COMPLETED
                else f"https://evidence.riverside.local/{req_def['requirement_id'].lower()}",
                evidence_notes=None
                if status != RequirementStatus.COMPLETED
                else f"Completed verification for {req_def['title']}",
                due_date=due_date,
                completed_date=completed_date,
                owner=_get_requirement_owner(req_def["category"]),
            )
            db.add(requirement)

    db.commit()


def create_riverside_device_compliance(db: Session, tenants: dict[str, Tenant]) -> None:
    """Create Riverside device compliance records.

    Args:
        db: Database session
        tenants: Dictionary of tenant name to Tenant objects
    """
    snapshot_date = datetime(2025, 1, 15, 0, 0, 0)

    for tenant_name, config in TENANT_DEVICE_CONFIG.items():
        tenant = tenants[tenant_name]
        compliance_pct = _calculate_device_percentage(config)

        device = RiversideDeviceCompliance(
            tenant_id=tenant.id,
            total_devices=config["total_devices"],
            mdm_enrolled=config["mdm_enrolled"],
            edr_covered=config["edr_covered"],
            encrypted_devices=config["encrypted_devices"],
            compliant_devices=config["compliant_devices"],
            compliance_percentage=compliance_pct,
            snapshot_date=snapshot_date,
        )
        db.add(device)

    db.commit()


def create_riverside_threat_data(db: Session, tenants: dict[str, Tenant]) -> None:
    """Create Riverside threat data records.

    Args:
        db: Database session
        tenants: Dictionary of tenant name to Tenant objects
    """
    snapshot_date = datetime(2025, 1, 15, 0, 0, 0)

    for tenant_name, config in TENANT_THREAT_CONFIG.items():
        tenant = tenants[tenant_name]

        threat = RiversideThreatData(
            tenant_id=tenant.id,
            threat_score=config["threat_score"],
            vulnerability_count=config["vulnerability_count"],
            malicious_domain_alerts=config["malicious_domain_alerts"],
            peer_comparison_percentile=config["peer_comparison_percentile"],
            snapshot_date=snapshot_date,
        )
        db.add(threat)

    db.commit()


def create_riverside_test_data(db: Session) -> dict[str, Tenant]:
    """Create all Riverside test data fixtures.

    This function creates complete test data for all 5 Riverside tenants:
    - HTT (Headquarters)
    - BCC (Beach Cities Cloud)
    - FN (First Nations)
    - TLL (Tenant Label)
    - DCE (Standalone - DCE Office)

    Data includes:
    - Tenant records
    - Compliance maturity tracking
    - MFA enrollment statistics
    - Requirements (IAM-001 to IAM-008, RC-001 to RC-010)
    - Device compliance metrics
    - Threat intelligence data

    Args:
        db: Database session

    Returns:
        Dictionary mapping tenant names to Tenant objects

    Example:
        >>> tenants = create_riverside_test_data(db)
        >>> print(tenants["HTT"].name)
        'HTT'
    """
    # Create tenants first
    tenants = create_riverside_tenants(db)

    # Create all compliance-related data
    create_riverside_compliance_data(db, tenants)
    create_riverside_mfa_data(db, tenants)
    create_riverside_requirements(db, tenants)
    create_riverside_device_compliance(db, tenants)
    create_riverside_threat_data(db, tenants)

    return tenants


def clear_riverside_test_data(db: Session) -> None:
    """Clear all Riverside test data from the database.

    Removes all records created by create_riverside_test_data() in the
    correct order to respect foreign key constraints.

    Args:
        db: Database session

    Example:
        >>> clear_riverside_test_data(db)
        >>> # All Riverside data is now removed
    """
    # Delete in reverse order of dependencies
    db.query(RiversideThreatData).delete(synchronize_session=False)
    db.query(RiversideDeviceCompliance).delete(synchronize_session=False)
    db.query(RiversideRequirement).delete(synchronize_session=False)
    db.query(RiversideMFA).delete(synchronize_session=False)
    db.query(RiversideCompliance).delete(synchronize_session=False)

    # Delete tenants last
    tenant_ids = [t["id"] for t in RIVERSIDE_TENANTS]
    db.query(Tenant).filter(Tenant.id.in_(tenant_ids)).delete(synchronize_session=False)

    db.commit()


# =============================================================================
# FIXTURE STATISTICS
# =============================================================================


def get_fixture_statistics() -> dict[str, Any]:
    """Get statistics about the fixtures.

    Returns:
        Dictionary with fixture counts and configuration details
    """
    return {
        "tenants": {
            "count": len(RIVERSIDE_TENANTS),
            "names": [t["name"] for t in RIVERSIDE_TENANTS],
        },
        "requirements": {
            "count": len(RIVERSIDE_REQUIREMENTS),
            "by_category": {
                "IAM": len(
                    [r for r in RIVERSIDE_REQUIREMENTS if r["category"] == RequirementCategory.IAM]
                ),
                "GS": len(
                    [r for r in RIVERSIDE_REQUIREMENTS if r["category"] == RequirementCategory.GS]
                ),
                "DS": len(
                    [r for r in RIVERSIDE_REQUIREMENTS if r["category"] == RequirementCategory.DS]
                ),
            },
            "by_priority": {
                "P0": len(
                    [r for r in RIVERSIDE_REQUIREMENTS if r["priority"] == RequirementPriority.P0]
                ),
                "P1": len(
                    [r for r in RIVERSIDE_REQUIREMENTS if r["priority"] == RequirementPriority.P1]
                ),
                "P2": len(
                    [r for r in RIVERSIDE_REQUIREMENTS if r["priority"] == RequirementPriority.P2]
                ),
            },
        },
        "total_records_per_tenant": {
            "compliance": 1,
            "mfa": 1,
            "requirements": len(RIVERSIDE_REQUIREMENTS),
            "device_compliance": 1,
            "threat_data": 1,
        },
        "deadline": "2026-07-08",
        "financial_risk": "$4M",
    }
