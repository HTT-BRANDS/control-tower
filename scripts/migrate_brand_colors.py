#!/usr/bin/env python3
"""Migration script to populate initial brand configurations for Riverside tenants.

This script inserts brand color configurations for the four Riverside brands:
- HTT: primary=#500711, secondary=#d1bdbf, accent=#ffc957
- Frenchies: primary=#052b48, secondary=#faaca8
- Bishops: primary=#EB631B, secondary=#CE9F7C
- Lash Lounge: primary=#513550, secondary=#D3BCC5

Usage:
    python scripts/migrate_brand_colors.py

    Or from project root:
    uv run python scripts/migrate_brand_colors.py
"""

import logging
import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy.orm import Session

from app.core.database import SessionLocal, init_db
from app.models.brand_config import BrandConfig
from app.models.tenant import Tenant

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Tenant matching patterns for brand configuration lookup
TENANT_MATCH_PATTERNS = {
    "HTT": ["htt", "head"],
    "Frenchies": ["french"],
    "Bishops": ["bishop"],
    "Lash Lounge": ["lash"],
}

# Riverside brand configurations
RIVERSIDE_BRAND_CONFIGS = [
    {
        "brand_name": "HTT",
        "primary_color": "#500711",
        "secondary_color": "#d1bdbf",
        "accent_color": "#ffc957",
    },
    {
        "brand_name": "Frenchies",
        "primary_color": "#052b48",
        "secondary_color": "#faaca8",
        "accent_color": None,
    },
    {
        "brand_name": "Bishops",
        "primary_color": "#EB631B",
        "secondary_color": "#CE9F7C",
        "accent_color": None,
    },
    {
        "brand_name": "Lash Lounge",
        "primary_color": "#513550",
        "secondary_color": "#D3BCC5",
        "accent_color": None,
    },
]


def get_or_create_brand_config(
    db: Session,
    tenant_id: str,
    config: dict,
) -> BrandConfig:
    """Get existing brand config or create new one.

    Args:
        db: Database session
        tenant_id: Tenant ID to associate with brand config
        config: Brand configuration dictionary

    Returns:
        BrandConfig instance (existing or newly created)
    """
    existing = db.query(BrandConfig).filter(BrandConfig.tenant_id == tenant_id).first()

    if existing:
        logger.info(f"Brand config already exists for tenant: {tenant_id}")
        # Update with new values
        existing.brand_name = config["brand_name"]
        existing.primary_color = config["primary_color"]
        existing.secondary_color = config["secondary_color"]
        existing.accent_color = config.get("accent_color")
        db.commit()
        logger.info(f"Updated brand config for: {config['brand_name']}")
        return existing

    brand_config = BrandConfig(
        tenant_id=tenant_id,
        brand_name=config["brand_name"],
        primary_color=config["primary_color"],
        secondary_color=config["secondary_color"],
        accent_color=config.get("accent_color"),
    )
    db.add(brand_config)
    db.commit()
    db.refresh(brand_config)

    return brand_config


def migrate_brand_colors(db: Session | None = None) -> dict:
    """Migrate brand color configurations for Riverside tenants.

    Attempts to match brand configurations to tenants by name.
    If no matching tenant is found, the brand config is skipped.

    Args:
        db: Optional database session. If not provided, a new one is created.

    Returns:
        Dictionary with migration results summary
    """
    should_close = False
    if db is None:
        db = SessionLocal()
        should_close = True

    results = {
        "created": [],
        "updated": [],
        "skipped": [],
        "errors": [],
    }

    try:
        # Get all active tenants
        tenants = db.query(Tenant).filter(Tenant.is_active.is_(True)).all()
        tenant_map = {t.name.lower(): t for t in tenants}

        logger.info(f"Found {len(tenants)} active tenants")

        for config in RIVERSIDE_BRAND_CONFIGS:
            brand_name = config["brand_name"]
            brand_lower = brand_name.lower()

            # Try to find matching tenant by name
            tenant = None

            # Exact match
            if brand_lower in tenant_map:
                tenant = tenant_map[brand_lower]
            else:
                # Use matching patterns from constant
                patterns = TENANT_MATCH_PATTERNS.get(brand_name, [])
                for pattern in patterns:
                    for name, t in tenant_map.items():
                        if pattern in name:
                            tenant = t
                            break
                    if tenant:
                        break

            if not tenant:
                logger.warning(f"No matching tenant found for brand: {brand_name}. Skipping.")
                results["skipped"].append(
                    {
                        "brand": brand_name,
                        "reason": "No matching tenant found",
                    }
                )
                continue

            try:
                # Check if config exists
                existing = db.query(BrandConfig).filter(BrandConfig.tenant_id == tenant.id).first()

                if existing:
                    # Update existing
                    existing.brand_name = config["brand_name"]
                    existing.primary_color = config["primary_color"]
                    existing.secondary_color = config["secondary_color"]
                    existing.accent_color = config.get("accent_color")
                    db.commit()
                    logger.info(f"Updated brand config for: {brand_name} (tenant: {tenant.name})")
                    results["updated"].append(
                        {
                            "brand": brand_name,
                            "tenant_id": tenant.id,
                            "tenant_name": tenant.name,
                        }
                    )
                else:
                    # Create new
                    brand_config = BrandConfig(
                        tenant_id=tenant.id,
                        brand_name=config["brand_name"],
                        primary_color=config["primary_color"],
                        secondary_color=config["secondary_color"],
                        accent_color=config.get("accent_color"),
                    )
                    db.add(brand_config)
                    db.commit()
                    db.refresh(brand_config)
                    logger.info(f"Created brand config for: {brand_name} (tenant: {tenant.name})")
                    results["created"].append(
                        {
                            "brand": brand_name,
                            "tenant_id": tenant.id,
                            "tenant_name": tenant.name,
                            "config_id": brand_config.id,
                        }
                    )

            except Exception as e:
                db.rollback()
                logger.error(f"Error processing {brand_name}: {e}")
                results["errors"].append(
                    {
                        "brand": brand_name,
                        "error": str(e),
                    }
                )

        return results

    except Exception as e:
        logger.error(f"Migration failed: {e}")
        db.rollback()
        raise
    finally:
        if should_close:
            db.close()


def main() -> int:
    """Main entry point for the migration script.

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    logger.info("Starting brand color migration...")

    try:
        # Initialize database (creates tables if they don't exist)
        init_db()
        logger.info("Database initialized")

        # Run migration
        results = migrate_brand_colors()

        # Print summary
        logger.info("=" * 50)
        logger.info("Migration Summary:")
        logger.info(f"  Created: {len(results['created'])}")
        logger.info(f"  Updated: {len(results['updated'])}")
        logger.info(f"  Skipped: {len(results['skipped'])}")
        logger.info(f"  Errors:  {len(results['errors'])}")
        logger.info("=" * 50)

        if results["created"]:
            logger.info("Created configurations:")
            for item in results["created"]:
                logger.info(f"  - {item['brand']} -> {item['tenant_name']}")

        if results["updated"]:
            logger.info("Updated configurations:")
            for item in results["updated"]:
                logger.info(f"  - {item['brand']} -> {item['tenant_name']}")

        if results["errors"]:
            logger.error("Errors occurred:")
            for item in results["errors"]:
                logger.error(f"  - {item['brand']}: {item['error']}")
            return 1

        logger.info("Migration completed successfully!")
        return 0

    except Exception as e:
        logger.error(f"Migration failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
