#!/usr/bin/env python3
"""Comprehensive seed data for Azure Governance Platform.

Populates ALL models with realistic demo data for 5 HTT brand tenants.
Creates 30 days of time-series data for dashboards and trend charts.

Usage:
    uv run python scripts/seed_data.py           # Seed (skip if data exists)
    uv run python scripts/seed_data.py --force    # Drop and re-seed
    uv run python scripts/seed_data.py --dry-run  # Preview only
"""

import json
import random
import sys
import uuid
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import Base, SessionLocal, engine, init_db
from app.models.brand_config import BrandConfig
from app.models.compliance import ComplianceSnapshot, PolicyState
from app.models.cost import CostAnomaly, CostSnapshot
from app.models.dmarc import DKIMRecord, DMARCAlert, DMARCRecord, DMARCReport
from app.models.identity import IdentitySnapshot, PrivilegedUser
from app.models.monitoring import Alert, SyncJobLog, SyncJobMetrics
from app.models.recommendation import Recommendation
from app.models.resource import IdleResource, Resource, ResourceTag
from app.models.riverside import (
    RiversideCompliance,
    RiversideDeviceCompliance,
    RiversideMFA,
    RiversideRequirement,
    RiversideThreatData,
)
from app.models.sync import SyncJob
from app.models.tenant import Subscription, Tenant, UserTenant

# ── Constants ───────────────────────────────────────────────────
NOW = datetime.now(UTC)
TODAY = date.today()
DEADLINE = date(2026, 7, 8)

TENANT_DEFS = [
    {
        "name": "HTT Brands Corporate",
        "tenant_id": "aaaaaaaa-1111-4000-a000-000000000001",
        "desc": "Corporate HQ — all shared services",
        "brand_key": "httbrands",
        "primary": "#500711",
        "secondary": "#BB86FC",
        "accent": "#FFC957",
    },
    {
        "name": "Bishops Cuts & Color",
        "tenant_id": "bbbbbbbb-2222-4000-b000-000000000002",
        "desc": "Bishops salon franchise operations",
        "brand_key": "bishops",
        "primary": "#c2410c",
        "secondary": "#F59E0B",
        "accent": "#3B82F6",
    },
    {
        "name": "Frenchies Modern Nail Care",
        "tenant_id": "cccccccc-3333-4000-c000-000000000003",
        "desc": "Frenchies franchise & e-commerce",
        "brand_key": "frenchies",
        "primary": "#2563eb",
        "secondary": "#8B5CF6",
        "accent": "#EC4899",
    },
    {
        "name": "The Lash Lounge",
        "tenant_id": "dddddddd-4444-4000-d000-000000000004",
        "desc": "The Lash Lounge franchise network",
        "brand_key": "lashlounge",
        "primary": "#7c3aed",
        "secondary": "#EC4899",
        "accent": "#F59E0B",
    },
    {
        "name": "Delta Crown Enterprises",
        "tenant_id": "eeeeeeee-5555-4000-e000-000000000005",
        "desc": "Delta Crown PE portfolio oversight",
        "brand_key": "deltacrown",
        "primary": "#004538",
        "secondary": "#10B981",
        "accent": "#F59E0B",
    },
]

AZURE_LOCATIONS = ["eastus", "eastus2", "westus2", "centralus", "westeurope", "northeurope"]
RESOURCE_TYPES = [
    (
        "Microsoft.Compute/virtualMachines",
        "vm",
        ["Standard_D2s_v3", "Standard_B2s", "Standard_D4s_v3"],
    ),
    ("Microsoft.Storage/storageAccounts", "st", ["Standard_LRS", "Standard_GRS"]),
    ("Microsoft.Sql/servers/databases", "sqldb", ["S0", "S1", "Basic"]),
    ("Microsoft.Web/sites", "app", ["F1", "B1", "S1"]),
    ("Microsoft.KeyVault/vaults", "kv", ["standard"]),
    ("Microsoft.Network/virtualNetworks", "vnet", [None]),
    ("Microsoft.Network/publicIPAddresses", "pip", ["Standard"]),
    ("Microsoft.ContainerRegistry/registries", "acr", ["Basic", "Standard"]),
]
SERVICE_NAMES = [
    "Virtual Machines",
    "Storage",
    "SQL Database",
    "App Service",
    "Azure Functions",
    "Key Vault",
    "Virtual Network",
    "Container Registry",
    "Azure Monitor",
    "Application Insights",
]
POLICY_DEFS = [
    ("Require tags on resources", "Tags", 0.35),
    ("Allowed locations — US only", "General", 0.10),
    ("Require HTTPS for storage accounts", "Storage", 0.15),
    ("Audit VMs without managed disks", "Compute", 0.20),
    ("Enforce network security groups", "Network", 0.12),
    ("Require encryption at rest", "Security", 0.08),
    ("Audit SQL servers without auditing", "SQL", 0.18),
    ("Deny public IP addresses", "Network", 0.22),
]
ADMIN_NAMES = [
    "Tyler Granlund",
    "Sarah Chen",
    "Marcus Williams",
    "Jessica Patel",
    "David Kim",
    "Emily Rodriguez",
    "James Thompson",
    "Aisha Mohammed",
    "Robert Garcia",
    "Lisa Nakamura",
    "Chris Anderson",
    "Priya Sharma",
]
ADMIN_ROLES = [
    "Global Administrator",
    "User Administrator",
    "Security Administrator",
    "Billing Administrator",
    "Application Administrator",
    "Exchange Administrator",
    "Compliance Administrator",
]
DOMAINS = {
    "httbrands": ["httbrands.com", "htt.io"],
    "bishops": ["bishopscuts.com", "bishops.style"],
    "frenchies": ["frenchiesnails.com", "frenchies.beauty"],
    "lashlounge": ["thelashlounge.com", "lashlounge.beauty"],
    "deltacrown": ["deltacrown.com", "dce-portfolio.com"],
}


# ── Helpers ─────────────────────────────────────────────────────
def uid() -> str:
    return str(uuid.uuid4())


def past(days: int) -> datetime:
    return NOW - timedelta(days=days)


def past_date(days: int) -> date:
    return TODAY - timedelta(days=days)


def jitter(base: float, pct: float = 0.15) -> float:
    """Add realistic noise to a value."""
    return base * (1 + random.uniform(-pct, pct))


# ── Seed Functions ──────────────────────────────────────────────
def seed_tenants_and_brands(db) -> list[dict]:
    """Create 5 HTT brand tenants with brand configs and subscriptions."""
    results = []
    for t in TENANT_DEFS:
        tid = uid()
        tenant = Tenant(
            id=tid,
            name=t["name"],
            tenant_id=t["tenant_id"],
            description=t["desc"],
            is_active=True,
            created_at=past(180),
        )
        db.add(tenant)

        # Brand config
        db.add(
            BrandConfig(
                id=uid(),
                tenant_id=tid,
                brand_name=t["name"],
                primary_color=t["primary"],
                secondary_color=t["secondary"],
                accent_color=t["accent"],
                brand_key=t["brand_key"],
                heading_font="Inter",
                body_font="Inter",
            )
        )

        # 2–3 subscriptions per tenant
        subs = []
        for env in ["Production", "Development", "Staging"][: random.randint(2, 3)]:
            sub_id = uid()
            sub = Subscription(
                id=uid(),
                tenant_ref=tid,
                subscription_id=sub_id,
                display_name=f"{t['name'].split()[0]} — {env}",
                state="Enabled",
                synced_at=past(0),
            )
            db.add(sub)
            subs.append({"id": sub_id, "env": env})

        results.append({"id": tid, "def": t, "subs": subs})

    db.flush()  # Get IDs without full commit
    return results


def seed_costs(db, tenants: list[dict]):
    """30 days of cost data with realistic trends per tenant."""
    for t in tenants:
        base_daily = random.uniform(800, 4000)  # Bigger tenants spend more
        sub = t["subs"][0]  # Costs on production sub
        for day_offset in range(30):
            d = past_date(day_offset)
            # Weekends are cheaper
            weekend_factor = 0.6 if d.weekday() >= 5 else 1.0
            for svc in random.sample(SERVICE_NAMES, random.randint(4, 7)):
                svc_base = base_daily * random.uniform(0.05, 0.25) * weekend_factor
                db.add(
                    CostSnapshot(
                        tenant_id=t["id"],
                        subscription_id=sub["id"],
                        date=d,
                        total_cost=round(jitter(svc_base), 2),
                        currency="USD",
                        service_name=svc,
                        meter_category=svc,
                        synced_at=past(day_offset),
                    )
                )

    # Sprinkle in a few cost anomalies
    for t in random.sample(tenants, 3):
        sub = t["subs"][0]
        db.add(
            CostAnomaly(
                tenant_id=t["id"],
                subscription_id=sub["id"],
                detected_at=past(random.randint(1, 7)),
                anomaly_type=random.choice(["spike", "unusual_service", "new_resource"]),
                description=random.choice(
                    [
                        "VM scale-out triggered 3x cost increase on Standard_D4s_v3 pool",
                        "Unexpected Azure Functions consumption spike — 2M executions in 1hr",
                        "New Application Gateway deployed without cost tag",
                        "Storage egress 400% above 30-day average",
                    ]
                ),
                expected_cost=round(random.uniform(200, 800), 2),
                actual_cost=round(random.uniform(1200, 3500), 2),
                percentage_change=round(random.uniform(45, 300), 1),
                service_name=random.choice(SERVICE_NAMES),
                is_acknowledged=random.choice([True, False]),
            )
        )

    db.flush()


def seed_compliance(db, tenants: list[dict]):
    """Compliance snapshots over 30 days + policy states."""
    for t in tenants:
        sub = t["subs"][0]
        base_compliance = random.uniform(78, 96)
        for day_offset in range(30):
            # Compliance slowly improving over time
            trend = (
                day_offset * 0.1
            )  # Gets better as days increase (going back in time, so reverse)
            score = min(99.5, max(60, base_compliance - trend + random.uniform(-1, 1)))
            compliant = random.randint(150, 400)
            non_compliant = random.randint(5, int(compliant * (1 - score / 100) * 2))
            db.add(
                ComplianceSnapshot(
                    tenant_id=t["id"],
                    subscription_id=sub["id"],
                    snapshot_date=past(day_offset),
                    overall_compliance_percent=round(score, 1),
                    secure_score=round(score * random.uniform(0.85, 1.0), 1),
                    compliant_resources=compliant,
                    non_compliant_resources=non_compliant,
                    exempt_resources=random.randint(0, 8),
                    synced_at=past(day_offset),
                )
            )

        # Policy states (current)
        for policy_name, category, violation_rate in POLICY_DEFS:
            violations = random.randint(0, int(50 * violation_rate))
            db.add(
                PolicyState(
                    tenant_id=t["id"],
                    subscription_id=sub["id"],
                    policy_definition_id=f"/providers/Microsoft.Authorization/policyDefinitions/{uid()}",
                    policy_name=policy_name,
                    policy_category=category,
                    compliance_state="NonCompliant" if violations > 0 else "Compliant",
                    non_compliant_count=violations,
                    recommendation=f"Review {violations} resources for {policy_name.lower()}"
                    if violations
                    else None,
                    synced_at=past(0),
                )
            )

    db.flush()


def seed_resources(db, tenants: list[dict]):
    """Rich resource inventory with tags, idle resources."""
    for t in tenants:
        sub = t["subs"][0]
        resource_count = random.randint(25, 60)
        resource_ids = []

        for i in range(resource_count):
            rtype, prefix, skus = random.choice(RESOURCE_TYPES)
            rg = f"rg-{t['def']['brand_key']}-{random.choice(['prod', 'dev', 'shared', 'data', 'network'])}"
            name = f"{prefix}-{t['def']['brand_key']}-{i:03d}"
            rid = f"/subscriptions/{sub['id']}/resourceGroups/{rg}/providers/{rtype}/{name}"
            tags = {
                "Environment": random.choice(["Production", "Development", "Staging"]),
                "Owner": random.choice(ADMIN_NAMES[:4]),
                "Brand": t["def"]["name"],
            }
            if random.random() > 0.3:
                tags["CostCenter"] = random.choice(
                    ["CC-HTT-001", "CC-BCC-002", "CC-FN-003", "CC-TLL-004"]
                )
            if random.random() > 0.4:
                tags["Application"] = random.choice(
                    ["governance-platform", "salon-booking", "e-commerce", "crm"]
                )

            db.add(
                Resource(
                    id=rid,
                    tenant_id=t["id"],
                    subscription_id=sub["id"],
                    resource_group=rg,
                    resource_type=rtype,
                    name=name,
                    location=random.choice(AZURE_LOCATIONS),
                    provisioning_state="Succeeded",
                    sku=random.choice(skus),
                    tags_json=json.dumps(tags),
                    is_orphaned=1 if random.random() > 0.92 else 0,
                    estimated_monthly_cost=round(random.uniform(5, 800), 2)
                    if random.random() > 0.3
                    else None,
                    synced_at=past(0),
                )
            )
            resource_ids.append(rid)

            # Tags
            for tag_name, tag_value in tags.items():
                db.add(
                    ResourceTag(
                        resource_id=rid,
                        tag_name=tag_name,
                        tag_value=tag_value,
                        is_required=1 if tag_name in ("Environment", "Owner") else 0,
                        synced_at=past(0),
                    )
                )

        # Idle resources (10-15% of total)
        for rid in random.sample(resource_ids, max(2, resource_count // 8)):
            db.add(
                IdleResource(
                    resource_id=rid,
                    tenant_id=t["id"],
                    subscription_id=sub["id"],
                    idle_type=random.choice(
                        ["low_cpu", "no_connections", "zero_traffic", "unused_disk"]
                    ),
                    description=random.choice(
                        [
                            "CPU avg < 2% for 14 days",
                            "Zero inbound connections for 21 days",
                            "No network traffic for 30 days",
                            "Disk unattached for 60 days",
                            "App Service receiving 0 requests for 14 days",
                        ]
                    ),
                    estimated_monthly_savings=round(random.uniform(15, 350), 2),
                    idle_days=random.randint(7, 90),
                    detected_at=past(random.randint(1, 14)),
                )
            )

    db.flush()


def seed_identity(db, tenants: list[dict]):
    """Identity snapshots over 30 days + privileged users."""
    for t in tenants:
        base_users = random.randint(80, 500)
        for day_offset in range(30):
            total = base_users + random.randint(-5, 5)
            mfa_pct = random.uniform(0.78, 0.96)
            mfa_enabled = int(total * mfa_pct)
            db.add(
                IdentitySnapshot(
                    tenant_id=t["id"],
                    snapshot_date=past_date(day_offset),
                    total_users=total,
                    active_users=int(total * random.uniform(0.82, 0.95)),
                    guest_users=random.randint(5, 45),
                    mfa_enabled_users=mfa_enabled,
                    mfa_disabled_users=total - mfa_enabled,
                    privileged_users=random.randint(4, 18),
                    stale_accounts_30d=random.randint(3, 18),
                    stale_accounts_90d=random.randint(1, 8),
                    service_principals=random.randint(15, 80),
                    synced_at=past(day_offset),
                )
            )

        # Privileged users
        used_names = random.sample(ADMIN_NAMES, min(len(ADMIN_NAMES), random.randint(5, 12)))
        for name in used_names:
            email = name.lower().replace(" ", ".") + f"@{t['def']['brand_key']}.onmicrosoft.com"
            db.add(
                PrivilegedUser(
                    tenant_id=t["id"],
                    user_principal_name=email,
                    display_name=name,
                    user_type=random.choices(["Member", "Guest"], weights=[85, 15])[0],
                    role_name=random.choice(ADMIN_ROLES),
                    role_scope="/",
                    is_permanent=1 if random.random() > 0.35 else 0,
                    mfa_enabled=1 if random.random() > 0.08 else 0,
                    last_sign_in=past(random.randint(0, 45)),
                    synced_at=past(0),
                )
            )

    db.flush()


def seed_sync_history(db, tenants: list[dict]):
    """Sync job logs, metrics, and alerts."""
    job_types = ["costs", "compliance", "resources", "identity"]

    for jt in job_types:
        # 30 days of sync runs (1-2x per day)
        total_runs, successes, failures = 0, 0, 0
        durations = []
        for day_offset in range(30):
            for _run in range(random.randint(1, 2)):
                started = past(day_offset) + timedelta(hours=random.randint(0, 12))
                duration_ms = random.randint(800, 25000)
                status = random.choices(["completed", "failed"], weights=[95, 5])[0]
                records = random.randint(50, 500) if status == "completed" else 0

                db.add(
                    SyncJobLog(
                        job_type=jt,
                        tenant_id=random.choice(tenants)["id"],
                        status=status,
                        started_at=started,
                        ended_at=started + timedelta(milliseconds=duration_ms),
                        duration_ms=duration_ms,
                        records_processed=records,
                        records_created=int(records * 0.1),
                        records_updated=int(records * 0.8),
                        errors_count=random.randint(1, 5) if status == "failed" else 0,
                        error_message="Azure API throttled (429)" if status == "failed" else None,
                    )
                )

                # Also create legacy SyncJob records
                db.add(
                    SyncJob(
                        job_type=jt,
                        tenant_id=random.choice(tenants)["id"],
                        status=status,
                        started_at=started,
                        completed_at=started + timedelta(milliseconds=duration_ms),
                        records_processed=records,
                    )
                )

                total_runs += 1
                if status == "completed":
                    successes += 1
                else:
                    failures += 1
                durations.append(duration_ms)

        # Aggregated metrics per job type
        db.add(
            SyncJobMetrics(
                job_type=jt,
                total_runs=total_runs,
                successful_runs=successes,
                failed_runs=failures,
                avg_duration_ms=sum(durations) / len(durations),
                min_duration_ms=min(durations),
                max_duration_ms=max(durations),
                avg_records_processed=random.uniform(100, 300),
                total_records_processed=total_runs * random.randint(100, 300),
                total_errors=failures,
                success_rate=round(successes / total_runs, 3),
                last_run_at=past(0),
                last_success_at=past(0),
                last_failure_at=past(random.randint(1, 7)) if failures else None,
            )
        )

    # Alerts
    alert_templates = [
        (
            "sync_failure",
            "warning",
            "Compliance sync failed for {tenant}",
            "Sync returned HTTP 429. Retry scheduled in 5 minutes.",
        ),
        (
            "stale_sync",
            "warning",
            "Cost data stale for {tenant}",
            "Last successful sync was 8 hours ago — threshold is 6 hours.",
        ),
        (
            "high_error_rate",
            "error",
            "High error rate on identity sync",
            "12% error rate over the last 24 hours (threshold: 5%).",
        ),
        (
            "no_records",
            "info",
            "No new resources detected for {tenant}",
            "Resources sync completed but found 0 new records — verify API permissions.",
        ),
    ]
    for _ in range(random.randint(5, 12)):
        template = random.choice(alert_templates)
        t = random.choice(tenants)
        is_resolved = random.random() > 0.4
        db.add(
            Alert(
                alert_type=template[0],
                severity=template[1],
                job_type=random.choice(job_types),
                tenant_id=t["id"],
                title=template[2].format(tenant=t["def"]["name"]),
                message=template[3],
                is_resolved=1 if is_resolved else 0,
                created_at=past(random.randint(0, 14)),
                resolved_at=past(random.randint(0, 3)) if is_resolved else None,
                resolved_by="tyler.granlund@httbrands.com" if is_resolved else None,
            )
        )

    db.flush()


def seed_recommendations(db, tenants: list[dict]):
    """Cost optimization and security recommendations."""
    rec_templates = [
        (
            "cost_optimization",
            "idle_vm",
            "Shut down idle VM {name}",
            "VM has < 2% CPU utilization over 14 days",
            "High",
            180,
        ),
        (
            "cost_optimization",
            "right_size_vm",
            "Right-size {name} from D4s to D2s",
            "VM consistently uses < 25% of allocated CPU",
            "Medium",
            95,
        ),
        (
            "cost_optimization",
            "reserved_instance",
            "Purchase RI for {name}",
            "VM has been running 24/7 for 90+ days",
            "High",
            420,
        ),
        (
            "security",
            "unencrypted_storage",
            "Enable encryption on {name}",
            "Storage account does not have encryption at rest enabled",
            "Critical",
            None,
        ),
        (
            "security",
            "open_nsg",
            "Restrict NSG rules on {name}",
            "Network security group allows inbound traffic on all ports",
            "Critical",
            None,
        ),
        (
            "performance",
            "slow_query",
            "Optimize SQL queries on {name}",
            "P95 query latency > 2s on 3 queries",
            "Medium",
            None,
        ),
        (
            "reliability",
            "no_backup",
            "Enable backup for {name}",
            "SQL database has no point-in-time restore configured",
            "High",
            None,
        ),
    ]

    for t in tenants:
        for _ in range(random.randint(3, 8)):
            tmpl = random.choice(rec_templates)
            name = f"resource-{t['def']['brand_key']}-{random.randint(1, 50):03d}"
            db.add(
                Recommendation(
                    tenant_id=t["id"],
                    subscription_id=t["subs"][0]["id"],
                    category=tmpl[0],
                    recommendation_type=tmpl[1],
                    title=tmpl[2].format(name=name),
                    description=tmpl[3],
                    impact=tmpl[4],
                    potential_savings_monthly=round(tmpl[5] * random.uniform(0.8, 1.3), 2)
                    if tmpl[5]
                    else None,
                    potential_savings_annual=round(tmpl[5] * 12 * random.uniform(0.8, 1.3), 2)
                    if tmpl[5]
                    else None,
                    resource_name=name,
                    implementation_effort=random.choice(["Low", "Medium", "High"]),
                    is_dismissed=0,
                    created_at=past(random.randint(1, 30)),
                )
            )

    db.flush()


def seed_dmarc(db, tenants: list[dict]):
    """DMARC/DKIM records and alerts for all tenant domains."""
    for t in tenants:
        brand_key = t["def"]["brand_key"]
        domains = DOMAINS.get(brand_key, [f"{brand_key}.com"])

        for domain in domains:
            # DMARC record
            policy = random.choices(["reject", "quarantine", "none"], weights=[50, 30, 20])[0]
            db.add(
                DMARCRecord(
                    id=uid(),
                    tenant_id=t["id"],
                    domain=domain,
                    policy=policy,
                    pct=100 if policy == "reject" else random.choice([50, 75, 100]),
                    rua=f"mailto:dmarc-rua@{domain}",
                    ruf=f"mailto:dmarc-ruf@{domain}",
                    adkim="s" if policy == "reject" else "r",
                    aspf="s" if policy == "reject" else "r",
                    is_valid=True,
                    synced_at=past(0),
                )
            )

            # DKIM record
            is_enabled = random.random() > 0.15
            db.add(
                DKIMRecord(
                    id=uid(),
                    tenant_id=t["id"],
                    domain=domain,
                    selector="selector1",
                    is_enabled=is_enabled,
                    is_aligned=is_enabled and random.random() > 0.2,
                    key_size=2048,
                    synced_at=past(0),
                )
            )

            # DMARC aggregate reports (last 30 days)
            for day_offset in range(30):
                passed = random.randint(800, 5000)
                failed = random.randint(0, int(passed * 0.05))
                total = passed + failed
                dkim_p = int(passed * random.uniform(0.9, 1.0))
                spf_p = int(passed * random.uniform(0.92, 1.0))
                db.add(
                    DMARCReport(
                        id=uid(),
                        tenant_id=t["id"],
                        domain=domain,
                        report_date=past(day_offset),
                        messages_total=total,
                        messages_passed=passed,
                        messages_failed=failed,
                        pct_compliant=round(passed / total * 100, 1) if total else 0,
                        dkim_passed=dkim_p,
                        dkim_failed=total - dkim_p,
                        spf_passed=spf_p,
                        spf_failed=total - spf_p,
                        both_passed=min(dkim_p, spf_p),
                        both_failed=max(0, failed - random.randint(0, failed // 2)),
                        source_ip_count=random.randint(5, 50),
                        reporter=random.choice(["google.com", "microsoft.com", "amazonses.com"]),
                        synced_at=past(day_offset),
                    )
                )

        # A few DMARC alerts
        if random.random() > 0.5:
            db.add(
                DMARCAlert(
                    id=uid(),
                    tenant_id=t["id"],
                    domain=random.choice(domains),
                    alert_type=random.choice(
                        ["policy_none", "dkim_disabled", "high_failure_rate", "spf_misconfigured"]
                    ),
                    severity=random.choice(["critical", "high", "medium"]),
                    message=random.choice(
                        [
                            "DMARC policy is set to 'none' — emails are not protected from spoofing",
                            "DKIM is disabled — email authentication cannot be verified",
                            "Failure rate exceeded 5% threshold in last 24 hours",
                            "SPF record includes more than 10 DNS lookups",
                        ]
                    ),
                    is_acknowledged=random.choice([True, False]),
                    created_at=past(random.randint(0, 14)),
                )
            )

    db.flush()


def seed_riverside(db, tenants: list[dict]):
    """Riverside compliance data — maturity scores, MFA, devices, requirements."""
    categories = ["IAM", "GS", "DS"]
    priorities = ["P0", "P1", "P2"]
    statuses = ["not_started", "in_progress", "completed", "blocked"]

    for t in tenants:
        maturity = round(random.uniform(1.5, 3.8), 1)
        completed_reqs = random.randint(8, 25)
        total_reqs = random.randint(30, 45)

        db.add(
            RiversideCompliance(
                tenant_id=t["id"],
                overall_maturity_score=maturity,
                target_maturity_score=3.0,
                deadline_date=DEADLINE,
                financial_risk="$4M",
                critical_gaps_count=random.randint(0, 8),
                requirements_completed=completed_reqs,
                requirements_total=total_reqs,
                last_assessment_date=past(random.randint(0, 3)),
            )
        )

        # MFA coverage
        total_users = random.randint(50, 300)
        mfa_users = int(total_users * random.uniform(0.75, 0.98))
        admin_total = random.randint(5, 15)
        admin_mfa = int(admin_total * random.uniform(0.85, 1.0))
        db.add(
            RiversideMFA(
                tenant_id=t["id"],
                total_users=total_users,
                mfa_enrolled_users=mfa_users,
                mfa_coverage_percentage=round(mfa_users / total_users * 100, 1),
                admin_accounts_total=admin_total,
                admin_accounts_mfa=admin_mfa,
                admin_mfa_percentage=round(admin_mfa / admin_total * 100, 1),
                unprotected_users=total_users - mfa_users,
                snapshot_date=NOW,
            )
        )

        # Device compliance
        total_devices = random.randint(30, 200)
        compliant_devices = int(total_devices * random.uniform(0.7, 0.95))
        db.add(
            RiversideDeviceCompliance(
                tenant_id=t["id"],
                total_devices=total_devices,
                mdm_enrolled=int(total_devices * random.uniform(0.8, 0.98)),
                edr_covered=int(total_devices * random.uniform(0.7, 0.95)),
                encrypted_devices=int(total_devices * random.uniform(0.75, 0.98)),
                compliant_devices=compliant_devices,
                compliance_percentage=round(compliant_devices / total_devices * 100, 1),
                snapshot_date=NOW,
            )
        )

        # Threat data
        db.add(
            RiversideThreatData(
                tenant_id=t["id"],
                threat_score=round(random.uniform(15, 75), 1),
                vulnerability_count=random.randint(2, 30),
                malicious_domain_alerts=random.randint(0, 8),
                peer_comparison_percentile=random.randint(40, 90),
                snapshot_date=NOW,
            )
        )

        # Requirements
        req_id = 1
        for cat in categories:
            for _ in range(random.randint(8, 15)):
                status = random.choices(statuses, weights=[15, 25, 50, 10])[0]
                priority = random.choices(priorities, weights=[20, 40, 40])[0]
                db.add(
                    RiversideRequirement(
                        tenant_id=t["id"],
                        requirement_id=f"RS-{cat}-{req_id:03d}",
                        category=cat,
                        priority=priority,
                        title=f"Implement {cat} control #{req_id}",
                        description=f"Detailed requirement for {cat} category, priority {priority}",
                        status=status,
                        due_date=DEADLINE - timedelta(days=random.randint(0, 180)),
                        owner=random.choice(ADMIN_NAMES[:6]),
                        completed_date=TODAY if status == "completed" else None,
                    )
                )
                req_id += 1

    db.flush()


def seed_user_tenants(db, tenants: list[dict]):
    """User-tenant access mappings."""
    users = [
        ("tyler.granlund@httbrands.com", "admin"),
        ("sarah.chen@httbrands.com", "operator"),
        ("marcus.williams@httbrands.com", "viewer"),
        ("jessica.patel@httbrands.com", "operator"),
    ]

    for email, role in users:
        for t in tenants:
            db.add(
                UserTenant(
                    id=uid(),
                    user_id=email,
                    tenant_id=t["id"],
                    role=role,
                    is_active=True,
                    can_manage_resources=role in ("admin", "operator"),
                    can_view_costs=True,
                    can_manage_compliance=role == "admin",
                    granted_by="system",
                    granted_at=past(180),
                )
            )

    db.flush()


# ── Main ────────────────────────────────────────────────────────
def main():
    import argparse

    parser = argparse.ArgumentParser(description="Seed Azure Governance Platform database")
    parser.add_argument("--force", action="store_true", help="Drop all data and re-seed")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    args = parser.parse_args()

    print("🐶 Richard's Comprehensive Seed Script")
    print("=" * 50)

    if args.dry_run:
        print("DRY RUN — no data will be written\n")
        for t in TENANT_DEFS:
            print(f"  Would create tenant: {t['name']} ({t['brand_key']})")
        print(f"\n  Would create ~{len(TENANT_DEFS) * 30 * 5} cost snapshots")
        print(f"  Would create ~{len(TENANT_DEFS) * 30} compliance snapshots")
        print(f"  Would create ~{len(TENANT_DEFS) * 40} resources")
        print(f"  Would create ~{len(TENANT_DEFS) * 30} identity snapshots")
        print(f"  Would create ~{len(TENANT_DEFS) * 4} DMARC/DKIM records")
        print(f"  Would create ~{len(TENANT_DEFS) * 35} Riverside requirements")
        print("\nDone (dry run). No changes made.")
        return

    print("\nInitializing database...")
    init_db()

    db = SessionLocal()
    try:
        if args.force:
            print("⚠️  --force: Dropping all tables and recreating...")
            Base.metadata.drop_all(bind=engine)
            Base.metadata.create_all(bind=engine)
            print("  ✓ Tables recreated")
        else:
            existing = db.query(Tenant).first()
            if existing:
                print(f"\n⚠️  Database already has data (found tenant: {existing.name})")
                print("   Use --force to drop and re-seed, or delete data/governance.db")
                return

        random.seed(42)  # Reproducible data

        tenants = seed_tenants_and_brands(db)
        print(f"  ✓ {len(tenants)} tenants with brand configs")

        seed_costs(db, tenants)
        print("  ✓ 30 days of cost data + anomalies")

        seed_compliance(db, tenants)
        print("  ✓ 30 days of compliance snapshots + policy states")

        seed_resources(db, tenants)
        print("  ✓ Resources, tags, and idle resource detection")

        seed_identity(db, tenants)
        print("  ✓ 30 days of identity snapshots + privileged users")

        seed_sync_history(db, tenants)
        print("  ✓ Sync job logs, metrics, and alerts")

        seed_recommendations(db, tenants)
        print("  ✓ Cost & security recommendations")

        seed_dmarc(db, tenants)
        print("  ✓ DMARC/DKIM records, reports, and alerts")

        seed_riverside(db, tenants)
        print("  ✓ Riverside compliance, MFA, devices, requirements")

        seed_user_tenants(db, tenants)
        print("  ✓ User-tenant access mappings")

        db.commit()
        print("\n🎉 Seeding complete! All dashboards should now show data.")
        print("   Run: uvicorn app.main:app --reload")

    except Exception as e:
        db.rollback()
        print(f"\n❌ Seed failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
