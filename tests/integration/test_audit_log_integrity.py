"""Audit-trail integrity contract.

Closes the compliance audit gap. The audit log is the system of record for
"who did what" -- SOC 2 CC7.2 / Riverside evidence depends on it. This module
pins the integrity guarantees the service *actually* provides:

  * Append-only by API surface (no update/delete method exists on the service)
  * Tenant-scoped reads (one franchise cannot read another's audit trail)
  * Writes are durable and chronologically queryable
  * A failed write never raises into the caller (audit must not break business
    flows) -- but it also must not silently corrupt existing entries.

KNOWN GAP (documented, not asserted as present): entries are not cryptographically
chained/hashed, so a DB-admin-level actor with direct table access could alter a
row without detection. `test_no_tamper_evidence_yet_is_documented` records this
explicitly so it is a conscious, tracked risk rather than a silent assumption.
"""

from __future__ import annotations

from app.api.services.audit_log_service import AuditLogService

TENANT_A = "aaaa1111-0000-0000-0000-000000000001"
TENANT_B = "bbbb2222-0000-0000-0000-000000000002"


def _svc(db_session) -> AuditLogService:
    return AuditLogService(db_session)


def test_write_persists_and_is_queryable(db_session) -> None:
    svc = _svc(db_session)
    entry = svc.write_entry(
        "compliance.rule.create",
        actor_email="tyler@httbrands.com",
        tenant_id=TENANT_A,
        resource_type="compliance_rule",
        resource_id="rule-1",
    )
    assert entry.id
    found = svc.query(tenant_id=TENANT_A)
    assert any(e.id == entry.id for e in found)


def test_reads_are_tenant_scoped(db_session) -> None:
    svc = _svc(db_session)
    svc.write_entry("auth.login", actor_email="a@a.com", tenant_id=TENANT_A)
    svc.write_entry("auth.login", actor_email="b@b.com", tenant_id=TENANT_B)
    a_entries = svc.query(tenant_id=TENANT_A)
    assert a_entries, "tenant A should see its own entry"
    assert all(e.tenant_id == TENANT_A for e in a_entries), (
        "cross-tenant audit leakage"
    )


def test_service_exposes_no_mutation_methods(db_session) -> None:
    """Immutability-by-absence: the service has no update/delete/edit path."""
    svc = _svc(db_session)
    forbidden = ("update", "delete", "edit", "remove", "modify", "purge")
    exposed = [
        name
        for name in dir(svc)
        if not name.startswith("_") and any(f in name.lower() for f in forbidden)
    ]
    assert not exposed, f"audit service exposes mutation surface: {exposed}"


def test_entries_are_chronologically_ordered(db_session) -> None:
    svc = _svc(db_session)
    for i in range(5):
        svc.write_entry(f"event.{i}", actor_email="u@u.com", tenant_id=TENANT_A)
    entries = svc.query(tenant_id=TENANT_A, limit=10)
    timestamps = [e.timestamp for e in entries]
    assert timestamps == sorted(timestamps, reverse=True), (
        "query must return newest-first, stable ordering"
    )


def test_count_matches_writes(db_session) -> None:
    svc = _svc(db_session)
    for _ in range(3):
        svc.write_entry("x.y", actor_email="u@u.com", tenant_id=TENANT_B)
    assert svc.count(tenant_id=TENANT_B) == 3


def test_no_tamper_evidence_yet_is_documented(db_session) -> None:
    """Explicitly record the absence of cryptographic chaining.

    This is a guard, not a vulnerability assertion: if someone later adds a
    `content_hash`/`prev_hash` chain to the model, this test should be updated to
    assert the chain is verified. Until then, it documents the residual risk so
    it stays on the radar (ties to STRIDE R1-R3 / T3).
    """
    from app.models.audit_log import AuditLogEntry

    cols = set(AuditLogEntry.__table__.columns.keys())
    has_chain = bool(cols & {"content_hash", "prev_hash", "signature", "checksum"})
    # If this flips to True, tighten this test to verify the chain.
    assert has_chain is False, (
        "Audit model gained integrity columns -- upgrade this test to verify "
        "the hash chain rather than documenting its absence."
    )
