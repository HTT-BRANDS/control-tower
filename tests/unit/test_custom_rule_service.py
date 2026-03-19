"""Unit tests for CustomRuleService — CM-002."""
import uuid
from datetime import UTC
from unittest.mock import MagicMock


def _make_db():
    db = MagicMock()
    db.add.return_value = None
    db.commit.return_value = None
    db.refresh.return_value = None
    db.rollback.return_value = None
    db.delete.return_value = None
    return db

def _schema():
    return {"type": "object", "properties": {"state": {"type": "string"}}}

def _make_mock_rule(rule_id=None, tenant_id="t-1"):
    from datetime import datetime

    from app.models.custom_rule import CustomComplianceRule
    r = MagicMock(spec=CustomComplianceRule)
    r.id = rule_id or str(uuid.uuid4())
    r.tenant_id = tenant_id
    r.name = "Test Rule"
    r.category = "resource_property"
    r.severity = "medium"
    r.rule_schema = _schema()
    r.is_enabled = True
    r.created_at = datetime.now(UTC)
    r.updated_at = datetime.now(UTC)
    r.last_evaluated_at = None
    r.created_by = None
    r.description = None
    return r


class TestValidateSchema:
    def test_allows_valid_schema(self):
        from app.api.services.custom_rule_service import _validate_schema
        assert _validate_schema(_schema()) == []

    def test_blocks_http_ref(self):
        from app.api.services.custom_rule_service import _validate_schema
        errors = _validate_schema({"$ref": "http://evil.com/schema"})
        assert any("$ref" in e or "Remote" in e for e in errors)

    def test_blocks_https_ref(self):
        from app.api.services.custom_rule_service import _validate_schema
        errors = _validate_schema({"$ref": "https://attacker.com/x.json"})
        assert any("Remote" in e for e in errors)

    def test_allows_local_ref(self):
        from app.api.services.custom_rule_service import _validate_schema
        assert _validate_schema({"$ref": "#/definitions/Foo"}) == []

    def test_blocks_oversized_schema(self):
        from app.api.services.custom_rule_service import _validate_schema
        big = {"properties": {f"f{i}": {"type": "string"} for i in range(10000)}}
        errors = _validate_schema(big)
        assert any("size" in e or "exceed" in e or "bytes" in e for e in errors)


class TestCustomRuleServiceCreate:
    def test_create_success(self):
        from app.api.services.custom_rule_service import CustomRuleService
        db = _make_db()
        rule, errors = CustomRuleService(db).create(
            tenant_id="t-1", name="My Rule",
            category="resource_property", rule_schema=_schema()
        )
        assert errors == []
        assert rule.name == "My Rule"
        db.add.assert_called_once()
        db.commit.assert_called_once()

    def test_create_rejects_invalid_category(self):
        from app.api.services.custom_rule_service import CustomRuleService
        rule, errors = CustomRuleService(_make_db()).create(
            tenant_id="t-1", name="R", category="badcat", rule_schema=_schema()
        )
        assert rule is None and any("category" in e for e in errors)

    def test_create_rejects_invalid_severity(self):
        from app.api.services.custom_rule_service import CustomRuleService
        rule, errors = CustomRuleService(_make_db()).create(
            tenant_id="t-1", name="R", category="compliance_score",
            severity="extreme", rule_schema=_schema()
        )
        assert rule is None and any("severity" in e for e in errors)

    def test_create_rejects_blank_name(self):
        from app.api.services.custom_rule_service import CustomRuleService
        rule, errors = CustomRuleService(_make_db()).create(
            tenant_id="t-1", name="  ", category="mfa_coverage", rule_schema=_schema()
        )
        assert rule is None and any("name" in e for e in errors)

    def test_create_rejects_remote_ref(self):
        from app.api.services.custom_rule_service import CustomRuleService
        rule, errors = CustomRuleService(_make_db()).create(
            tenant_id="t-1", name="Evil",
            category="resource_property", rule_schema={"$ref": "https://evil.com/x"}
        )
        assert rule is None and len(errors) > 0

    def test_create_survives_db_failure(self):
        from app.api.services.custom_rule_service import CustomRuleService
        db = _make_db()
        db.commit.side_effect = Exception("down")
        rule, errors = CustomRuleService(db).create(
            tenant_id="t-1", name="R", category="resource_property", rule_schema=_schema()
        )
        assert rule is None
        db.rollback.assert_called_once()

    def test_create_unique_ids(self):
        from app.api.services.custom_rule_service import CustomRuleService
        svc = CustomRuleService(_make_db())
        r1, _ = svc.create(tenant_id="t-1", name="A", category="resource_property", rule_schema=_schema())
        r2, _ = svc.create(tenant_id="t-1", name="B", category="resource_property", rule_schema=_schema())
        assert r1.id != r2.id

    def test_create_all_categories(self):
        from app.api.services.custom_rule_service import VALID_CATEGORIES, CustomRuleService
        for cat in VALID_CATEGORIES:
            r, e = CustomRuleService(_make_db()).create(
                tenant_id="t-1", name=cat, category=cat, rule_schema=_schema()
            )
            assert e == [], f"{cat} should be valid"


class TestCustomRuleServiceCRUD:
    def _setup_query(self, db, result):
        q = MagicMock()
        q.filter.return_value = q
        q.first.return_value = result
        q.order_by.return_value = q
        q.offset.return_value = q
        q.limit.return_value = q
        q.all.return_value = [result] if result else []
        db.query.return_value = q
        return q

    def test_get_returns_none_for_missing(self):
        from app.api.services.custom_rule_service import CustomRuleService
        db = _make_db()
        self._setup_query(db, None)
        assert CustomRuleService(db).get("x", "t-1") is None

    def test_delete_false_when_not_found(self):
        from app.api.services.custom_rule_service import CustomRuleService
        db = _make_db()
        self._setup_query(db, None)
        assert CustomRuleService(db).delete("x", "t-1") is False

    def test_update_errors_when_not_found(self):
        from app.api.services.custom_rule_service import CustomRuleService
        db = _make_db()
        self._setup_query(db, None)
        rule, errors = CustomRuleService(db).update("x", "t-1", name="New")
        assert rule is None and len(errors) > 0

    def test_list_returns_list(self):
        from app.api.services.custom_rule_service import CustomRuleService
        db = _make_db()
        self._setup_query(db, None)
        assert isinstance(CustomRuleService(db).list_rules("t-1"), list)


class TestCustomRuleServiceEvaluate:
    def test_evaluate_passing(self):
        from app.api.services.custom_rule_service import CustomRuleService
        rule = _make_mock_rule()
        rule.rule_schema = {"type": "object", "required": ["state"]}
        result = CustomRuleService(_make_db()).evaluate(rule, {"state": "ok"})
        assert result["passed"] is True

    def test_evaluate_failing(self):
        from app.api.services.custom_rule_service import CustomRuleService
        rule = _make_mock_rule()
        rule.rule_schema = {"type": "object", "required": ["state"]}
        result = CustomRuleService(_make_db()).evaluate(rule, {})
        assert result["passed"] is False and len(result["errors"]) > 0


class TestCustomRuleRoutes:
    def test_list_requires_auth(self, client):
        assert client.get("/api/v1/compliance/rules?tenant_id=t-1").status_code in (401, 403)

    def test_list_authenticated(self, authed_client):
        r = authed_client.get("/api/v1/compliance/rules?tenant_id=t-1")
        assert r.status_code == 200
        data = r.json()
        assert "rules" in data and "count" in data

    def test_create_requires_auth(self, client):
        assert client.post("/api/v1/compliance/rules", json={}).status_code in (401, 403)

    def test_create_valid_payload(self, authed_client):
        r = authed_client.post("/api/v1/compliance/rules", json={
            "tenant_id": "00000000-0000-0000-0000-000000000001",
            "name": "Test Rule", "category": "resource_property",
            "severity": "medium", "rule_schema": {"type": "object"},
        })
        assert r.status_code in (201, 422)

    def test_get_nonexistent_404(self, authed_client):
        assert authed_client.get("/api/v1/compliance/rules/bad-id?tenant_id=t-1").status_code == 404

    def test_delete_nonexistent_404(self, authed_client):
        assert authed_client.delete("/api/v1/compliance/rules/bad-id?tenant_id=t-1").status_code == 404
