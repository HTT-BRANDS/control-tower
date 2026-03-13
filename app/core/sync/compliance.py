"""Compliance data synchronization module."""

import logging
from datetime import datetime

from azure.core.exceptions import HttpResponseError

from app.api.services.azure_client import azure_client_manager
from app.api.services.monitoring_service import MonitoringService
from app.core.circuit_breaker import COMPLIANCE_SYNC_BREAKER, circuit_breaker
from app.core.database import get_db_context
from app.core.retry import COMPLIANCE_SYNC_POLICY, retry_with_backoff
from app.models.compliance import ComplianceSnapshot, PolicyState
from app.models.tenant import Tenant

logger = logging.getLogger(__name__)


@circuit_breaker(COMPLIANCE_SYNC_BREAKER)
@retry_with_backoff(COMPLIANCE_SYNC_POLICY)
async def sync_compliance():
    """Sync compliance data from all tenants.

    Fetches policy compliance states from Azure Policy Insights API
    and secure scores from Azure Security Center for all active tenants
    and their subscriptions, storing results in ComplianceSnapshot and
    PolicyState models.
    """
    logger.info(f"Starting compliance sync at {datetime.utcnow()}")

    snapshot_date = datetime.utcnow().date()
    total_snapshots = 0
    total_policy_states = 0
    total_errors = 0
    log_id = None

    try:
        with get_db_context() as db:
            # Start monitoring
            monitoring = MonitoringService(db)
            log_entry = monitoring.start_sync_job(job_type="compliance")
            log_id = log_entry.id
            # Get all active tenants
            tenants = db.query(Tenant).filter(Tenant.is_active).all()
            logger.info(f"Found {len(tenants)} active tenants to sync for compliance")

            for tenant in tenants:
                logger.info(f"Syncing compliance for tenant: {tenant.name} ({tenant.tenant_id})")

                try:
                    # Get subscriptions for this tenant
                    subscriptions = await azure_client_manager.list_subscriptions(tenant.tenant_id)
                    logger.info(
                        f"Found {len(subscriptions)} subscriptions for tenant {tenant.name}"
                    )

                    for sub in subscriptions:
                        sub_id = sub["subscription_id"]
                        sub_name = sub["display_name"]

                        # Skip non-enabled subscriptions
                        if sub["state"] != "Enabled":
                            logger.info(f"Skipping subscription {sub_name} (state: {sub['state']})")
                            continue

                        try:
                            logger.info(
                                f"Querying compliance for subscription: {sub_name} ({sub_id[:8]}...)"
                            )

                            # Get policy and security clients
                            policy_client = azure_client_manager.get_policy_client(
                                tenant.tenant_id, sub_id
                            )
                            security_client = azure_client_manager.get_security_client(
                                tenant.tenant_id, sub_id
                            )

                            # Initialize counters for this subscription
                            compliant_resources = 0
                            non_compliant_resources = 0
                            exempt_resources = 0
                            secure_score = None

                            # Query Azure Policy Insights for compliance states
                            try:
                                policy_states = (
                                    policy_client.policy_states.list_query_results_for_subscription(
                                        policy_states_resource="latest",
                                        subscription_id=sub_id,
                                    )
                                )

                                # Track unique policies for aggregation
                                policy_aggregates = {}

                                for state in policy_states:
                                    policy_def_id = state.policy_definition_id or "unknown"
                                    policy_name = (
                                        state.policy_definition_reference_id or "Unknown Policy"
                                    )
                                    # SDK v4+ returns strings; older versions return enums
                                    raw_state = state.compliance_state
                                    compliance_state = (
                                        raw_state.value
                                        if hasattr(raw_state, "value")
                                        else str(raw_state)
                                        if raw_state
                                        else "Unknown"
                                    )
                                    resource_id = state.resource_id or ""
                                    policy_category = None

                                    # Try to extract category from metadata if available
                                    if state.policy_definition_group_names:
                                        policy_category = ",".join(
                                            state.policy_definition_group_names
                                        )

                                    # Aggregate counts
                                    if compliance_state == "Compliant":
                                        compliant_resources += 1
                                    elif compliance_state == "NonCompliant":
                                        non_compliant_resources += 1
                                    elif compliance_state == "Exempt":
                                        exempt_resources += 1

                                    # Track individual policy state
                                    policy_key = (policy_def_id, sub_id)
                                    if policy_key not in policy_aggregates:
                                        policy_aggregates[policy_key] = {
                                            "policy_definition_id": policy_def_id,
                                            "policy_name": policy_name,
                                            "policy_category": policy_category,
                                            "compliance_state": compliance_state,
                                            "non_compliant_count": 0,
                                            "resource_id": resource_id,
                                            "recommendation": None,
                                        }

                                    if compliance_state == "NonCompliant":
                                        policy_aggregates[policy_key]["non_compliant_count"] += 1
                                        # Store first non-compliant resource as example
                                        if not policy_aggregates[policy_key]["resource_id"]:
                                            policy_aggregates[policy_key]["resource_id"] = (
                                                resource_id
                                            )

                                # Create PolicyState records
                                for policy_data in policy_aggregates.values():
                                    policy_state = PolicyState(
                                        tenant_id=tenant.id,
                                        subscription_id=sub_id,
                                        policy_definition_id=policy_data["policy_definition_id"],
                                        policy_name=policy_data["policy_name"],
                                        policy_category=policy_data["policy_category"],
                                        compliance_state=policy_data["compliance_state"],
                                        non_compliant_count=policy_data["non_compliant_count"],
                                        resource_id=policy_data["resource_id"],
                                        recommendation=policy_data["recommendation"],
                                        synced_at=datetime.utcnow(),
                                    )
                                    db.add(policy_state)
                                    total_policy_states += 1

                                logger.info(
                                    f"Processed {len(policy_aggregates)} unique policies "
                                    f"for subscription {sub_name}"
                                )

                            except HttpResponseError as e:
                                if e.status_code == 403:
                                    logger.error(
                                        f"Access denied to policy data for subscription {sub_name}. "
                                        f"Missing Policy Insights Reader role?"
                                    )
                                else:
                                    logger.error(
                                        f"HTTP error querying policy states for {sub_name}: "
                                        f"{e.status_code} - {e.message}"
                                    )
                                # Continue with security score even if policy query fails

                            # Query Azure Security Center for secure score
                            try:
                                secure_scores = security_client.secure_scores.list()
                                for score in secure_scores:
                                    # Get the overall secure score (percentage)
                                    if score.name == "ascScore":
                                        # SDK flattens properties.score.current → score.current
                                        secure_score = getattr(score, "current", None)
                                        if secure_score is None and hasattr(score, "score"):
                                            secure_score = getattr(score.score, "current", None)
                                        break

                                if secure_score is not None:
                                    logger.info(f"Secure score for {sub_name}: {secure_score:.2f}")
                                else:
                                    logger.info(
                                        f"No secure score found for subscription {sub_name}"
                                    )

                            except HttpResponseError as e:
                                if e.status_code == 403:
                                    logger.error(
                                        f"Access denied to Security Center for subscription {sub_name}. "
                                        f"Missing Security Reader role?"
                                    )
                                else:
                                    logger.error(
                                        f"HTTP error querying secure scores for {sub_name}: "
                                        f"{e.status_code} - {e.message}"
                                    )
                                # Continue without secure score

                            # Calculate overall compliance percentage
                            total_evaluated = (
                                compliant_resources + non_compliant_resources + exempt_resources
                            )
                            overall_compliance = (
                                (compliant_resources / total_evaluated * 100)
                                if total_evaluated > 0
                                else 0.0
                            )

                            # Create ComplianceSnapshot
                            snapshot = ComplianceSnapshot(
                                tenant_id=tenant.id,
                                subscription_id=sub_id,
                                snapshot_date=snapshot_date,
                                overall_compliance_percent=overall_compliance,
                                secure_score=secure_score,
                                compliant_resources=compliant_resources,
                                non_compliant_resources=non_compliant_resources,
                                exempt_resources=exempt_resources,
                                synced_at=datetime.utcnow(),
                            )
                            db.add(snapshot)
                            db.commit()
                            total_snapshots += 1

                            logger.info(
                                f"Compliance snapshot for {sub_name}: "
                                f"{overall_compliance:.1f}% compliant "
                                f"({compliant_resources}/{total_evaluated} resources)"
                            )

                        except HttpResponseError as e:
                            total_errors += 1
                            if e.status_code == 403:
                                logger.error(
                                    f"Access denied to compliance data for subscription {sub_name}. "
                                    f"Check Azure RBAC permissions."
                                )
                            else:
                                logger.error(
                                    f"HTTP error syncing compliance for {sub_name}: "
                                    f"{e.status_code} - {e.message}"
                                )
                        except Exception as e:
                            total_errors += 1
                            logger.error(
                                f"Error syncing compliance for subscription {sub_name}: {e}",
                                exc_info=True,
                            )

                except Exception as e:
                    total_errors += 1
                    logger.error(
                        f"Error processing tenant {tenant.name}: {e}",
                        exc_info=True,
                    )

        # Update monitoring with final status
        if log_id:
            monitoring.complete_sync_job(
                log_id=log_id,
                status="completed" if total_errors == 0 else "failed",
                final_records={
                    "records_processed": total_snapshots + total_policy_states,
                    "records_created": total_snapshots + total_policy_states,
                    "records_updated": 0,
                    "errors_count": total_errors,
                },
            )

        logger.info(
            f"Compliance sync completed: {total_snapshots} snapshots, "
            f"{total_policy_states} policy states synced, "
            f"{total_errors} errors encountered"
        )

    except Exception as e:
        logger.error(f"Fatal error during compliance sync: {e}", exc_info=True)
        # Update monitoring with failure status
        if log_id:
            with get_db_context() as db:
                monitoring = MonitoringService(db)
                monitoring.complete_sync_job(
                    log_id=log_id,
                    status="failed",
                    error_message=str(e)[:1000],
                    final_records={
                        "records_processed": total_snapshots + total_policy_states,
                        "records_created": total_snapshots + total_policy_states,
                        "records_updated": 0,
                        "errors_count": total_errors + 1,
                    },
                )
        raise
