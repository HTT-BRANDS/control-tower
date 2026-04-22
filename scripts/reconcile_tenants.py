"""Reconcile ``config/tenants.yaml`` <-> DB ``tenants`` table.

This script is the authoritative tool for detecting and fixing drift between
the YAML-declared tenant inventory and the actual rows in the database.

Origin: bd-c7aa (DCE was is_active=False in DB but is_active=True in YAML,
so it never showed up in sync jobs or /health/data). The underlying class
of bug is the same latent-footgun pattern as a1sb and sf24 -- a silent
config-vs-reality mismatch that no one noticed until it caused a symptom.

Detected drift classes:
  - Missing in DB: exists in YAML, no matching row
  - Extra in DB: row exists, not in YAML (reported only -- human review)
  - Name mismatches: same tenant_id, different display name
  - is_active mismatches: YAML says active, DB says inactive (or vice versa)

Usage::

    python scripts/reconcile_tenants.py            # dry-run (default)
    python scripts/reconcile_tenants.py --apply    # apply auto-fixable drift
    python scripts/reconcile_tenants.py --verbose  # debug logging

Auto-fix semantics (with --apply):
  - Missing-in-DB: inserts a new tenants row
  - is_active mismatch: updates db_row.is_active to match YAML
  - Name mismatch: reported only (renames need human review)
  - Extra in DB: reported only (could be intentional legacy data)

Exit code 0 on success (including clean dry-run); exit 1 if any drift
was detected in dry-run mode. Suitable for a CI / startup assertion.
"""

from __future__ import annotations

import argparse
import logging
import sys
import uuid
from dataclasses import dataclass

# Make 'app' importable when running from repo root
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))

# Import submodules directly to avoid pulling app.core.__init__ (which
# eagerly imports the scheduler + other heavy deps not needed here).
import importlib

_db = importlib.import_module("app.core.database")
_tc = importlib.import_module("app.core.tenants_config")
_tm = importlib.import_module("app.models.tenant")

SessionLocal = _db.SessionLocal
TenantConfig = _tc.TenantConfig
get_active_tenants = _tc.get_active_tenants
Tenant = _tm.Tenant

logger = logging.getLogger("reconcile_tenants")


# ---------------------------------------------------------------------------
# Drift detection
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Drift:
    """Result of comparing YAML tenants to DB tenants."""

    missing_in_db: list[TenantConfig]  # exists in YAML, not in DB
    extra_in_db: list[Tenant]  # exists in DB, not in YAML
    name_mismatches: list[tuple[TenantConfig, Tenant]]  # same tenant_id, different name
    active_mismatches: list[tuple[TenantConfig, Tenant]]  # is_active disagrees

    @property
    def has_drift(self) -> bool:
        return bool(
            self.missing_in_db or self.extra_in_db or self.name_mismatches or self.active_mismatches
        )


def detect_drift(yaml_tenants: dict[str, TenantConfig], db_tenants: list[Tenant]) -> Drift:
    """Compare YAML and DB tenant inventories. Returns structured drift report."""
    # Index DB tenants by their azure tenant_id (the stable identifier)
    db_by_tid = {t.tenant_id: t for t in db_tenants}

    missing: list[TenantConfig] = []
    name_mismatches: list[tuple[TenantConfig, Tenant]] = []
    active_mismatches: list[tuple[TenantConfig, Tenant]] = []

    for cfg in yaml_tenants.values():
        db_row = db_by_tid.get(cfg.tenant_id)
        if db_row is None:
            missing.append(cfg)
            continue
        if db_row.name != cfg.name:
            name_mismatches.append((cfg, db_row))
        if bool(db_row.is_active) != bool(cfg.is_active):
            active_mismatches.append((cfg, db_row))

    yaml_tids = {cfg.tenant_id for cfg in yaml_tenants.values()}
    extra = [t for t in db_tenants if t.tenant_id not in yaml_tids]

    return Drift(
        missing_in_db=missing,
        extra_in_db=extra,
        name_mismatches=name_mismatches,
        active_mismatches=active_mismatches,
    )


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def render_report(drift: Drift) -> str:
    """Human-readable drift summary (stdout-friendly)."""
    lines: list[str] = []
    if drift.missing_in_db:
        lines.append(f"[MISSING-IN-DB] ({len(drift.missing_in_db)}):")
        for cfg in drift.missing_in_db:
            lines.append(f"   - {cfg.code} ({cfg.name}) tenant_id={cfg.tenant_id}")
    if drift.active_mismatches:
        lines.append(f"[IS_ACTIVE DRIFT] ({len(drift.active_mismatches)}):")
        for cfg, db in drift.active_mismatches:
            lines.append(f"   - {cfg.code} ({cfg.name}): YAML={cfg.is_active} DB={db.is_active}")
    if drift.name_mismatches:
        lines.append(f"[NAME MISMATCHES] ({len(drift.name_mismatches)}):")
        for cfg, db in drift.name_mismatches:
            lines.append(f"   - tenant_id={cfg.tenant_id}: YAML='{cfg.name}' DB='{db.name}'")
    if drift.extra_in_db:
        lines.append(f"[EXTRA-IN-DB] ({len(drift.extra_in_db)}) -- in DB but not YAML:")
        for t in drift.extra_in_db:
            lines.append(f"   - {t.name} tenant_id={t.tenant_id} (db id={t.id})")
    if not drift.has_drift:
        lines.append("[OK] No drift -- YAML and DB inventories match.")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Apply
# ---------------------------------------------------------------------------


def apply_fixes(drift: Drift) -> dict[str, list[str]]:
    """Apply auto-fixable drift. Returns a dict summarizing actions taken."""
    inserted: list[str] = []
    reactivated: list[str] = []
    deactivated: list[str] = []

    with SessionLocal() as session:
        # 1. Insert missing
        for cfg in drift.missing_in_db:
            row = Tenant(
                id=str(uuid.uuid4()),
                name=cfg.name,
                tenant_id=cfg.tenant_id,
                client_id=cfg.app_id,
                description=f"Reconciled from tenants.yaml (code={cfg.code})",
                is_active=cfg.is_active,
                use_lighthouse=False,
                use_oidc=cfg.oidc_enabled,
            )
            session.add(row)
            inserted.append(cfg.code)
            logger.info("Inserted tenant: %s (%s)", cfg.code, cfg.tenant_id)

        # 2. Fix is_active mismatches -- YAML is authoritative
        for cfg, db_row in drift.active_mismatches:
            db_row.is_active = bool(cfg.is_active)
            session.add(db_row)
            if cfg.is_active:
                reactivated.append(cfg.code)
                logger.info("Reactivated tenant: %s (%s)", cfg.code, cfg.tenant_id)
            else:
                deactivated.append(cfg.code)
                logger.info("Deactivated tenant: %s (%s)", cfg.code, cfg.tenant_id)

        session.commit()

    return {
        "inserted": inserted,
        "reactivated": reactivated,
        "deactivated": deactivated,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Detect and (optionally) fix drift between tenants.yaml and the DB."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply auto-fixable drift (default: dry-run)",
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s [%(name)s] %(message)s",
    )

    yaml_tenants = get_active_tenants()
    logger.info("Loaded %d tenants from YAML", len(yaml_tenants))

    with SessionLocal() as session:
        db_tenants = session.query(Tenant).all()
    logger.info("Loaded %d tenants from DB", len(db_tenants))

    drift = detect_drift(yaml_tenants, db_tenants)
    print(render_report(drift))

    if not drift.has_drift:
        return 0

    # Extras and name mismatches are reported but not auto-fixed
    if drift.extra_in_db or drift.name_mismatches:
        print(
            "\nNote: extras and name mismatches are reported only. Resolve manually after review."
        )

    if not args.apply:
        print("\nDry-run mode. Re-run with --apply to fix missing / is_active drift.")
        return 1

    summary = apply_fixes(drift)
    parts = []
    if summary["inserted"]:
        parts.append(f"inserted {len(summary['inserted'])}: {', '.join(summary['inserted'])}")
    if summary["reactivated"]:
        parts.append(
            f"reactivated {len(summary['reactivated'])}: {', '.join(summary['reactivated'])}"
        )
    if summary["deactivated"]:
        parts.append(
            f"deactivated {len(summary['deactivated'])}: {', '.join(summary['deactivated'])}"
        )
    if parts:
        print("\n[APPLIED] " + " | ".join(parts))
    else:
        print("\n[APPLIED] No auto-fixable drift. Extras/name-mismatches unchanged.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
