#!/usr/bin/env python3
"""Seed database with sample data for development/testing."""

import sys
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import SessionLocal, init_db
from app.models.compliance import ComplianceSnapshot, PolicyState
from app.models.cost import CostSnapshot
from app.models.identity import IdentitySnapshot, PrivilegedUser
from app.models.resource import Resource
from app.models.tenant import Subscription, Tenant


def seed_tenants(db):
    """Create sample tenants."""
    tenants = [
        Tenant(
            id=str(uuid.uuid4()),
            name="Production Tenant",
            tenant_id="11111111-1111-1111-1111-111111111111",
            description="Main production workloads",
            is_active=True,
        ),
        Tenant(
            id=str(uuid.uuid4()),
            name="Development Tenant",
            tenant_id="22222222-2222-2222-2222-222222222222",
            description="Development and testing",
            is_active=True,
        ),
        Tenant(
            id=str(uuid.uuid4()),
            name="Staging Tenant",
            tenant_id="33333333-3333-3333-3333-333333333333",
            description="Pre-production staging",
            is_active=True,
        ),
        Tenant(
            id=str(uuid.uuid4()),
            name="Sandbox Tenant",
            tenant_id="44444444-4444-4444-4444-444444444444",
            description="Experimentation and POCs",
            is_active=True,
        ),
    ]

    for tenant in tenants:
        db.add(tenant)
        # Add subscriptions for each tenant
        for i in range(2):
            sub = Subscription(
                id=str(uuid.uuid4()),
                tenant_ref=tenant.id,
                subscription_id=str(uuid.uuid4()),
                display_name=f"{tenant.name} - Sub {i + 1}",
                state="Enabled",
                synced_at=datetime.utcnow(),
            )
            db.add(sub)

    db.commit()
    return tenants


def seed_costs(db, tenants):
    """Create sample cost data."""
    import random

    services = [
        "Virtual Machines",
        "Storage",
        "SQL Database",
        "App Service",
        "Azure Functions",
        "Key Vault",
        "Virtual Network",
        "Application Gateway",
    ]

    for tenant in tenants:
        random.uniform(500, 3000)
        for day_offset in range(30):
            snapshot_date = date.today() - timedelta(days=day_offset)
            for service in random.sample(services, 5):
                cost = CostSnapshot(
                    tenant_id=tenant.id,
                    subscription_id=tenant.subscriptions[0].subscription_id,
                    date=snapshot_date,
                    total_cost=random.uniform(50, 500) * (1 + random.uniform(-0.2, 0.2)),
                    currency="USD",
                    service_name=service,
                    synced_at=datetime.utcnow(),
                )
                db.add(cost)

    db.commit()


def seed_compliance(db, tenants):
    """Create sample compliance data."""
    import random

    for tenant in tenants:
        compliance = ComplianceSnapshot(
            tenant_id=tenant.id,
            subscription_id=tenant.subscriptions[0].subscription_id,
            snapshot_date=datetime.utcnow(),
            overall_compliance_percent=random.uniform(75, 98),
            secure_score=random.uniform(60, 90),
            compliant_resources=random.randint(100, 500),
            non_compliant_resources=random.randint(5, 50),
            exempt_resources=random.randint(0, 10),
            synced_at=datetime.utcnow(),
        )
        db.add(compliance)

        # Add some policy states
        policies = [
            ("Require tag on resources", "Tags", random.randint(5, 20)),
            ("Allowed locations", "General", random.randint(0, 5)),
            ("Require HTTPS for storage", "Storage", random.randint(2, 10)),
            ("Audit VMs without managed disks", "Compute", random.randint(0, 8)),
        ]

        for policy_name, category, violations in policies:
            state = PolicyState(
                tenant_id=tenant.id,
                subscription_id=tenant.subscriptions[0].subscription_id,
                policy_definition_id=f"/providers/Microsoft.Authorization/policyDefinitions/{uuid.uuid4()}",
                policy_name=policy_name,
                policy_category=category,
                compliance_state="NonCompliant" if violations > 0 else "Compliant",
                non_compliant_count=violations,
                synced_at=datetime.utcnow(),
            )
            db.add(state)

    db.commit()


def seed_resources(db, tenants):
    """Create sample resource data."""
    import json
    import random

    resource_types = [
        "Microsoft.Compute/virtualMachines",
        "Microsoft.Storage/storageAccounts",
        "Microsoft.Sql/servers",
        "Microsoft.Web/sites",
        "Microsoft.KeyVault/vaults",
        "Microsoft.Network/virtualNetworks",
    ]

    locations = ["eastus", "westus2", "centralus", "westeurope"]

    for tenant in tenants:
        for i in range(random.randint(20, 50)):
            resource_type = random.choice(resource_types)
            tags = {
                "Environment": random.choice(["Production", "Development", "Staging"]),
                "Owner": random.choice(["team-a@company.com", "team-b@company.com"]),
            }
            if random.random() > 0.3:
                tags["CostCenter"] = random.choice(["CC001", "CC002", "CC003"])
            if random.random() > 0.5:
                tags["Application"] = random.choice(["app-1", "app-2", "app-3"])

            resource = Resource(
                id=f"/subscriptions/{tenant.subscriptions[0].subscription_id}/resourceGroups/rg-{i}/providers/{resource_type}/resource-{i}",
                tenant_id=tenant.id,
                subscription_id=tenant.subscriptions[0].subscription_id,
                resource_group=f"rg-{i % 5}",
                resource_type=resource_type,
                name=f"resource-{i}",
                location=random.choice(locations),
                provisioning_state="Succeeded",
                tags_json=json.dumps(tags),
                is_orphaned=1 if random.random() > 0.9 else 0,
                estimated_monthly_cost=random.uniform(10, 500) if random.random() > 0.5 else None,
                synced_at=datetime.utcnow(),
            )
            db.add(resource)

    db.commit()


def seed_identity(db, tenants):
    """Create sample identity data."""
    import random

    for tenant in tenants:
        total_users = random.randint(100, 500)
        guest_users = random.randint(10, 50)
        mfa_enabled = int(total_users * random.uniform(0.7, 0.95))

        identity = IdentitySnapshot(
            tenant_id=tenant.id,
            snapshot_date=date.today(),
            total_users=total_users,
            active_users=int(total_users * 0.9),
            guest_users=guest_users,
            mfa_enabled_users=mfa_enabled,
            mfa_disabled_users=total_users - mfa_enabled,
            privileged_users=random.randint(5, 20),
            stale_accounts_30d=random.randint(5, 20),
            stale_accounts_90d=random.randint(2, 10),
            service_principals=random.randint(20, 100),
            synced_at=datetime.utcnow(),
        )
        db.add(identity)

        # Add privileged users
        roles = [
            "Global Administrator",
            "User Administrator",
            "Billing Administrator",
            "Security Administrator",
        ]

        for i in range(random.randint(5, 15)):
            priv_user = PrivilegedUser(
                tenant_id=tenant.id,
                user_principal_name=f"admin{i}@tenant.onmicrosoft.com",
                display_name=f"Admin User {i}",
                user_type=random.choice(["Member", "Member", "Member", "Guest"]),
                role_name=random.choice(roles),
                role_scope="/",
                is_permanent=1 if random.random() > 0.3 else 0,
                mfa_enabled=1 if random.random() > 0.1 else 0,
                last_sign_in=datetime.utcnow() - timedelta(days=random.randint(0, 60)),
                synced_at=datetime.utcnow(),
            )
            db.add(priv_user)

    db.commit()


def main():
    """Seed the database."""
    print("Initializing database...")
    init_db()

    print("Seeding data...")
    db = SessionLocal()

    try:
        # Check if data already exists
        existing = db.query(Tenant).first()
        if existing:
            print("Database already seeded. Clear data/ folder to re-seed.")
            return

        tenants = seed_tenants(db)
        print(f"  ✓ Created {len(tenants)} tenants")

        seed_costs(db, tenants)
        print("  ✓ Created cost data")

        seed_compliance(db, tenants)
        print("  ✓ Created compliance data")

        seed_resources(db, tenants)
        print("  ✓ Created resource inventory")

        seed_identity(db, tenants)
        print("  ✓ Created identity data")

        print("\nSeeding complete! Run 'uvicorn app.main:app --reload' to start.")

    finally:
        db.close()


if __name__ == "__main__":
    main()
