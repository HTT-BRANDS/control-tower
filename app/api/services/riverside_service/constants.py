"""Riverside Service - Constants and configuration."""

from datetime import date
from enum import Enum

# Critical deadline - July 8, 2026
RIVERSIDE_DEADLINE = date(2026, 7, 8)
FINANCIAL_RISK = "$4M"

# Target maturity score
TARGET_MATURITY_SCORE = 3.0
CURRENT_MATURITY_SCORE = 2.4


class RequirementLevel(Enum):
    """Maturity levels for security requirements."""

    EMERGING = "Emerging"
    DEVELOPING = "Developing"
    MATURE = "Mature"
    LEADING = "Leading"


class MFAStatus(Enum):
    """MFA enforcement status for users."""

    ENFORCED = "Enforced"
    AVAILABLE = "Available"
    PENDING = "Pending"
    NOT_CONFIGURED = "Not Configured"


class RequirementStatus(Enum):
    """Implementation status of security requirements."""

    NOT_STARTED = "Not Started"
    IN_PROGRESS = "In Progress"
    COMPLETED = "Completed"
    AT_RISK = "At Risk"


class DeadlinePhase(Enum):
    """Implementation phases for Riverside requirements."""

    PHASE_1_Q3_2025 = "Phase 1: Q3 2025"
    PHASE_2_Q4_2025 = "Phase 2: Q4 2025"
    PHASE_3_Q1_2026 = "Phase 3: Q1 2026"


class RiversideRequirementCategory(Enum):
    """Categories of Riverside security requirements."""

    MFA_ENFORCEMENT = "MFA Enforcement"
    CONDITIONAL_ACCESS = "Conditional Access"
    PRIVILEGED_ACCESS = "Privileged Access"
    DEVICE_COMPLIANCE = "Device Compliance"
    THREAT_MANAGEMENT = "Threat Management"
    DATA_LOSS_PREVENTION = "Data Loss Prevention"
    LOGGING_MONITORING = "Logging & Monitoring"
    INCIDENT_RESPONSE = "Incident Response"


# Threshold percentages for maturity levels
MFA_THRESHOLD_PERCENTAGES = {
    "Emerging": 25,
    "Developing": 50,
    "Mature": 75,
    "Leading": 95,
}

# Service Tenant configurations — keys are UPPERCASE brand codes,
# values must match Tenant.name exactly in the database.
RIVERSIDE_TENANTS = {
    "HTT": "Head-To-Toe (HTT)",
    "BCC": "Bishops (BCC)",
    "FN": "Frenchies (FN)",
    "TLL": "Lash Lounge (TLL)",
}

# Include DCE for tracking but it's not a Riverside compliance tenant
ALL_TENANTS = {
    **RIVERSIDE_TENANTS,
    "DCE": "Delta Crown (DCE)",
}

# Admin role IDs for tracking
ADMIN_ROLE_IDS = [
    "62e90394-69f5-4237-9190-012177145e10",  # Global Admin
    "194ae4cb-b126-40b2-bd5b-6091b380977d",  # Security Admin
    "f28a1f50-f6e7-4571-818b-6a12f2af6b6c",  # Exchange Admin
    "f2ef992c-3afb-46b9-b7cf-a126ee74c451",  # SharePoint Admin
]

# Sync configuration
RIVERSIDE_SYNC_INTERVAL_HOURS = 4
