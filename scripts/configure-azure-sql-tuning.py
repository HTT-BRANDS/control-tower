#!/usr/bin/env python3
"""Azure SQL Automated Tuning Configuration Script.

Configures Azure SQL automatic tuning features:
- Automatic index management (CREATE/DROP INDEX)
- Automatic plan correction
- Query Store settings
- Intelligent Insights

Usage:
    python scripts/configure-azure-sql-tuning.py --enable-all
    python scripts/configure-azure-sql-tuning.py --enable-index-create --enable-index-drop
    python scripts/configure-azure-sql-tuning.py --status
    python scripts/configure-azure-sql-tuning.py --recommendations

Environment:
    Requires DATABASE_URL environment variable set to Azure SQL connection string.
"""

import argparse
import json
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import SessionLocal

logging.basicConfig(
    level=logging.INFO,
    format="%(asmosctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@dataclass
class TuningOptions:
    """Azure SQL Automatic Tuning options."""

    force_last_good_plan: str = "DEFAULT"  # ON, OFF, or DEFAULT
    create_index: str = "DEFAULT"
    drop_index: str = "DEFAULT"
    maintain_index: str = "DEFAULT"


class AzureSQLTuningManager:
    """Manages Azure SQL Automatic Tuning configuration."""

    # Tuning option descriptions
    OPTION_DESCRIPTIONS = {
        "force_last_good_plan": """
            Automatic Plan Correction:
            - Detects performance regressions from plan changes
            - Reverts to last known good plan when regression detected
            - Prevents parameter sniffing issues
        """,
        "create_index": """
            Automatic Index Creation:
            - Analyzes query workload history
            - Recommends and creates indexes for performance
            - Validates index improvement before keeping
        """,
        "drop_index": """
            Automatic Index Deletion:
            - Identifies redundant and unused indexes
            - Drops indexes not used for 90+ days
            - Considers index maintenance cost vs benefit
        """,
        "maintain_index": """
            Automatic Index Maintenance:
            - Rebuilds fragmented indexes automatically
            - Updates statistics as needed
            - Optimizes index fill factor
        """,
    }

    def __init__(self, db: Session):
        self.db = db
        self._is_azure_sql: bool | None = None

    def is_azure_sql(self) -> bool:
        """Check if connected to Azure SQL (not SQLite)."""
        if self._is_azure_sql is not None:
            return self._is_azure_sql

        settings = get_settings()
        self._is_azure_sql = (
            "database.windows.net" in settings.database_url or "mssql" in settings.database_url
        ) and not settings.database_url.startswith("sqlite")
        return self._is_azure_sql

    def get_current_tuning_options(self) -> dict[str, str]:
        """Get current automatic tuning options from the database."""
        if not self.is_azure_sql():
            return {"error": "Automatic Tuning is only available on Azure SQL"}

        try:
            # Get current automatic tuning settings
            result = self.db.execute(
                text("""
                    SELECT 
                        desired_state,
                        desired_state_reason,
                        actual_state
                    FROM sys.database_automatic_tuning_options
                    WHERE name = 'FORCE_LAST_GOOD_PLAN'
                """)
            ).fetchone()

            if not result:
                return {"error": "Could not retrieve tuning options"}

            # Get all options
            all_options = self.db.execute(
                text("""
                    SELECT 
                        name,
                        desired_state,
                        actual_state,
                        reason,
                        is_disabled_reason
                    FROM sys.database_automatic_tuning_options
                    ORDER BY name
                """)
            ).fetchall()

            return {
                row.name.lower().replace("force_last_good_plan", "force_last_good_plan"): {
                    "desired": row.desired_state,
                    "actual": row.actual_state,
                    "reason": row.reason,
                    "disabled_reason": row.is_disabled_reason,
                }
                for row in all_options
            }

        except Exception as e:
            logger.error(f"Failed to get tuning options: {e}")
            return {"error": str(e)}

    def set_tuning_option(self, option_name: str, state: str) -> bool:
        """Set a specific automatic tuning option.

        Args:
            option_name: Option name (e.g., 'FORCE_LAST_GOOD_PLAN')
            state: Desired state ('ON', 'OFF', or 'DEFAULT')

        Returns:
            True if successful, False otherwise
        """
        if not self.is_azure_sql():
            logger.error("Automatic Tuning is only available on Azure SQL")
            return False

        valid_options = [
            "FORCE_LAST_GOOD_PLAN",
            "CREATE_INDEX",
            "DROP_INDEX",
            "MAINTAIN_INDEX",
        ]

        if option_name.upper() not in valid_options:
            logger.error(f"Invalid option: {option_name}")
            logger.info(f"Valid options: {', '.join(valid_options)}")
            return False

        valid_states = ["ON", "OFF", "DEFAULT"]
        if state.upper() not in valid_states:
            logger.error(f"Invalid state: {state}")
            logger.info(f"Valid states: {', '.join(valid_states)}")
            return False

        try:
            # Build and execute ALTER DATABASE statement
            sql = f"""
                ALTER DATABASE CURRENT
                SET AUTOMATIC_TUNING ( {option_name} = {state.upper()} )
            """
            self.db.execute(text(sql))
            self.db.commit()

            logger.info(f"✅ Set {option_name} = {state.upper()}")
            return True

        except Exception as e:
            logger.error(f"Failed to set {option_name}: {e}")
            self.db.rollback()
            return False

    def configure_all(self, options: TuningOptions) -> bool:
        """Configure all automatic tuning options."""
        if not self.is_azure_sql():
            logger.error("Automatic Tuning is only available on Azure SQL")
            return False

        success = True

        success &= self.set_tuning_option("FORCE_LAST_GOOD_PLAN", options.force_last_good_plan)
        success &= self.set_tuning_option("CREATE_INDEX", options.create_index)
        success &= self.set_tuning_option("DROP_INDEX", options.drop_index)
        success &= self.set_tuning_option("MAINTAIN_INDEX", options.maintain_index)

        return success

    def get_tuning_recommendations(self) -> list[dict[str, Any]]:
        """Get active automatic tuning recommendations.

        Returns:
            List of tuning recommendations from sys.dm_db_tuning_recommendations
        """
        if not self.is_azure_sql():
            return []

        try:
            result = self.db.execute(
                text("""
                    SELECT 
                        tr.type,
                        tr.state,
                        tr.state_desc,
                        tr.details,
                        tr.script,
                        tr.estimated_gain,
                        tr.error,
                        tr.regressed_plan_id,
                        tr.regressed_plan_execution_count,
                        tr.regressed_plan_error_count,
                        tr.regressed_plan_corrected_count,
                        tr.regressed_plan_first_execution_time,
                        tr.regressed_plan_last_execution_time,
                        tr.regressed_plan_average_duration,
                        tr.regressed_plan_total_duration
                    FROM sys.dm_db_tuning_recommendations tr
                    ORDER BY tr.estimated_gain DESC
                """)
            ).fetchall()

            recommendations = []
            for row in result:
                try:
                    details = json.loads(row.details) if row.details else {}
                except:
                    details = {"raw": row.details}

                recommendations.append(
                    {
                        "type": row.type,
                        "state": row.state,
                        "state_description": row.state_desc,
                        "details": details,
                        "script": row.script,
                        "estimated_gain": float(row.estimated_gain) if row.estimated_gain else None,
                        "error": row.error,
                        "regressed_plan": {
                            "plan_id": row.regressed_plan_id,
                            "execution_count": row.regressed_plan_execution_count,
                            "error_count": row.regressed_plan_error_count,
                            "corrected_count": row.regressed_plan_corrected_count,
                        }
                        if row.regressed_plan_id
                        else None,
                    }
                )

            return recommendations

        except Exception as e:
            logger.error(f"Failed to get tuning recommendations: {e}")
            return []

    def get_query_store_config(self) -> dict[str, Any]:
        """Get Query Store configuration."""
        if not self.is_azure_sql():
            return {"error": "Query Store is only available on Azure SQL"}

        try:
            result = self.db.execute(
                text("""
                    SELECT 
                        actual_state,
                        actual_state_desc,
                        readonly_reason,
                        current_storage_size_mb,
                        flush_interval_seconds,
                        interval_length_minutes,
                        stale_query_threshold_days,
                        max_storage_size_mb,
                        query_capture_mode,
                        query_capture_mode_desc,
                        size_based_cleanup_mode,
                        size_based_cleanup_mode_desc
                    FROM sys.database_query_store_options
                """)
            ).fetchone()

            if not result:
                return {"error": "Could not retrieve Query Store configuration"}

            return {
                "actual_state": result.actual_state_desc,
                "readonly_reason": result.readonly_reason,
                "current_storage_size_mb": result.current_storage_size_mb,
                "max_storage_size_mb": result.max_storage_size_mb,
                "storage_utilization_percent": (
                    (result.current_storage_size_mb / result.max_storage_size_mb * 100)
                    if result.max_storage_size_mb
                    else None
                ),
                "flush_interval_seconds": result.flush_interval_seconds,
                "interval_length_minutes": result.interval_length_minutes,
                "stale_query_threshold_days": result.stale_query_threshold_days,
                "query_capture_mode": result.query_capture_mode_desc,
                "size_based_cleanup_mode": result.size_based_cleanup_mode_desc,
            }

        except Exception as e:
            logger.error(f"Failed to get Query Store config: {e}")
            return {"error": str(e)}

    def set_query_store_config(
        self,
        operation_mode: str = "READ_WRITE",
        max_storage_mb: int = 100,
        stale_threshold_days: int = 30,
        interval_minutes: int = 60,
    ) -> bool:
        """Configure Query Store settings."""
        if not self.is_azure_sql():
            logger.error("Query Store is only available on Azure SQL")
            return False

        try:
            sql = f"""
                ALTER DATABASE CURRENT
                SET QUERY_STORE = ON (
                    OPERATION_MODE = {operation_mode},
                    MAX_STORAGE_SIZE_MB = {max_storage_mb},
                    STALE_QUERY_THRESHOLD_DAYS = {stale_threshold_days},
                    INTERVAL_LENGTH_MINUTES = {interval_minutes},
                    QUERY_CAPTURE_MODE = AUTO,
                    SIZE_BASED_CLEANUP_MODE = AUTO
                )
            """
            self.db.execute(text(sql))
            self.db.commit()

            logger.info("✅ Query Store configured:")
            logger.info(f"   Operation Mode: {operation_mode}")
            logger.info(f"   Max Storage: {max_storage_mb} MB")
            logger.info(f"   Stale Threshold: {stale_threshold_days} days")
            logger.info(f"   Interval: {interval_minutes} minutes")

            return True

        except Exception as e:
            logger.error(f"Failed to configure Query Store: {e}")
            self.db.rollback()
            return False

    def print_status(self) -> None:
        """Print comprehensive status of automatic tuning."""
        print("\n" + "=" * 80)
        print("AZURE SQL AUTOMATIC TUNING STATUS")
        print("=" * 80)

        if not self.is_azure_sql():
            print("\n⚠️  Automatic Tuning is only available on Azure SQL")
            print("   Current connection: SQLite or other non-Azure SQL database")
            return

        # Current tuning options
        options = self.get_current_tuning_options()
        print("\n📊 Automatic Tuning Options:")
        print("-" * 80)

        if "error" in options:
            print(f"   Error: {options['error']}")
        else:
            for name, values in options.items():
                status_icon = (
                    "🟢"
                    if values.get("actual") == "ON"
                    else "🔴"
                    if values.get("actual") == "OFF"
                    else "⚪"
                )
                print(f"\n   {status_icon} {name.upper()}")
                print(f"      Desired: {values.get('desired', 'N/A')}")
                print(f"      Actual: {values.get('actual', 'N/A')}")
                if values.get("reason"):
                    print(f"      Reason: {values['reason']}")
                if name in self.OPTION_DESCRIPTIONS:
                    print(f"      {self.OPTION_DESCRIPTIONS[name]}")

        # Query Store status
        print("\n📈 Query Store Configuration:")
        print("-" * 80)
        qs_config = self.get_query_store_config()

        if "error" in qs_config:
            print(f"   Error: {qs_config['error']}")
        else:
            state_icon = "🟢" if qs_config.get("actual_state") == "READ_WRITE" else "🔴"
            print(f"\n   {state_icon} State: {qs_config.get('actual_state')}")
            print(
                f"   Storage: {qs_config.get('current_storage_size_mb'):.1f} / {qs_config.get('max_storage_size_mb')} MB"
            )
            print(f"   Storage Utilization: {qs_config.get('storage_utilization_percent', 0):.1f}%")
            print(f"   Stale Query Threshold: {qs_config.get('stale_query_threshold_days')} days")
            print(f"   Capture Mode: {qs_config.get('query_capture_mode')}")
            print(f"   Cleanup Mode: {qs_config.get('size_based_cleanup_mode')}")

        # Active recommendations
        print("\n💡 Active Tuning Recommendations:")
        print("-" * 80)
        recommendations = self.get_tuning_recommendations()

        if not recommendations:
            print("   No active recommendations")
        else:
            for i, rec in enumerate(recommendations[:10], 1):
                print(f"\n   {i}. Type: {rec['type']} | State: {rec['state_description']}")
                if rec.get("estimated_gain"):
                    print(f"      Estimated Gain: {rec['estimated_gain']:.2f}%")
                if rec.get("details"):
                    print(f"      Details: {json.dumps(rec['details'], indent=6)[:200]}...")


def main():
    parser = argparse.ArgumentParser(
        description="Configure Azure SQL Automatic Tuning",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Check current status
  %(prog)s --status

  # Enable all automatic tuning features
  %(prog)s --enable-all

  # Enable specific features
  %(prog)s --enable-plan-correction --enable-create-index

  # Configure Query Store
  %(prog)s --configure-query-store --qs-max-storage 200 --qs-stale-days 30

  # View recommendations
  %(prog)s --recommendations

Tuning Options:
  FORCE_LAST_GOOD_PLAN - Revert to last known good plan on regression
  CREATE_INDEX - Automatically create beneficial indexes
  DROP_INDEX - Automatically drop unused indexes
  MAINTAIN_INDEX - Automatically rebuild fragmented indexes
        """,
    )

    # Status commands
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show current automatic tuning status",
    )
    parser.add_argument(
        "--recommendations",
        action="store_true",
        help="Show active tuning recommendations",
    )

    # Enable/disable options
    parser.add_argument(
        "--enable-all",
        action="store_true",
        help="Enable all automatic tuning features",
    )
    parser.add_argument(
        "--disable-all",
        action="store_true",
        help="Disable all automatic tuning features",
    )
    parser.add_argument(
        "--enable-plan-correction",
        action="store_true",
        help="Enable automatic plan correction (FORCE_LAST_GOOD_PLAN)",
    )
    parser.add_argument(
        "--disable-plan-correction",
        action="store_true",
        help="Disable automatic plan correction",
    )
    parser.add_argument(
        "--enable-create-index",
        action="store_true",
        help="Enable automatic index creation",
    )
    parser.add_argument(
        "--disable-create-index",
        action="store_true",
        help="Disable automatic index creation",
    )
    parser.add_argument(
        "--enable-drop-index",
        action="store_true",
        help="Enable automatic index deletion",
    )
    parser.add_argument(
        "--disable-drop-index",
        action="store_true",
        help="Disable automatic index deletion",
    )

    # Query Store configuration
    parser.add_argument(
        "--configure-query-store",
        action="store_true",
        help="Configure Query Store settings",
    )
    parser.add_argument(
        "--qs-max-storage",
        type=int,
        default=100,
        help="Query Store max storage in MB (default: 100)",
    )
    parser.add_argument(
        "--qs-stale-days",
        type=int,
        default=30,
        help="Query Store stale query threshold in days (default: 30)",
    )
    parser.add_argument(
        "--qs-interval",
        type=int,
        default=60,
        help="Query Store interval length in minutes (default: 60)",
    )

    # Output
    parser.add_argument(
        "--output",
        type=str,
        help="Output file for JSON results",
    )

    args = parser.parse_args()

    # If no action specified, show help
    if not any(
        [
            args.status,
            args.recommendations,
            args.enable_all,
            args.disable_all,
            args.enable_plan_correction,
            args.disable_plan_correction,
            args.enable_create_index,
            args.disable_create_index,
            args.enable_drop_index,
            args.disable_drop_index,
            args.configure_query_store,
        ]
    ):
        parser.print_help()
        sys.exit(0)

    # Initialize
    print("\n🔌 Connecting to database...")
    db = SessionLocal()

    try:
        manager = AzureSQLTuningManager(db)

        if not manager.is_azure_sql():
            print("\n⚠️  Automatic Tuning is only available on Azure SQL")
            print("   Current connection: SQLite or other non-Azure SQL database")
            sys.exit(1)

        # Execute requested actions
        if args.status:
            manager.print_status()

        if args.recommendations:
            print("\n" + "=" * 80)
            print("TUNING RECOMMENDATIONS")
            print("=" * 80)
            recommendations = manager.get_tuning_recommendations()
            print(json.dumps(recommendations, indent=2, default=str))

        # Handle enable/disable options
        if args.enable_all:
            print("\n" + "=" * 80)
            print("ENABLING ALL AUTOMATIC TUNING FEATURES")
            print("=" * 80)
            options = TuningOptions(
                force_last_good_plan="ON",
                create_index="ON",
                drop_index="ON",
                maintain_index="ON",
            )
            success = manager.configure_all(options)
            if success:
                print("\n✅ All features enabled successfully")
            else:
                print("\n❌ Some features could not be enabled")

        if args.disable_all:
            print("\n" + "=" * 80)
            print("DISABLING ALL AUTOMATIC TUNING FEATURES")
            print("=" * 80)
            options = TuningOptions(
                force_last_good_plan="OFF",
                create_index="OFF",
                drop_index="OFF",
                maintain_index="OFF",
            )
            success = manager.configure_all(options)
            if success:
                print("\n✅ All features disabled successfully")
            else:
                print("\n❌ Some features could not be disabled")

        # Individual options
        if args.enable_plan_correction:
            manager.set_tuning_option("FORCE_LAST_GOOD_PLAN", "ON")
        if args.disable_plan_correction:
            manager.set_tuning_option("FORCE_LAST_GOOD_PLAN", "OFF")

        if args.enable_create_index:
            manager.set_tuning_option("CREATE_INDEX", "ON")
        if args.disable_create_index:
            manager.set_tuning_option("CREATE_INDEX", "OFF")

        if args.enable_drop_index:
            manager.set_tuning_option("DROP_INDEX", "ON")
        if args.disable_drop_index:
            manager.set_tuning_option("DROP_INDEX", "OFF")

        if args.configure_query_store:
            print("\n" + "=" * 80)
            print("CONFIGURING QUERY STORE")
            print("=" * 80)
            manager.set_query_store_config(
                max_storage_mb=args.qs_max_storage,
                stale_threshold_days=args.qs_stale_days,
                interval_minutes=args.qs_interval,
            )

        # Save output if requested
        if args.output:
            output_data = {
                "tuning_options": manager.get_current_tuning_options(),
                "query_store_config": manager.get_query_store_config(),
                "recommendations": manager.get_tuning_recommendations(),
            }
            with open(args.output, "w") as f:
                json.dump(output_data, f, indent=2, default=str)
            print(f"\n💾 Results saved to: {args.output}")

        print("\n" + "=" * 80)
        print("Configuration complete! 🎉")
        print("=" * 80 + "\n")

    except Exception as e:
        logger.error(f"Configuration failed: {e}")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
