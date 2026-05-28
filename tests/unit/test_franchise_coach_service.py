"""Unit tests for the franchise-coach service.

Verifies:
- Severity classification thresholds
- Short-code extraction from tenant names
- Brand-voice messages contain the right vocabulary
- DCE Entra-P1 special case is handled
- Overall view aggregation across multiple brands
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from app.api.services.franchise_coach_service import (
    _compliance_severity,
    _extract_short_code,
    _identity_severity,
    _roll_up_severity,
    build_franchise_coach_view,
)


# ============================================================================
# Pure-function tests (no DB)
# ============================================================================


class TestShortCodeExtraction:
    @pytest.mark.parametrize(
        "name,expected",
        [
            ("Head-To-Toe (HTT)", "HTT"),
            ("Bishops (BCC)", "BCC"),
            ("Frenchies Modern Nail Care (FN)", "FN"),
            ("The Lash Lounge (TLL)", "TLL"),
            ("Delta Crown Extensions (DCE)", "DCE"),
        ],
    )
    def test_extracts_paren_short_code(self, name: str, expected: str):
        assert _extract_short_code(name) == expected

    def test_falls_back_to_caps_when_no_parens(self):
        assert _extract_short_code("My Custom Brand") == "MCB"

    def test_empty_string_safe(self):
        assert _extract_short_code("") == ""


class TestIdentitySeverity:
    def test_healthy_when_high_mfa_and_no_stale(self):
        assert _identity_severity(97.0, 0, has_premium_p1=True) == "healthy"

    def test_critical_when_low_mfa(self):
        assert _identity_severity(50.0, 0, has_premium_p1=True) == "critical"

    def test_critical_when_many_stale(self):
        assert _identity_severity(96.0, 10, has_premium_p1=True) == "critical"

    def test_attention_when_missing_p1(self):
        # Even perfect numbers can't be trusted without P1 visibility.
        assert _identity_severity(100.0, 0, has_premium_p1=False) == "attention"

    def test_attention_in_middle_band(self):
        assert _identity_severity(88.0, 3, has_premium_p1=True) == "attention"


class TestComplianceSeverity:
    def test_healthy_when_high_percent(self):
        assert _compliance_severity(95.0, 80.0) == "healthy"

    def test_critical_when_low_percent(self):
        assert _compliance_severity(50.0, None) == "critical"

    def test_critical_when_low_secure_score(self):
        # Even with decent compliance %, very low secure score is critical
        assert _compliance_severity(85.0, 30.0) == "critical"

    def test_attention_in_middle(self):
        assert _compliance_severity(80.0, 60.0) == "attention"


class TestRollUp:
    def test_critical_beats_attention(self):
        assert _roll_up_severity(["healthy", "critical", "attention"]) == "critical"

    def test_attention_beats_healthy(self):
        assert _roll_up_severity(["healthy", "attention", "healthy"]) == "attention"

    def test_all_healthy(self):
        assert _roll_up_severity(["healthy", "healthy"]) == "healthy"


# ============================================================================
# Integration test with mocked DB
# ============================================================================


class _StubTenant:
    def __init__(self, id_: str, name: str, is_active: bool = True):
        self.id = id_
        self.name = name
        self.is_active = is_active


class _StubIdentitySnapshot:
    def __init__(self, **kw):
        self.id = 1
        self.mfa_enabled_users = kw.get("mfa_enabled_users", 95)
        self.mfa_disabled_users = kw.get("mfa_disabled_users", 5)
        self.privileged_users = kw.get("privileged_users", 3)
        self.stale_accounts_30d = kw.get("stale_accounts_30d", 0)
        self.stale_accounts_90d = kw.get("stale_accounts_90d", 0)
        self.synced_at = kw.get("synced_at", datetime.now(UTC))


class _StubComplianceSnapshot:
    def __init__(self, **kw):
        self.id = 1
        self.overall_compliance_percent = kw.get("overall_compliance_percent", 92.0)
        self.secure_score = kw.get("secure_score", 75.0)
        self.non_compliant_resources = kw.get("non_compliant_resources", 4)
        self.compliant_resources = kw.get("compliant_resources", 50)
        self.exempt_resources = kw.get("exempt_resources", 0)
        self.synced_at = kw.get("synced_at", datetime.now(UTC))


class _StubFreshRow:
    def __init__(self):
        self.synced_at = datetime.now(UTC)


def _make_session(tenants, identity_map, compliance_map, fresh_for_all=True):
    """Build a MagicMock session that routes queries by model type.

    Each model gets its OWN counter so HTT/DCE identity and HTT/DCE compliance
    are served in the order tenants are iterated.
    """
    from app.models.compliance import ComplianceSnapshot, PolicyState
    from app.models.cost import CostSnapshot
    from app.models.identity import IdentitySnapshot
    from app.models.resource import Resource
    from app.models.tenant import Tenant

    session = MagicMock()
    counters: dict[str, int] = {"identity": 0, "compliance": 0}

    def _next(kind: str, by_tenant: dict):
        # Each tenant triggers TWO lookups per model: one in the insight
        # builder (_build_*_insight) and one in _build_sync_freshness.
        # So advance the tenant index every other call.
        i = counters[kind] // 2
        counters[kind] += 1
        if i < len(tenants):
            return by_tenant.get(tenants[i].id)
        return None

    def query_side_effect(model):
        q = MagicMock()
        if model is Tenant:
            q.filter.return_value.all.return_value = tenants
            return q
        if model is IdentitySnapshot:
            q.filter.return_value.order_by.return_value.first.side_effect = lambda: _next(
                "identity", identity_map
            )
            return q
        if model is ComplianceSnapshot:
            q.filter.return_value.order_by.return_value.first.side_effect = lambda: _next(
                "compliance", compliance_map
            )
            return q
        if model is PolicyState:
            policy_q = MagicMock()
            policy_q.filter.return_value.distinct.return_value.limit.return_value.all.return_value = [
                ("Security",),
                ("Network",),
            ]
            return policy_q
        if model is CostSnapshot or model is Resource:
            inner = _StubFreshRow() if fresh_for_all else None
            q.filter.return_value.order_by.return_value.first.return_value = inner
            return q
        # Fallback: empty
        q.filter.return_value.order_by.return_value.first.return_value = None
        q.filter.return_value.all.return_value = []
        return q

    session.query.side_effect = query_side_effect
    return session


def test_view_with_one_healthy_and_one_critical_brand():
    """End-to-end: two brands, mixed health, verify aggregation."""
    t_htt = _StubTenant("htt-id", "Head-To-Toe (HTT)")
    t_dce = _StubTenant("dce-id", "Delta Crown Extensions (DCE)")
    identity_map = {
        "htt-id": _StubIdentitySnapshot(
            mfa_enabled_users=98, mfa_disabled_users=2, stale_accounts_30d=0
        ),
        "dce-id": _StubIdentitySnapshot(
            mfa_enabled_users=40, mfa_disabled_users=60, stale_accounts_30d=10
        ),
    }
    compliance_map = {
        "htt-id": _StubComplianceSnapshot(overall_compliance_percent=95.0, secure_score=80.0),
        "dce-id": _StubComplianceSnapshot(overall_compliance_percent=55.0, secure_score=35.0),
    }
    session = _make_session([t_htt, t_dce], identity_map, compliance_map)

    view = build_franchise_coach_view(session)

    assert view.brand_count == 2
    assert len(view.cards) == 2

    # DCE special: has_premium_p1 is False → identity stays at 'attention' regardless
    dce_card = next(c for c in view.cards if c.brand_short_code == "DCE")
    assert dce_card.identity is not None
    assert dce_card.identity.has_premium_p1 is False
    # Compliance for DCE is critical
    assert dce_card.compliance is not None
    assert dce_card.compliance.severity == "critical"
    # Overall: critical wins
    assert dce_card.overall_severity == "critical"

    htt_card = next(c for c in view.cards if c.brand_short_code == "HTT")
    assert htt_card.overall_severity == "healthy"


class TestBrandVoiceLanguage:
    """The coaching messages must follow the HTT brand voice charter."""

    @pytest.fixture
    def view(self):
        t = _StubTenant("htt-id", "Head-To-Toe (HTT)")
        identity_map = {
            "htt-id": _StubIdentitySnapshot(
                mfa_enabled_users=30, mfa_disabled_users=70, stale_accounts_30d=12
            )
        }
        compliance_map = {
            "htt-id": _StubComplianceSnapshot(overall_compliance_percent=40.0, secure_score=30.0)
        }
        session = _make_session([t], identity_map, compliance_map)
        return build_franchise_coach_view(session)

    def test_identity_message_uses_approved_vocabulary(self, view):
        msg = view.cards[0].identity.coaching_message
        # 'protect', 'coach' are approved
        approved = ["protect", "coach"]
        assert any(word in msg.lower() for word in approved)

    def test_compliance_message_does_not_use_banned_buzzwords(self, view):
        msg = view.cards[0].compliance.coaching_message.lower()
        banned = ["disruptive", "game-changing", "synergies", "as an ai"]
        for bad in banned:
            assert bad not in msg

    def test_headline_does_not_use_banned_buzzwords(self, view):
        headline = view.cards[0].headline.lower()
        banned = ["disruptive", "synergies", "paradigm shift"]
        for bad in banned:
            assert bad not in headline
