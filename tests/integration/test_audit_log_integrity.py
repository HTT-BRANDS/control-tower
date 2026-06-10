"""Audit-trail integrity contract.

Closes the compliance audit gap. The audit log is the system of record for
"who did what" -- SOC 2 CC7.2 / Riverside evidence depends on it. This module
pins the integrity guarantees the service *actually* provides:

  * Append-only by API surface (no update/delete method exists on the service)
  * Tenant-scoped reads (one franchise cannot read another's audit trail)
  * Writes are durable and chronologically queryable
  * A failed write never raises into the caller (audit must not break business
    flows) -- but it also must not silently corrupt existing entries.

INTEGRITY GUARANTEE (Finding 3 closed): entries carry a content_hash (SHA-256
of their payload) and a prev_hash pointer forming a linked chain. A DB-admin-
level mutation changes the content_hash, breaking the chain and making tampering
detectable via AuditLogService.verify_chain(). See migration 014.
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
    assert all(e.tenant_id == TENANT_A for e in a_entries), "cross-tenant audit leakage"


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


def test_hash_chain_is_present_and_verified(db_session) -> None:
    """Hash-chain columns exist AND verify_chain() detects tampering.

    Supersedes the old 'test_no_tamper_evidence_yet_is_documented' placeholder
    that recorded the absence of a chain as a conscious risk. Finding 3 from
    docs/testing/TESTING_SUITE_AUDIT_2026-06.md is now closed: content_hash +
    prev_hash are added by migration 014 and computed by AuditLogService.
    """
    from app.models.audit_log import AuditLogEntry

    # 1. Schema: both columns must exist.
    cols = set(AuditLogEntry.__table__.columns.keys())
    assert "content_hash" in cols, "content_hash column missing from AuditLogEntry"
    assert "prev_hash" in cols, "prev_hash column missing from AuditLogEntry"

    # 2. New writes carry hashes.
    svc = _svc(db_session)
    e1 = svc.write_entry("audit.chain.test.1", actor_email="a@a.com", tenant_id=TENANT_A)
    e2 = svc.write_entry("audit.chain.test.2", actor_email="a@a.com", tenant_id=TENANT_A)
    e3 = svc.write_entry("audit.chain.test.3", actor_email="a@a.com", tenant_id=TENANT_A)

    assert e1.content_hash, "genesis row must have a content_hash"
    assert e1.prev_hash is None, "genesis row prev_hash must be None"
    assert e2.prev_hash == e1.content_hash, "e2.prev_hash must point to e1"
    assert e3.prev_hash == e2.content_hash, "e3.prev_hash must point to e2"

    # 3. verify_chain() passes on an intact chain.
    ok, reason = svc.verify_chain()
    assert ok, f"chain should be intact but got: {reason}"

    # 4. verify_chain() detects a field mutation.
    # Directly mutate a row's payload column in the DB, bypassing the service.
    db_session.query(AuditLogEntry).filter(AuditLogEntry.id == e2.id).update(
        {"action": "TAMPERED"}, synchronize_session="fetch"
    )
    db_session.commit()

    ok_after, reason_after = svc.verify_chain()
    assert not ok_after, "mutated row should break chain verification"
    assert e2.id in reason_after or "content_hash mismatch" in reason_after, (
        f"failure reason should reference the tampered row: {reason_after}"
    )
