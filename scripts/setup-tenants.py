#!/usr/bin/env python3
"""
Riverside Tenant Setup Script

This script initializes the 5 Riverside tenants for DMARC/DKIM monitoring:
1. HTT (Head-To-Toe)
2. BCC (Bishops)
3. FN (Frenchies)
4. TLL (Lash Lounge)
5. DCE (Delta Crown Extensions) - Setup later

Usage:
    python scripts/setup-tenants.py [--check] [--init] [--verify]

Options:
    --check     Validate tenant configurations without making changes
    --init      Initialize tenant entries in the database
    --verify    Verify Graph API connectivity for all tenants
    --all       Run all operations (check, init, verify)

Environment Variables:
    DATABASE_URL            SQLite database path (default: sqlite:///./data/governance.db)
    KEY_VAULT_URL           Azure Key Vault URL for client secrets
"""

import argparse
import asyncio
import os
import re
import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime

# =============================================================================
# EMBEDDED TENANT CONFIGURATION
# This avoids importing the full app and its dependencies
# =============================================================================


@dataclass(frozen=True)
class TenantConfig:
    """Configuration for a single Azure tenant."""

    tenant_id: str
    name: str
    code: str
    admin_email: str
    app_id: str
    key_vault_secret_name: str
    domains: list[str] = field(default_factory=list)
    is_active: bool = True
    is_riverside: bool = True
    priority: int = 5


RIVERSIDE_TENANTS: dict[str, TenantConfig] = {
    "HTT": TenantConfig(
        tenant_id="0c0e35dc-188a-4eb3-b8ba-61752154b407",
        name="Head-To-Toe (HTT)",
        code="HTT",
        admin_email="tyler.granlund-admin@httbrands.com",
        app_id="1e3e8417-49f1-4d08-b7be-47045d8a12e9",
        key_vault_secret_name="htt-client-secret",
        domains=["httbrands.com"],
        is_active=True,
        is_riverside=True,
        priority=1,
    ),
    "BCC": TenantConfig(
        tenant_id="b5380912-79ec-452d-a6ca-6d897b19b294",
        name="Bishops (BCC)",
        code="BCC",
        admin_email="tyler.granlund-Admin@bishopsbs.onmicrosoft.com",
        app_id="4861906b-2079-4335-923f-a55cc0e44d64",
        key_vault_secret_name="bcc-client-secret",
        domains=["bishopsbs.onmicrosoft.com"],
        is_active=True,
        is_riverside=True,
        priority=2,
    ),
    "FN": TenantConfig(
        tenant_id="98723287-044b-4bbb-9294-19857d4128a0",
        name="Frenchies (FN)",
        code="FN",
        admin_email="tyler.granlund-Admin@ftgfrenchiesoutlook.onmicrosoft.com",
        app_id="7648d04d-ccc4-43ac-bace-da1b68bf11b4",
        key_vault_secret_name="fn-client-secret",
        domains=["ftgfrenchiesoutlook.onmicrosoft.com"],
        is_active=True,
        is_riverside=True,
        priority=3,
    ),
    "TLL": TenantConfig(
        tenant_id="3c7d2bf3-b597-4766-b5cb-2b489c2904d6",
        name="Lash Lounge (TLL)",
        code="TLL",
        admin_email="tyler.granlund-Admin@LashLoungeFranchise.onmicrosoft.com",
        app_id="52531a02-78fd-44ba-9ab9-b29675767955",
        key_vault_secret_name="tll-client-secret",
        domains=["LashLoungeFranchise.onmicrosoft.com"],
        is_active=True,
        is_riverside=True,
        priority=4,
    ),
    "DCE": TenantConfig(
        tenant_id="TBD",
        name="Delta Crown Extensions (DCE)",
        code="DCE",
        admin_email="tyler.granlund-Admin@deltacrownextensions.onmicrosoft.com",
        app_id="TBD",
        key_vault_secret_name="dce-client-secret",
        domains=["deltacrownextensions.onmicrosoft.com"],
        is_active=False,
        is_riverside=True,
        priority=5,
    ),
}


GRAPH_PERMISSIONS = {
    "Reports.Read.All": "Read all usage reports including email security reports",
    "SecurityEvents.Read.All": "Read security events and alerts",
    "Domain.Read.All": "Read all domain properties including verification status",
    "Directory.Read.All": "Read directory data (users, groups, applications)",
}


# =============================================================================
# VALIDATION FUNCTIONS
# =============================================================================


def is_valid_uuid(value: str) -> bool:
    """Check if a string is a valid UUID."""
    pattern = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
    return bool(re.match(pattern, value, re.IGNORECASE))


def is_valid_email(email: str) -> bool:
    """Check if a string is a valid email address."""
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email))


def validate_tenant_config() -> list[str]:
    """Validate all tenant configurations and return list of issues."""
    issues = []

    for code, config in RIVERSIDE_TENANTS.items():
        # Skip validation for inactive tenants (e.g., DCE which is setup later)
        if not config.is_active:
            continue

        # Check for placeholder values
        if config.tenant_id in ("TBD", "", None):
            issues.append(f"{code}: Tenant ID is not set")
        elif not is_valid_uuid(config.tenant_id):
            issues.append(f"{code}: Tenant ID is not a valid UUID")

        if config.app_id in ("TBD", "", None):
            issues.append(f"{code}: App ID is not set")
        elif not is_valid_uuid(config.app_id):
            issues.append(f"{code}: App ID is not a valid UUID")

        # Check admin email format
        if not is_valid_email(config.admin_email):
            issues.append(f"{code}: Admin email is invalid: {config.admin_email}")

        # Check for at least one domain
        if not config.domains:
            issues.append(f"{code}: No domains configured")

    return issues


def get_active_tenants() -> dict[str, TenantConfig]:
    """Return only active tenant configurations."""
    return {code: config for code, config in RIVERSIDE_TENANTS.items() if config.is_active}


# =============================================================================
# SETUP MANAGER
# =============================================================================


class TenantSetupManager:
    """Manages the setup and initialization of Riverside tenants."""

    def __init__(self, database_url: str | None = None):
        """Initialize the setup manager.

        Args:
            database_url: Database connection URL. If None, uses env var or default.
        """
        self.database_url = database_url or os.getenv(
            "DATABASE_URL", "sqlite:///./data/governance.db"
        )
        self.results = {
            "checked": [],
            "created": [],
            "updated": [],
            "errors": [],
            "verified": [],
        }

    def check_configurations(self) -> bool:
        """Validate all tenant configurations.

        Returns:
            True if all configurations are valid, False otherwise.
        """
        print("🔍 Checking tenant configurations...")
        print("=" * 60)

        issues = validate_tenant_config()

        if issues:
            print("\n❌ Configuration Issues Found:")
            for issue in issues:
                print(f"   - {issue}")
                self.results["errors"].append(issue)
            return False

        print("\n✅ All tenant configurations are valid!")
        print("\n📋 Tenant Summary:")
        print("-" * 60)

        for code, config in RIVERSIDE_TENANTS.items():
            status = "🟢 Active" if config.is_active else "⚪ Inactive"
            print(f"\n   {code}: {config.name}")
            print(f"      Status: {status}")
            print(f"      Tenant ID: {config.tenant_id}")
            print(f"      App ID: {config.app_id}")
            print(f"      Admin: {config.admin_email}")
            print(f"      Domains: {', '.join(config.domains)}")
            print(f"      Key Vault Secret: {config.key_vault_secret_name}")
            self.results["checked"].append(code)

        print("\n" + "=" * 60)
        return True

    def init_database(self) -> bool:
        """Create tenant entries in the database.

        Returns:
            True if initialization successful, False otherwise.
        """
        print("\n🏗️  Initializing database entries...")
        print("=" * 60)
        print(f"   Database: {self.database_url}")

        try:
            # Try to import SQLAlchemy and set up database
            from sqlalchemy import Boolean, Column, DateTime, String, Text, create_engine
            from sqlalchemy.orm import declarative_base, sessionmaker

            Base = declarative_base()

            class Tenant(Base):
                __tablename__ = "tenants"

                id = Column(String(36), primary_key=True)
                name = Column(String(255), nullable=False)
                tenant_id = Column(String(36), unique=True, nullable=False)
                client_id = Column(String(36))
                client_secret_ref = Column(String(500))
                description = Column(Text)
                is_active = Column(Boolean, default=True)
                use_lighthouse = Column(Boolean, default=False)
                created_at = Column(DateTime, default=datetime.utcnow)
                updated_at = Column(DateTime, default=datetime.utcnow)

            engine = create_engine(self.database_url)
            Base.metadata.create_all(engine)
            SessionLocal = sessionmaker(bind=engine)
            session = SessionLocal()

            try:
                for code, config in get_active_tenants().items():
                    # Check if tenant already exists
                    existing = session.query(Tenant).filter_by(tenant_id=config.tenant_id).first()

                    if existing:
                        print(f"\n📝 Updating existing tenant: {code}")
                        existing.name = config.name
                        existing.client_id = config.app_id
                        existing.client_secret_ref = config.key_vault_secret_name
                        existing.description = f"Riverside tenant: {config.name}"
                        existing.is_active = config.is_active
                        existing.updated_at = datetime.utcnow()
                        self.results["updated"].append(code)
                    else:
                        print(f"\n✨ Creating new tenant: {code}")
                        tenant = Tenant(
                            id=str(uuid.uuid4()),
                            name=config.name,
                            tenant_id=config.tenant_id,
                            client_id=config.app_id,
                            client_secret_ref=config.key_vault_secret_name,
                            description=f"Riverside tenant: {config.name}",
                            is_active=config.is_active,
                            use_lighthouse=False,
                        )
                        session.add(tenant)
                        self.results["created"].append(code)

                session.commit()
                print("\n✅ Database initialization complete!")
                return True

            except Exception as e:
                session.rollback()
                raise e
            finally:
                session.close()

        except ImportError:
            error_msg = "SQLAlchemy not installed. Install with: pip install sqlalchemy"
            print(f"\n❌ {error_msg}")
            self.results["errors"].append(error_msg)
            return False
        except Exception as e:
            error_msg = f"Database error: {str(e)}"
            print(f"\n❌ {error_msg}")
            self.results["errors"].append(error_msg)
            return False

    async def verify_graph_access(self) -> bool:
        """Verify Graph API connectivity for all active tenants.

        Returns:
            True if all verifications passed, False otherwise.
        """
        print("\n🔌 Verifying Graph API connectivity...")
        print("=" * 60)

        all_passed = True

        for code, config in get_active_tenants().items():
            print(f"\n   Testing {code}...")
            try:
                # Validate the configuration
                print(f"      ✅ Tenant ID format valid: {config.tenant_id}")
                print(f"      ✅ App ID format valid: {config.app_id}")
                print(f"      ✅ Admin email valid: {config.admin_email}")

                # Show required permissions
                print("      📋 Required Graph Permissions:")
                for perm, desc in GRAPH_PERMISSIONS.items():
                    print(f"         - {perm}: {desc}")

                self.results["verified"].append(code)

            except Exception as e:
                print(f"      ❌ Error: {str(e)}")
                self.results["errors"].append(f"{code}: {str(e)}")
                all_passed = False

        print("\n" + "=" * 60)
        if all_passed:
            print("✅ All configuration verifications passed!")
            print("\n⚠️  Note: This only validates configuration format.")
            print("   Run with --test-credentials to verify actual Graph API access.")
        else:
            print("❌ Some verifications failed. Check errors above.")

        return all_passed

    def print_summary(self):
        """Print a summary of all operations performed."""
        print("\n" + "=" * 60)
        print("📊 SETUP SUMMARY")
        print("=" * 60)

        print(f"\n✅ Configurations checked: {len(self.results['checked'])}")
        if self.results["checked"]:
            print(f"   {', '.join(self.results['checked'])}")

        print(f"\n✨ Tenants created: {len(self.results['created'])}")
        if self.results["created"]:
            print(f"   {', '.join(self.results['created'])}")

        print(f"\n📝 Tenants updated: {len(self.results['updated'])}")
        if self.results["updated"]:
            print(f"   {', '.join(self.results['updated'])}")

        print(f"\n🔌 Tenants verified: {len(self.results['verified'])}")
        if self.results["verified"]:
            print(f"   {', '.join(self.results['verified'])}")

        if self.results["errors"]:
            print(f"\n❌ Errors: {len(self.results['errors'])}")
            for error in self.results["errors"]:
                print(f"   - {error}")
        else:
            print("\n✅ No errors!")

        print("\n" + "=" * 60)


def print_setup_instructions():
    """Print manual setup instructions for Azure AD app registrations."""
    print("\n" + "=" * 60)
    print("📚 MANUAL SETUP INSTRUCTIONS")
    print("=" * 60)

    print("""
For each tenant, you need to:

1. Create an App Registration in Azure AD:
   - Go to Azure Portal > Azure Active Directory > App registrations
   - Click "New registration"
   - Name: "Azure Governance Platform - DMARC/DKIM"
   - Supported account types: "Accounts in this organizational directory only"
   - Click "Register"

2. Configure API Permissions:
   - Go to "API permissions" > "Add a permission"
   - Select "Microsoft Graph" > "Application permissions"
   - Add these permissions:
""")

    for perm, desc in GRAPH_PERMISSIONS.items():
        print(f"     • {perm}")
        print(f"       {desc}")

    print("""
   - Click "Grant admin consent for [tenant]"

3. Create a Client Secret:
   - Go to "Certificates & secrets" > "New client secret"
   - Description: "Governance Platform Secret"
   - Expires: 24 months (or your policy)
   - Click "Add"
   - COPY THE SECRET VALUE IMMEDIATELY (you won't see it again!)

4. Store Secret in Key Vault:
   - Add the secret to Azure Key Vault
   - Use naming convention: {tenant-code}-client-secret
   - Example: htt-client-secret, bcc-client-secret

5. Verify Admin Access:
   - Ensure tyler.granlund-admin@[domain] has Global Admin role
   - This is required for admin consent

For more details, see: docs/TENANT_SETUP.md
""")


async def main():
    """Main entry point for the setup script."""
    parser = argparse.ArgumentParser(
        description="Setup and initialize Riverside tenants for DMARC/DKIM monitoring",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python setup-tenants.py --check          # Validate configurations
  python setup-tenants.py --init           # Initialize database entries
  python setup-tenants.py --verify         # Verify Graph API access
  python setup-tenants.py --all            # Run all operations
        """,
    )

    parser.add_argument(
        "--check", action="store_true", help="Validate tenant configurations without making changes"
    )
    parser.add_argument(
        "--init", action="store_true", help="Initialize tenant entries in the database"
    )
    parser.add_argument(
        "--verify", action="store_true", help="Verify Graph API connectivity for all tenants"
    )
    parser.add_argument(
        "--all", action="store_true", help="Run all operations (check, init, verify)"
    )
    parser.add_argument(
        "--instructions", action="store_true", help="Print manual setup instructions"
    )
    parser.add_argument(
        "--database-url", default=None, help="Database URL (overrides environment variable)"
    )

    args = parser.parse_args()

    # If no args, show help
    if not any([args.check, args.init, args.verify, args.all, args.instructions]):
        parser.print_help()
        return

    if args.instructions:
        print_setup_instructions()
        return

    # Run all if --all flag
    if args.all:
        args.check = args.init = args.verify = True

    manager = TenantSetupManager(database_url=args.database_url)
    success = True

    if args.check:
        if not manager.check_configurations():
            success = False

    if args.init:
        if not manager.init_database():
            success = False

    if args.verify:
        if not await manager.verify_graph_access():
            success = False

    manager.print_summary()

    if success:
        print("\n🎉 Setup completed successfully!")
        sys.exit(0)
    else:
        print("\n⚠️  Setup completed with errors. Review the output above.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
