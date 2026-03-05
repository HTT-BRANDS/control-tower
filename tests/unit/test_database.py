"""Simple unit tests for app/core/database.py.

Tests core database functionality with in-memory SQLite:
1. Base has metadata
2. get_db yields a session
3. Models have __tablename__
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.models.tenant import Tenant
from app.models.resource import Resource
from app.models.cost import CostSnapshot


def test_base_has_metadata():
    """Test that Base has metadata attribute."""
    assert hasattr(Base, "metadata")
    assert Base.metadata is not None
    assert hasattr(Base.metadata, "create_all")


def test_get_db_yields_session():
    """Test that get_db yields a valid Session instance."""
    gen = get_db()
    session = next(gen)
    
    assert isinstance(session, Session)
    assert session is not None
    
    # Clean up
    try:
        next(gen)
    except StopIteration:
        pass


def test_tenant_model_has_tablename():
    """Test that Tenant model has __tablename__."""
    assert hasattr(Tenant, "__tablename__")
    assert Tenant.__tablename__ == "tenants"


def test_resource_model_has_tablename():
    """Test that Resource model has __tablename__."""
    assert hasattr(Resource, "__tablename__")
    assert Resource.__tablename__ == "resources"


def test_cost_model_has_tablename():
    """Test that CostSnapshot model has __tablename__."""
    assert hasattr(CostSnapshot, "__tablename__")
    assert CostSnapshot.__tablename__ == "cost_snapshots"
