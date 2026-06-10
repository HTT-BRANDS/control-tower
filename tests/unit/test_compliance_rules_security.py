"""Security tests for the custom compliance rule engine (CM-002).

Closes the audit gap: the rule engine accepts tenant-authored JSON Schema, which
is an attacker-controlled input surface. These tests target the three risks that
matter for a multi-tenant governance product:

  * SSRF via remote ``$ref`` (ADR-0005 FF-3)
  * DoS via oversized schema payloads
  * IDOR / cross-tenant access (a tenant reaching another tenant's rules)

STRIDE coverage: I3 (cross-tenant disclosure), D (resource exhaustion),
plus the SSRF pivot risk to the Azure metadata endpoint.
"""

from __future__ import annotations

import pytest

from app.api.services.custom_rule_service import (
    MAX_RULE_SCHEMA_SIZE,
    CustomRuleService,
)

TENANT_A = "11111111-1111-1111-1111-111111111111"
TENANT_B = "22222222-2222-2222-2222-222222222222"

VALID_SCHEMA = {
    "type": "object",
    "properties": {"tag": {"type": "string"}},
    "required": ["tag"],
}


@pytest.fixture
def svc(db_session) -> CustomRuleService:
    return CustomRuleService(db_session)


def _make(svc, tenant_id=TENANT_A, schema=None, **kw):
    return svc.create(
        tenant_id=tenant_id,
        name=kw.get("name", "Tag required"),
        description=kw.get("description"),
        category=kw.get("category", "resource_property"),
        severity=kw.get("severity", "medium"),
        rule_schema=schema if schema is not None else VALID_SCHEMA,
        created_by="tester@example.com",
    )


def test_valid_rule_is_created(svc) -> None:
    rule, errors = _make(svc)
    assert errors == []
    assert rule is not None
    assert rule.tenant_id == TENANT_A


def test_remote_http_ref_is_blocked(svc) -> None:
    """SSRF: a remote $ref must be refused, not fetched/stored."""
    malicious = {"$ref": "http://169.254.169.254/metadata/instance"}
    rule, errors = _make(svc, schema=malicious)
    assert rule is None
    assert any("ref" in e.lower() for e in errors)


def test_remote_https_ref_is_blocked(svc) -> None:
    malicious = {"properties": {"x": {"$ref": "https://evil.example.com/s.json"}}}
    rule, errors = _make(svc, schema=malicious)
    assert rule is None
    assert errors


def test_local_ref_is_permitted(svc) -> None:
    """Intra-document refs (#/...) are legitimate JSON Schema and allowed."""
    ok = {
        "type": "object",
        "properties": {"a": {"$ref": "#/$defs/str"}},
        "$defs": {"str": {"type": "string"}},
    }
    rule, errors = _make(svc, schema=ok)
    assert errors == [], errors
    assert rule is not None


def test_oversized_schema_is_rejected(svc) -> None:
    """DoS guard: schemas above the 64KB cap are refused."""
    huge = {"type": "object", "blob": "A" * (MAX_RULE_SCHEMA_SIZE + 100)}
    rule, errors = _make(svc, schema=huge)
    assert rule is None
    assert any("size" in e.lower() for e in errors)


def test_invalid_category_rejected(svc) -> None:
    rule, errors = _make(svc, category="../../etc/passwd")
    assert rule is None
    assert errors


def test_invalid_severity_rejected(svc) -> None:
    rule, errors = _make(svc, severity="catastrophic")
    assert rule is None
    assert errors


def test_tenant_cannot_read_another_tenants_rule(svc) -> None:
    """IDOR: a rule created by tenant A is invisible to tenant B."""
    rule, errors = _make(svc, tenant_id=TENANT_A)
    assert errors == []
    # Tenant B asks for A's rule id -> must get nothing.
    leaked = svc.get(rule.id, tenant_id=TENANT_B)
    assert leaked is None
    # And A still sees it.
    assert svc.get(rule.id, tenant_id=TENANT_A) is not None


def test_tenant_cannot_delete_another_tenants_rule(svc) -> None:
    rule, _ = _make(svc, tenant_id=TENANT_A)
    assert svc.delete(rule.id, tenant_id=TENANT_B) is False
    # Still present for the real owner.
    assert svc.get(rule.id, tenant_id=TENANT_A) is not None


def test_tenant_cannot_update_another_tenants_rule(svc) -> None:
    rule, _ = _make(svc, tenant_id=TENANT_A)
    updated, errors = svc.update(rule.id, tenant_id=TENANT_B, name="hijacked")
    assert updated is None
    assert errors


def test_list_is_scoped_to_tenant(svc) -> None:
    _make(svc, tenant_id=TENANT_A, name="A1")
    _make(svc, tenant_id=TENANT_A, name="A2")
    _make(svc, tenant_id=TENANT_B, name="B1")
    a_rules = svc.list_rules(tenant_id=TENANT_A)
    b_rules = svc.list_rules(tenant_id=TENANT_B)
    assert all(r.tenant_id == TENANT_A for r in a_rules)
    assert all(r.tenant_id == TENANT_B for r in b_rules)
    assert len(a_rules) == 2
    assert len(b_rules) == 1
