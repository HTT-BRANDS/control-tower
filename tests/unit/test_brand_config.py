"""Unit tests for BrandConfig model."""

from datetime import datetime

import pytest

from app.models.brand_config import BrandConfig
from app.models.tenant import Tenant


class TestBrandConfigCreation:
    """Tests for BrandConfig model creation."""

    def test_brand_config_creation(self, db_session):
        """Test creating a brand config with all fields."""
        # Create tenant first
        tenant = Tenant(
            id="test-tenant-id",
            name="Test Tenant",
            tenant_id="test-tenant-uuid",
        )
        db_session.add(tenant)
        db_session.commit()

        # Create brand config
        brand_config = BrandConfig(
            tenant_id=tenant.id,
            brand_name="Test Brand",
            primary_color="#FF5733",
            secondary_color="#33FF57",
            accent_color="#3357FF",
        )
        db_session.add(brand_config)
        db_session.commit()

        # Verify creation
        assert brand_config.id is not None
        assert brand_config.tenant_id == tenant.id
        assert brand_config.brand_name == "Test Brand"
        assert brand_config.primary_color == "#FF5733"
        assert brand_config.secondary_color == "#33FF57"
        assert brand_config.accent_color == "#3357FF"
        assert brand_config.created_at is not None
        assert brand_config.updated_at is not None

    def test_brand_config_without_accent(self, db_session):
        """Test creating a brand config without optional accent color."""
        tenant = Tenant(
            id="test-tenant-id-2",
            name="Test Tenant 2",
            tenant_id="test-tenant-uuid-2",
        )
        db_session.add(tenant)
        db_session.commit()

        brand_config = BrandConfig(
            tenant_id=tenant.id,
            brand_name="Minimal Brand",
            primary_color="#000000",
            secondary_color="#FFFFFF",
            accent_color=None,
        )
        db_session.add(brand_config)
        db_session.commit()

        assert brand_config.accent_color is None
        assert brand_config.brand_name == "Minimal Brand"

    def test_brand_config_auto_uuid(self, db_session):
        """Test that brand config auto-generates UUID if not provided."""
        tenant = Tenant(
            id="test-tenant-id-3",
            name="Test Tenant 3",
            tenant_id="test-tenant-uuid-3",
        )
        db_session.add(tenant)
        db_session.commit()

        brand_config = BrandConfig(
            tenant_id=tenant.id,
            brand_name="Auto UUID Brand",
            primary_color="#123456",
            secondary_color="#654321",
        )
        db_session.add(brand_config)
        db_session.commit()

        # ID should be auto-generated UUID
        assert brand_config.id is not None
        assert len(brand_config.id) == 36  # UUID string length

    def test_brand_config_timestamps(self, db_session):
        """Test that created_at and updated_at are set automatically."""
        tenant = Tenant(
            id="test-tenant-id-4",
            name="Test Tenant 4",
            tenant_id="test-tenant-uuid-4",
        )
        db_session.add(tenant)
        db_session.commit()

        before_create = datetime.utcnow()
        brand_config = BrandConfig(
            tenant_id=tenant.id,
            brand_name="Timestamp Brand",
            primary_color="#111111",
            secondary_color="#222222",
        )
        db_session.add(brand_config)
        db_session.commit()
        after_create = datetime.utcnow()

        assert before_create <= brand_config.created_at <= after_create
        assert before_create <= brand_config.updated_at <= after_create


class TestBrandConfigToDict:
    """Tests for brand config to_dict method."""

    def test_brand_config_to_dict(self, db_session):
        """Test conversion to dictionary."""
        tenant = Tenant(
            id="test-tenant-dict",
            name="Dict Test Tenant",
            tenant_id="test-tenant-dict-uuid",
        )
        db_session.add(tenant)
        db_session.commit()

        brand_config = BrandConfig(
            tenant_id=tenant.id,
            brand_name="Dict Brand",
            primary_color="#AABBCC",
            secondary_color="#DDEEFF",
            accent_color="#112233",
        )
        db_session.add(brand_config)
        db_session.commit()

        result = brand_config.to_dict()

        assert result["id"] == brand_config.id
        assert result["tenant_id"] == tenant.id
        assert result["brand_name"] == "Dict Brand"
        assert result["primary_color"] == "#AABBCC"
        assert result["secondary_color"] == "#DDEEFF"
        assert result["accent_color"] == "#112233"
        assert "created_at" in result
        assert "updated_at" in result

    def test_brand_config_to_dict_isoformat(self, db_session):
        """Test that timestamps are converted to ISO format strings."""
        tenant = Tenant(
            id="test-tenant-iso",
            name="ISO Test Tenant",
            tenant_id="test-tenant-iso-uuid",
        )
        db_session.add(tenant)
        db_session.commit()

        brand_config = BrandConfig(
            tenant_id=tenant.id,
            brand_name="ISO Brand",
            primary_color="#000000",
            secondary_color="#FFFFFF",
        )
        db_session.add(brand_config)
        db_session.commit()

        result = brand_config.to_dict()

        # Timestamps should be ISO format strings
        assert isinstance(result["created_at"], str)
        assert isinstance(result["updated_at"], str)
        assert "T" in result["created_at"]  # ISO format contains 'T'

    def test_brand_config_to_dict_none_timestamp(self, db_session):
        """Test to_dict handles None timestamps gracefully (before db commit)."""
        tenant = Tenant(
            id="test-tenant-none",
            name="None Test Tenant",
            tenant_id="test-tenant-none-uuid",
        )
        db_session.add(tenant)
        db_session.commit()

        # Create brand config without adding to session (no auto-timestamps)
        brand_config = BrandConfig(
            tenant_id=tenant.id,
            brand_name="None Timestamp Brand",
            primary_color="#000000",
            secondary_color="#FFFFFF",
        )
        # Timestamps should be None before db insert
        brand_config.created_at = None
        brand_config.updated_at = None

        result = brand_config.to_dict()

        assert result["created_at"] is None
        assert result["updated_at"] is None


class TestTenantRelationship:
    """Tests for BrandConfig-Tenant relationship."""

    def test_tenant_relationship(self, db_session):
        """Test that brand config can access its tenant."""
        tenant = Tenant(
            id="test-tenant-rel",
            name="Relationship Tenant",
            tenant_id="test-tenant-rel-uuid",
        )
        db_session.add(tenant)
        db_session.commit()

        brand_config = BrandConfig(
            tenant_id=tenant.id,
            brand_name="Related Brand",
            primary_color="#111111",
            secondary_color="#222222",
        )
        db_session.add(brand_config)
        db_session.commit()

        # Refresh to load relationship
        db_session.refresh(brand_config)

        # Access tenant through relationship
        assert brand_config.tenant is not None
        assert brand_config.tenant.id == tenant.id
        assert brand_config.tenant.name == "Relationship Tenant"

    def test_unique_tenant_constraint(self, db_session):
        """Test that only one brand config per tenant is allowed."""
        tenant = Tenant(
            id="test-tenant-unique",
            name="Unique Tenant",
            tenant_id="test-tenant-unique-uuid",
        )
        db_session.add(tenant)
        db_session.commit()

        # First config should succeed
        config1 = BrandConfig(
            tenant_id=tenant.id,
            brand_name="First Brand",
            primary_color="#111111",
            secondary_color="#222222",
        )
        db_session.add(config1)
        db_session.commit()

        # Second config for same tenant should fail due to unique constraint
        from sqlalchemy.exc import IntegrityError

        config2 = BrandConfig(
            tenant_id=tenant.id,  # Same tenant
            brand_name="Second Brand",
            primary_color="#333333",
            secondary_color="#444444",
        )
        db_session.add(config2)

        with pytest.raises(IntegrityError):
            db_session.commit()

        db_session.rollback()

    def test_cascade_delete(self, db_session):
        """Test that brand config is deleted when tenant is deleted."""
        tenant = Tenant(
            id="test-tenant-cascade",
            name="Cascade Tenant",
            tenant_id="test-tenant-cascade-uuid",
        )
        db_session.add(tenant)
        db_session.commit()

        brand_config = BrandConfig(
            tenant_id=tenant.id,
            brand_name="Cascade Brand",
            primary_color="#111111",
            secondary_color="#222222",
        )
        db_session.add(brand_config)
        db_session.commit()

        config_id = brand_config.id

        # Delete tenant
        db_session.delete(tenant)
        db_session.commit()

        # Brand config should be gone
        deleted_config = db_session.query(BrandConfig).filter(BrandConfig.id == config_id).first()

        assert deleted_config is None


class TestBrandConfigRepr:
    """Tests for __repr__ method."""

    def test_brand_config_repr(self, db_session):
        """Test string representation of BrandConfig."""
        tenant = Tenant(
            id="test-tenant-repr",
            name="Repr Tenant",
            tenant_id="test-tenant-repr-uuid",
        )
        db_session.add(tenant)
        db_session.commit()

        brand_config = BrandConfig(
            tenant_id=tenant.id,
            brand_name="Repr Brand",
            primary_color="#000000",
            secondary_color="#FFFFFF",
        )
        db_session.add(brand_config)
        db_session.commit()

        repr_str = repr(brand_config)

        assert "BrandConfig" in repr_str
        assert "Repr Brand" in repr_str
        assert tenant.id in repr_str


class TestBrandConfigValidation:
    """Tests for model validation."""

    def test_brand_config_required_fields(self, db_session):
        """Test that required fields must be provided."""
        # Missing required fields should fail with IntegrityError
        from sqlalchemy.exc import IntegrityError

        with pytest.raises(IntegrityError):
            brand_config = BrandConfig(
                # Missing tenant_id
                brand_name="Incomplete",
                primary_color="#000000",
                secondary_color="#FFFFFF",
            )
            db_session.add(brand_config)
            db_session.commit()

        db_session.rollback()

    @pytest.mark.parametrize(
        "primary,secondary",
        [
            ("#FF5733", "#33FF57"),
            ("#000000", "#FFFFFF"),
            ("#ABC", "#DEF"),  # Short hex
        ],
    )
    def test_valid_hex_colors(self, db_session, primary, secondary):
        """Test that various hex color formats are accepted."""
        tenant = Tenant(
            id=f"test-tenant-hex-{primary}",
            name="Hex Test",
            tenant_id=f"test-hex-{primary}",
        )
        db_session.add(tenant)
        db_session.commit()

        brand_config = BrandConfig(
            tenant_id=tenant.id,
            brand_name="Hex Brand",
            primary_color=primary,
            secondary_color=secondary,
        )
        db_session.add(brand_config)
        db_session.commit()

        assert brand_config.primary_color == primary
        assert brand_config.secondary_color == secondary
