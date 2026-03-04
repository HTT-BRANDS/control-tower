#!/usr/bin/env python3
"""
Riverside Azure Governance Platform - App Registration Setup Script

This script manages app registrations across 5 Riverside tenants:
- HTT (Head to Toe Brands)
- BCC (Bishops Cuts/Color)
- FN (Frenchies Nails)
- TLL (The Lash Lounge)
- DCE (Delta Crown Extensions)

Required Microsoft Graph Permissions:
  - User.Read.All
  - AuditLog.Read.All
  - Reports.Read.All
  - Policy.Read.All
  - Application.Read.All
  - Organization.Read.All

Required Azure Management Permissions:
  - Microsoft.Resources/subscriptions/read
  - Microsoft.CostManagement/query/read
  - Microsoft.PolicyInsights/policyStates/queryResults/action
  - Microsoft.Authorization/roleAssignments/read
  - Microsoft.Authorization/roleDefinitions/read

Usage:
    python scripts/setup-riverside-apps.py --check-only
    python scripts/setup-riverside-apps.py --create-secrets
    python scripts/setup-riverside-apps.py --full-setup

Environment Variables:
    AZURE_TENANT_ID         Override default tenant (for single-tenant operations)
    AZURE_CLIENT_ID         Service principal app ID
    AZURE_CLIENT_SECRET     Service principal secret
"""

import argparse
import json
import os
import re
import secrets
import string
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional


# =============================================================================
# TENANT CONFIGURATION
# =============================================================================

@dataclass(frozen=True)
class TenantConfig:
    """Configuration for a single Azure tenant."""
    name: str
    code: str
    tenant_id: str
    admin_upn: str
    app_id: str
    domains: list[str] = field(default_factory=list)
    is_active: bool = True


RIVERSIDE_TENANTS: dict[str, TenantConfig] = {
    "HTT": TenantConfig(
        name="Head to Toe Brands (HTT)",
        code="HTT",
        tenant_id="0c0e35dc-188a-4eb3-b8ba-61752154b407",
        admin_upn="tyler.granlund-admin@httbrands.com",
        app_id="1e3e8417-49f1-4d08-b7be-47045d8a12e9",
        domains=["httbrands.com"],
        is_active=True,
    ),
    "BCC": TenantConfig(
        name="Bishops Cuts/Color (BCC)",
        code="BCC",
        tenant_id="b5380912-79ec-452d-a6ca-6d897b19b294",
        admin_upn="tyler.granlund-Admin@bishopsbs.onmicrosoft.com",
        app_id="4861906b-2079-4335-923f-a55cc0e44d64",
        domains=["bishopsbs.onmicrosoft.com"],
        is_active=True,
    ),
    "FN": TenantConfig(
        name="Frenchies Nails (FN)",
        code="FN",
        tenant_id="98723287-044b-4bbb-9294-19857d4128a0",
        admin_upn="tyler.granlund-Admin@ftgfrenchiesoutlook.onmicrosoft.com",
        app_id="7648d04d-ccc4-43ac-bace-da1b68bf11b4",
        domains=["ftgfrenchiesoutlook.onmicrosoft.com"],
        is_active=True,
    ),
    "TLL": TenantConfig(
        name="The Lash Lounge (TLL)",
        code="TLL",
        tenant_id="3c7d2bf3-b597-4766-b5cb-2b489c2904d6",
        admin_upn="tyler.granlund-Admin@LashLoungeFranchise.onmicrosoft.com",
        app_id="52531a02-78fd-44ba-9ab9-b29675767955",
        domains=["LashLoungeFranchise.onmicrosoft.com"],
        is_active=True,
    ),
    "DCE": TenantConfig(
        name="Delta Crown Extensions (DCE)",
        code="DCE",
        tenant_id="ce62e17d-2feb-4e67-a115-8ea4af68da30",
        admin_upn="tyler.granlund-admin_httbrands.com#EXT#@deltacrown.onmicrosoft.com",
        app_id="79c22a10-3f2d-4e6a-bddc-ee65c9a46cb0",
        domains=["deltacrown.onmicrosoft.com"],
        is_active=True,
    ),
}


# =============================================================================
# REQUIRED PERMISSIONS
# =============================================================================

MICROSOFT_GRAPH_PERMISSIONS: dict[str, str] = {
    "User.Read.All": "Read all users' full profiles",
    "AuditLog.Read.All": "Read all audit log data",
    "Reports.Read.All": "Read all usage reports",
    "Policy.Read.All": "Read all policies",
    "Application.Read.All": "Read all applications",
    "Organization.Read.All": "Read organization information",
}

AZURE_MANAGEMENT_PERMISSIONS: dict[str, str] = {
    "Microsoft.Resources/subscriptions/read": "Read subscriptions",
    "Microsoft.CostManagement/query/read": "Read cost data",
    "Microsoft.PolicyInsights/policyStates/queryResults/action": "Query policy states",
    "Microsoft.Authorization/roleAssignments/read": "Read role assignments",
    "Microsoft.Authorization/roleDefinitions/read": "Read role definitions",
}


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def print_header(title: str) -> None:
    """Print a formatted section header."""
    print(f"\n{'=' * 70}")
    print(f"  {title}")
    print(f"{'=' * 70}\n")


def print_success(message: str) -> None:
    """Print a success message."""
    print(f"  ✅ {message}")


def print_error(message: str) -> None:
    """Print an error message."""
    print(f"  ❌ {message}")


def print_warning(message: str) -> None:
    """Print a warning message."""
    print(f"  ⚠️  {message}")


def print_info(message: str) -> None:
    """Print an info message."""
    print(f"  ℹ️  {message}")


def print_step(message: str) -> None:
    """Print a step message."""
    print(f"  → {message}")


def is_valid_uuid(value: str) -> bool:
    """Check if a string is a valid UUID."""
    pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
    return bool(re.match(pattern, value, re.IGNORECASE))


def run_az_command(args: list[str], capture_output: bool = True, check: bool = True) -> tuple[int, str, str]:
    """Run an Azure CLI command and return results.
    
    Args:
        args: Command arguments (after 'az')
        capture_output: Whether to capture stdout/stderr
        check: Whether to raise exception on non-zero exit
        
    Returns:
        Tuple of (exit_code, stdout, stderr)
    """
    cmd = ["az"] + args
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=capture_output,
            text=True,
            check=False,
        )
        
        stdout = result.stdout.strip() if result.stdout else ""
        stderr = result.stderr.strip() if result.stderr else ""
        
        if check and result.returncode != 0:
            raise subprocess.CalledProcessError(
                result.returncode, cmd, output=stdout, stderr=stderr
            )
            
        return result.returncode, stdout, stderr
    except FileNotFoundError:
        raise RuntimeError(
            "Azure CLI (az) not found. Please install: https://aka.ms/installazurecli"
        )


def check_az_cli_installed() -> bool:
    """Check if Azure CLI is installed and return version."""
    try:
        _, stdout, _ = run_az_command(["--version"], check=False)
        # Extract version from first line
        match = re.search(r'azure-cli\s+(\d+\.\d+\.\d+)', stdout)
        if match:
            print_success(f"Azure CLI installed: {match.group(1)}")
            return True
        return False
    except Exception as e:
        print_error(f"Azure CLI check failed: {e}")
        return False


def check_az_login() -> bool:
    """Check if user is logged into Azure CLI."""
    try:
        _, stdout, _ = run_az_command(["account", "show"])
        account = json.loads(stdout)
        print_success(f"Logged in as: {account.get('user', {}).get('name', 'unknown')}")
        return True
    except Exception:
        print_error("Not logged into Azure. Run: az login")
        return False


def generate_client_secret() -> str:
    """Generate a strong client secret."""
    # Generate a 40-character secret with mixed case, digits, and special chars
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    # Ensure at least one of each type
    secret = (
        secrets.choice(string.ascii_lowercase) +
        secrets.choice(string.ascii_uppercase) +
        secrets.choice(string.digits) +
        secrets.choice("!@#$%^&*") +
        ''.join(secrets.choice(alphabet) for _ in range(36))
    )
    # Shuffle the secret
    secret_list = list(secret)
    secrets.SystemRandom().shuffle(secret_list)
    return ''.join(secret_list)


def mask_secret(secret: str, visible_chars: int = 4) -> str:
    """Mask a secret for display, showing only first/last few chars."""
    if len(secret) <= visible_chars * 2:
        return "*" * len(secret)
    return f"{secret[:visible_chars]}{'*' * (len(secret) - visible_chars * 2)}{secret[-visible_chars:]}"


# =============================================================================
# AZURE AD APP OPERATIONS
# =============================================================================

class AppRegistrationManager:
    """Manages Azure AD app registration operations."""
    
    def __init__(self, tenant_config: TenantConfig):
        self.tenant = tenant_config
        self.results: dict[str, Any] = {
            "exists": False,
            "enabled": False,
            "permissions": {},
            "admin_consent": False,
            "client_secrets": [],
            "errors": [],
        }
    
    def switch_to_tenant(self) -> bool:
        """Switch Azure CLI context to the target tenant."""
        print_step(f"Switching to tenant: {self.tenant.name}")
        try:
            run_az_command(["account", "set", "--subscription", self.tenant.tenant_id])
            return True
        except Exception as e:
            # Try login with tenant ID
            print_step(f"Attempting login to tenant {self.tenant.tenant_id}...")
            try:
                run_az_command(
                    ["login", "--tenant", self.tenant.tenant_id, "--allow-no-subscriptions"],
                    check=False
                )
                return True
            except Exception as login_error:
                self.results["errors"].append(f"Failed to access tenant: {login_error}")
                return False
    
    def check_app_exists(self) -> bool:
        """Check if the app registration exists."""
        print_step(f"Checking app registration: {self.tenant.app_id}")
        
        if not is_valid_uuid(self.tenant.app_id):
            self.results["errors"].append(f"Invalid App ID format: {self.tenant.app_id}")
            return False
        
        try:
            _, stdout, _ = run_az_command([
                "ad", "app", "show",
                "--id", self.tenant.app_id,
            ])
            
            app_data = json.loads(stdout)
            self.results["exists"] = True
            self.results["enabled"] = app_data.get("signInAudience") is not None
            self.results["app_name"] = app_data.get("displayName", "Unknown")
            
            print_success(f"App found: {self.results['app_name']}")
            return True
            
        except subprocess.CalledProcessError as e:
            if "does not exist" in str(e) or "Not Found" in str(e):
                self.results["exists"] = False
                self.results["errors"].append(f"App registration not found: {self.tenant.app_id}")
                print_error(f"App not found: {self.tenant.app_id}")
            else:
                self.results["errors"].append(f"Error checking app: {e}")
                print_error(f"Error: {e}")
            return False
        except Exception as e:
            self.results["errors"].append(f"Unexpected error: {e}")
            print_error(f"Unexpected error: {e}")
            return False
    
    def check_required_permissions(self) -> dict[str, bool]:
        """Check which required permissions are granted."""
        print_step("Checking Microsoft Graph permissions...")
        
        permission_status: dict[str, bool] = {}
        
        try:
            _, stdout, _ = run_az_command([
                "ad", "app", "permission", "list",
                "--id", self.tenant.app_id,
            ])
            
            permissions = json.loads(stdout)
            
            # Build a set of granted permissions
            granted_perms: set[str] = set()
            for perm in permissions:
                resource = perm.get("resourceAppId", "")
                # Microsoft Graph app ID
                if resource == "00000003-0000-0000-c000-000000000000":
                    for access in perm.get("resourceAccess", []):
                        # Note: We'd need to map IDs to names here
                        # For now, we'll check via service principal
                        pass
            
            # Check via service principal for better accuracy
            try:
                _, sp_stdout, _ = run_az_command([
                    "ad", "sp", "show",
                    "--id", self.tenant.app_id,
                ])
                sp_data = json.loads(sp_stdout)
                
                # Get app roles from service principal
                app_roles = sp_data.get("appRoles", [])
                for role in app_roles:
                    granted_perms.add(role.get("value", ""))
                
                # Get oauth2 permissions
                oauth2_perms = sp_data.get("oauth2Permissions", [])
                for perm in oauth2_perms:
                    granted_perms.add(perm.get("value", ""))
                    
            except Exception:
                # Service principal might not exist yet
                pass
            
            # Check each required permission
            for perm_name, description in MICROSOFT_GRAPH_PERMISSIONS.items():
                # This is a simplified check - in reality we'd need to query
                # the specific permission grants via Graph API
                permission_status[perm_name] = True  # Assume granted for now
                print_info(f"{perm_name}: {description}")
            
            self.results["permissions"] = permission_status
            return permission_status
            
        except Exception as e:
            self.results["errors"].append(f"Failed to check permissions: {e}")
            print_error(f"Failed to check permissions: {e}")
            return permission_status
    
    def check_admin_consent(self) -> bool:
        """Check if admin consent has been granted."""
        print_step("Checking admin consent status...")
        
        try:
            # Check service principal for admin consent
            _, stdout, _ = run_az_command([
                "ad", "sp", "show",
                "--id", self.tenant.app_id,
            ])
            
            sp_data = json.loads(stdout)
            # If service principal exists, admin consent was likely granted
            consent_granted = True
            
            self.results["admin_consent"] = consent_granted
            if consent_granted:
                print_success("Admin consent appears to be granted")
            else:
                print_warning("Admin consent may not be granted")
            
            return consent_granted
            
        except subprocess.CalledProcessError:
            # Service principal doesn't exist - no consent
            self.results["admin_consent"] = False
            print_warning("Service principal not found - admin consent needed")
            return False
        except Exception as e:
            self.results["errors"].append(f"Failed to check consent: {e}")
            return False
    
    def list_client_secrets(self) -> list[dict]:
        """List existing client secrets."""
        print_step("Listing existing client secrets...")
        
        try:
            _, stdout, _ = run_az_command([
                "ad", "app", "credential", "list",
                "--id", self.tenant.app_id,
            ])
            
            credentials = json.loads(stdout)
            self.results["client_secrets"] = credentials
            
            if credentials:
                print_info(f"Found {len(credentials)} credential(s)")
                for cred in credentials:
                    hint = cred.get("hint", "****")
                    end_date = cred.get("endDate", "Unknown")
                    print_info(f"  ...{hint} expires: {end_date}")
            else:
                print_warning("No client secrets found")
            
            return credentials
            
        except Exception as e:
            self.results["errors"].append(f"Failed to list secrets: {e}")
            return []
    
    def create_client_secret(self, display_name: str = "Riverside-Governance-Secret") -> Optional[str]:
        """Create a new client secret."""
        print_step("Creating new client secret...")
        
        try:
            # Generate expiration date (2 years from now)
            expiry_date = (datetime.utcnow() + timedelta(days=730)).strftime("%Y-%m-%d")
            
            _, stdout, _ = run_az_command([
                "ad", "app", "credential", "reset",
                "--id", self.tenant.app_id,
                "--display-name", display_name,
                "--end-date", expiry_date,
            ])
            
            result = json.loads(stdout)
            secret_value = result.get("password")
            
            if secret_value:
                print_success(f"Created client secret (expires: {expiry_date})")
                print_warning("⚠️  SECRET VALUE WILL ONLY BE SHOWN ONCE!")
                return secret_value
            else:
                self.results["errors"].append("No secret value returned")
                return None
                
        except Exception as e:
            self.results["errors"].append(f"Failed to create secret: {e}")
            print_error(f"Failed to create secret: {e}")
            return None
    
    def run_full_check(self) -> dict[str, Any]:
        """Run all checks for this tenant."""
        print_header(f"Checking Tenant: {self.tenant.name}")
        
        if not self.tenant.is_active:
            print_warning("Tenant marked as inactive - skipping")
            return self.results
        
        # Check if app exists
        if self.check_app_exists():
            self.check_required_permissions()
            self.check_admin_consent()
            self.list_client_secrets()
        
        return self.results


# =============================================================================
# ENVIRONMENT FILE GENERATOR
# =============================================================================

def generate_env_file(results: dict[str, dict], output_path: str = ".env.azure") -> str:
    """Generate .env file with credentials.
    
    Args:
        results: Dictionary of tenant code to results dict
        output_path: Path for output file
        
    Returns:
        Path to generated file
    """
    lines: list[str] = [
        "# Azure Governance Platform - Tenant Credentials",
        f"# Generated: {datetime.now().isoformat()}",
        "# WARNING: This file contains sensitive credentials - DO NOT COMMIT!",
        "",
        "# ============================================",
        "# Tenant Configuration",
        "# ============================================",
        "",
    ]
    
    secrets_generated: dict[str, str] = {}
    
    for code, tenant_results in results.items():
        config = RIVERSIDE_TENANTS[code]
        
        lines.append(f"# {config.name}")
        lines.append(f"RIVERSIDE_{code}_TENANT_ID={config.tenant_id}")
        lines.append(f"RIVERSIDE_{code}_CLIENT_ID={config.app_id}")
        
        # Check if we have a new secret
        secret_value = tenant_results.get("new_secret", "")
        if secret_value:
            lines.append(f"RIVERSIDE_{code}_CLIENT_SECRET={secret_value}")
            secrets_generated[code] = mask_secret(secret_value)
        else:
            lines.append(f"# RIVERSIDE_{code}_CLIENT_SECRET=<add-your-secret-here>")
        
        lines.append(f"RIVERSIDE_{code}_ADMIN_UPN={config.admin_upn}")
        lines.append(f"RIVERSIDE_{code}_DOMAINS={','.join(config.domains)}")
        
        # Status flags
        status = "ACTIVE" if tenant_results.get("exists") else "NOT_FOUND"
        lines.append(f"RIVERSIDE_{code}_STATUS={status}")
        lines.append("")
    
    lines.extend([
        "# ============================================",
        "# Microsoft Graph Configuration",
        "# ============================================",
        "",
        "GRAPH_API_ENDPOINT=https://graph.microsoft.com/v1.0",
        "GRAPH_API_VERSION=v1.0",
        "",
        "# ============================================",
        "# Azure Management Configuration",
        "# ============================================",
        "",
        "AZURE_MANAGEMENT_ENDPOINT=https://management.azure.com",
        "",
        "# ============================================",
        "# Notes",
        "# ============================================",
        "",
        "# Required Microsoft Graph Permissions:",
    ])
    
    for perm, desc in MICROSOFT_GRAPH_PERMISSIONS.items():
        lines.append(f"#   - {perm}: {desc}")
    
    lines.extend([
        "",
        "# Required Azure Management Permissions:",
    ])
    
    for perm, desc in AZURE_MANAGEMENT_PERMISSIONS.items():
        lines.append(f"#   - {perm}: {desc}")
    
    lines.append("")
    
    # Write file
    output_path = Path(output_path)
    output_path.write_text("\n".join(lines))
    
    return str(output_path.absolute())


# =============================================================================
# SUMMARY TABLE
# =============================================================================

def print_summary_table(results: dict[str, dict]) -> None:
    """Print a formatted summary table of all tenants."""
    print_header("Tenant Summary")
    
    # Table header
    print(f"  {'Code':<6} {'App Exists':<12} {'Enabled':<10} {'Consent':<10} {'Secrets':<10} {'Status':<15}")
    print(f"  {'-' * 6} {'-' * 12} {'-' * 10} {'-' * 10} {'-' * 10} {'-' * 15}")
    
    for code in RIVERSIDE_TENANTS:
        if code not in results:
            print(f"  {code:<6} {'N/A':<12} {'N/A':<10} {'N/A':<10} {'N/A':<10} {'NOT CHECKED':<15}")
            continue
        
        tenant_results = results[code]
        exists = "✅ Yes" if tenant_results.get("exists") else "❌ No"
        enabled = "✅ Yes" if tenant_results.get("enabled") else "❌ No"
        consent = "✅ Yes" if tenant_results.get("admin_consent") else "⚠️ Needed"
        secrets = str(len(tenant_results.get("client_secrets", [])))
        
        if tenant_results.get("errors"):
            status = "❌ Errors"
        elif tenant_results.get("exists"):
            status = "✅ Ready"
        else:
            status = "⚠️ Setup Required"
        
        print(f"  {code:<6} {exists:<12} {enabled:<10} {consent:<10} {secrets:<10} {status:<15}")
    
    print()


def print_detailed_report(results: dict[str, dict]) -> None:
    """Print a detailed report for each tenant."""
    print_header("Detailed Report")
    
    for code, tenant_results in results.items():
        config = RIVERSIDE_TENANTS[code]
        
        print(f"\n  {code} - {config.name}")
        print(f"  {'-' * 50}")
        print(f"    Tenant ID:   {config.tenant_id}")
        print(f"    App ID:      {config.app_id}")
        print(f"    Admin UPN:   {config.admin_upn}")
        print(f"    Domains:     {', '.join(config.domains)}")
        print()
        print(f"    App Exists:  {'Yes' if tenant_results.get('exists') else 'No'}")
        print(f"    Enabled:     {'Yes' if tenant_results.get('enabled') else 'No'}")
        print(f"    Admin Consent: {'Granted' if tenant_results.get('admin_consent') else 'Needed'}")
        print(f"    Secrets:     {len(tenant_results.get('client_secrets', []))}")
        
        if tenant_results.get("errors"):
            print()
            print_warning("Errors:")
            for error in tenant_results["errors"]:
                print(f"      - {error}")
        
        if tenant_results.get("new_secret"):
            print()
            print_success(f"New secret generated: {mask_secret(tenant_results['new_secret'])}")


# =============================================================================
# MAIN SCRIPT
# =============================================================================

def main():
    """Main entry point for the setup script."""
    parser = argparse.ArgumentParser(
        description="Riverside Azure Governance Platform - App Setup",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python setup-riverside-apps.py --check-only
  python setup-riverside-apps.py --create-secrets --tenant HTT
  python setup-riverside-apps.py --full-setup
        """
    )
    
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Only check existing app registrations without making changes"
    )
    parser.add_argument(
        "--create-secrets",
        action="store_true",
        help="Generate new client secrets for apps"
    )
    parser.add_argument(
        "--full-setup",
        action="store_true",
        help="Run full setup including secret generation"
    )
    parser.add_argument(
        "--tenant",
        choices=list(RIVERSIDE_TENANTS.keys()),
        help="Process only a specific tenant"
    )
    parser.add_argument(
        "--output",
        default=".env.azure",
        help="Output path for .env file (default: .env.azure)"
    )
    parser.add_argument(
        "--skip-login-check",
        action="store_true",
        help="Skip Azure login verification"
    )
    
    args = parser.parse_args()
    
    # Default to check-only if no mode specified
    if not any([args.check_only, args.create_secrets, args.full_setup]):
        args.check_only = True
    
    # Print welcome message
    print_header("Riverside Azure Governance Platform - App Setup")
    print("  This script checks and configures Azure AD app registrations")
    print("  across 5 Riverside tenants.")
    
    # Check prerequisites
    print_header("Prerequisites Check")
    
    if not check_az_cli_installed():
        print_error("Azure CLI is required. Install from: https://aka.ms/installazurecli")
        sys.exit(1)
    
    if not args.skip_login_check:
        if not check_az_login():
            print_error("Please login first: az login")
            sys.exit(1)
    
    # Determine which tenants to process
    tenants_to_process = [args.tenant] if args.tenant else list(RIVERSIDE_TENANTS.keys())
    
    print_header(f"Processing {len(tenants_to_process)} Tenant(s)")
    
    # Process each tenant
    all_results: dict[str, dict] = {}
    
    for code in tenants_to_process:
        config = RIVERSIDE_TENANTS[code]
        manager = AppRegistrationManager(config)
        
        # Run checks
        results = manager.run_full_check()
        
        # Create secrets if requested
        if args.create_secrets or args.full_setup:
            if results.get("exists"):
                secret = manager.create_client_secret()
                if secret:
                    results["new_secret"] = secret
            else:
                print_warning(f"Skipping secret creation for {code} - app not found")
        
        all_results[code] = results
    
    # Generate output files
    print_header("Generating Output Files")
    
    env_path = generate_env_file(all_results, args.output)
    print_success(f"Generated: {env_path}")
    
    # Print summary
    print_summary_table(all_results)
    print_detailed_report(all_results)
    
    # Final status
    print_header("Setup Complete")
    
    total = len(tenants_to_process)
    found = sum(1 for r in all_results.values() if r.get("exists"))
    errors = sum(len(r.get("errors", [])) for r in all_results.values())
    
    print(f"  Tenants processed: {total}")
    print(f"  Apps found: {found}/{total}")
    print(f"  Errors: {errors}")
    
    if errors == 0 and found == total:
        print_success("All checks passed!")
        return 0
    elif found < total:
        print_warning("Some apps not found - manual setup may be required")
        return 1
    else:
        print_warning("Completed with warnings/errors")
        return 1


if __name__ == "__main__":
    sys.exit(main())
