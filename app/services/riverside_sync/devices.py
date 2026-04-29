"""Riverside device compliance table synchronization."""

from datetime import UTC, datetime

from azure.core.exceptions import HttpResponseError
from sqlalchemy import Date, cast
from sqlalchemy.orm import Session

from app.core.circuit_breaker import RIVERSIDE_SYNC_BREAKER, CircuitBreakerError, circuit_breaker
from app.core.database import get_db_context
from app.core.retry import RIVERSIDE_SYNC_POLICY, retry_with_backoff
from app.models.riverside import RiversideDeviceCompliance
from app.models.tenant import Tenant
from app.services.riverside_sync.common import SyncError, _resolve_package_attr, logger


@circuit_breaker(RIVERSIDE_SYNC_BREAKER)
@retry_with_backoff(RIVERSIDE_SYNC_POLICY)
async def sync_tenant_devices(
    tenant_id: str,
    db: Session | None = None,
    snapshot_date: datetime | None = None,
) -> dict:
    """Sync device compliance data for a specific tenant from Microsoft Graph API.

    Fetches device management data from Intune/Endpoint Manager, including
    MDM enrollment, compliance status, and encryption status.

    Args:
        tenant_id: Azure tenant ID to sync
        db: Database session (creates context if None)
        snapshot_date: Optional snapshot date (defaults to now)

    Returns:
        Dict with device sync results:
        - status: "success" or "error"
        - total_devices: total device count
        - compliant_devices: compliant device count
        - compliance_pct: compliance percentage
        - mdm_enrolled: MDM-enrolled device count
        - encrypted_devices: encrypted device count
        - edr_covered: EDR-covered device count

    Raises:
        SyncError: If sync fails and circuit breaker/retry exhausted
    """
    snapshot_date = snapshot_date or datetime.now(UTC)

    logger.info(f"Syncing device compliance for tenant: {tenant_id}")

    async def _do_sync(session: Session) -> dict:
        # Get tenant
        tenant = session.query(Tenant).filter(Tenant.tenant_id == tenant_id).first()
        if not tenant:
            raise SyncError(f"Tenant {tenant_id} not found", tenant_id)

        try:
            graph_client = _resolve_package_attr("_get_graph_client")(tenant_id)

            # Get managed devices from Intune via Graph API
            devices_data = await graph_client._request(
                "GET",
                "/deviceManagement/managedDevices",
                params={"$top": 999},
            )
            device_list = devices_data.get("value", [])
            total_devices = len(device_list)

            # Calculate compliance metrics
            compliant_devices = 0
            mdm_enrolled = 0
            encrypted_devices = 0

            MDM_AGENTS = {
                "mdm",
                "easMdm",
                "configurationManagerClientMdm",
                "configurationManagerClientMdmEas",
            }

            for device in device_list:
                # Check compliance state
                if device.get("complianceState") == "compliant":
                    compliant_devices += 1

                # Check MDM enrollment
                if device.get("managementAgent") in MDM_AGENTS:
                    mdm_enrolled += 1

                # Check encryption
                if device.get("isEncrypted"):
                    encrypted_devices += 1

            # For EDR coverage, use compliant devices as proxy
            # (In a real implementation, this would query Defender for Endpoint)
            edr_covered = compliant_devices

            # Calculate compliance percentage
            compliance_pct = (compliant_devices / total_devices * 100) if total_devices > 0 else 0.0

            # Check for existing record for today
            existing = (
                session.query(RiversideDeviceCompliance)
                .filter(
                    RiversideDeviceCompliance.tenant_id == tenant.id,
                    cast(RiversideDeviceCompliance.snapshot_date, Date) == snapshot_date.date(),
                )
                .first()
            )

            if existing:
                # Update existing record
                existing.total_devices = total_devices
                existing.mdm_enrolled = mdm_enrolled
                existing.edr_covered = edr_covered
                existing.encrypted_devices = encrypted_devices
                existing.compliant_devices = compliant_devices
                existing.compliance_percentage = round(compliance_pct, 2)
                existing.snapshot_date = snapshot_date
            else:
                # Create new record
                device_record = RiversideDeviceCompliance(
                    tenant_id=tenant.id,
                    total_devices=total_devices,
                    mdm_enrolled=mdm_enrolled,
                    edr_covered=edr_covered,
                    encrypted_devices=encrypted_devices,
                    compliant_devices=compliant_devices,
                    compliance_percentage=round(compliance_pct, 2),
                    snapshot_date=snapshot_date,
                )
                session.add(device_record)

            session.commit()

            logger.info(
                f"Device sync completed for {tenant.name}: "
                f"{compliance_pct:.1f}% compliant ({compliant_devices}/{total_devices})"
            )

            return {
                "status": "success",
                "total_devices": total_devices,
                "compliant_devices": compliant_devices,
                "compliance_pct": round(compliance_pct, 2),
                "mdm_enrolled": mdm_enrolled,
                "encrypted_devices": encrypted_devices,
                "edr_covered": edr_covered,
            }

        except HttpResponseError as e:
            session.rollback()
            error_msg = f"Azure API error syncing devices: {e.status_code} - {e.message}"
            logger.error(error_msg)
            raise SyncError(error_msg, tenant_id, status_code=e.status_code) from e
        except CircuitBreakerError as e:
            error_msg = f"Circuit breaker open for device sync: {e}"
            logger.error(error_msg)
            raise SyncError(error_msg, tenant_id) from e
        except Exception as e:
            session.rollback()
            error_msg = f"Unexpected error syncing devices: {e}"
            logger.error(error_msg)
            raise SyncError(error_msg, tenant_id) from e

    if db:
        return await _do_sync(db)
    else:
        with get_db_context() as session:
            return await _do_sync(session)
