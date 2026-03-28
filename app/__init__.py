"""Azure Multi-Tenant Governance Platform.

A lightweight, cost-effective platform for managing Azure/M365 governance
across multiple tenants with focus on cost optimization, compliance,
resource management, and identity governance.
"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("azure-governance-platform")
except PackageNotFoundError:
    # Package not installed (e.g., running from source without install)
    __version__ = "1.8.0"

__author__ = "Cloud Governance Team"
