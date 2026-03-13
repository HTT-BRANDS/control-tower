"""DMARC/DKIM insights service for email security monitoring.

Provides email authentication monitoring and security scoring
for Riverside Company tenants with July 2026 compliance deadline.
"""

import json
import logging
import re
import uuid
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.api.services.graph_client import GraphClient
from app.core.cache import cached, invalidate_on_sync_completion
from app.models.dmarc import DKIMRecord, DMARCAlert, DMARCRecord, DMARCReport
from app.models.tenant import Tenant

logger = logging.getLogger(__name__)

# Riverside tenant IDs (from existing codebase)
RIVERSIDE_TENANTS = {
    "riverside-htt": "HTT Tenant",
    "riverside-bcc": "BCC Tenant",
    "riverside-fn": "FN Tenant",
    "riverside-tll": "TLL Tenant",
}


class DMARCService:
    """Service for collecting and analyzing DMARC/DKIM data."""

    def __init__(self, db: Session):
        self.db = db

    async def sync_dmarc_records(self, tenant_id: str) -> list[DMARCRecord]:
        """Sync DMARC records from Graph Security API.

        Queries Microsoft Graph for domain security configuration
        and parses DMARC records.
        """
        records = []
        tenant = self.db.query(Tenant).filter(Tenant.id == tenant_id).first()

        if not tenant:
            logger.warning(f"Tenant {tenant_id} not found")
            return records

        try:
            # Get domains from Graph API
            graph_client = GraphClient(tenant.tenant_id)
            domains = await self._fetch_domains(graph_client)

            for domain_data in domains:
                domain_name = domain_data.get("id", "")
                if not domain_name or "onmicrosoft.com" in domain_name:
                    continue

                # Check DNS for DMARC record
                dmarc_record = await self._query_dmarc_dns(domain_name)

                if dmarc_record:
                    record = self._parse_dmarc_record(tenant_id, domain_name, dmarc_record)
                    records.append(record)
                    self.db.merge(record)

            self.db.commit()
            logger.info(f"Synced {len(records)} DMARC records for tenant {tenant.name}")

        except Exception as e:
            logger.error(f"Error syncing DMARC for tenant {tenant_id}: {e}")
            self.db.rollback()
            raise

        return records

    async def sync_dkim_records(self, tenant_id: str) -> list[DKIMRecord]:
        """Sync DKIM records from Graph API.

        Queries tenant domains and checks DKIM configuration status.
        """
        records = []
        tenant = self.db.query(Tenant).filter(Tenant.id == tenant_id).first()

        if not tenant:
            logger.warning(f"Tenant {tenant_id} not found")
            return records

        try:
            # Get DKIM signing configuration from Graph
            graph_client = GraphClient(tenant.tenant_id)
            dkim_configs = await self._fetch_dkim_config(graph_client)

            for config in dkim_configs:
                domain = config.get("domain", "")
                if not domain:
                    continue

                record = DKIMRecord(
                    id=str(uuid.uuid4()),
                    tenant_id=tenant_id,
                    domain=domain,
                    selector=config.get("selector", "default"),
                    is_enabled=config.get("enabled", False),
                    key_size=config.get("keySize", 2048),
                    key_type=config.get("keyType", "RSA"),
                    last_rotated=self._parse_datetime(config.get("lastRotatedDateTime")),
                    next_rotation_due=self._parse_datetime(config.get("nextRotationDateTime")),
                    dns_record_value=config.get("dnsRecordValue"),
                    is_aligned=config.get("alignmentStatus") == "aligned",
                    selector_status=config.get("status", "unknown"),
                    synced_at=datetime.utcnow(),
                )
                records.append(record)
                self.db.merge(record)

            self.db.commit()
            logger.info(f"Synced {len(records)} DKIM records for tenant {tenant.name}")

        except Exception as e:
            logger.error(f"Error syncing DKIM for tenant {tenant_id}: {e}")
            self.db.rollback()
            raise

        return records

    @cached("dmarc_summary")
    async def get_dmarc_summary(self, tenant_id: str | None = None) -> dict[str, Any]:
        """Get DMARC/DKIM summary across tenants.

        Returns aggregated statistics including pass/fail rates,
        compliance percentages, and recent failures.
        """
        summary = {
            "total_domains": 0,
            "dmarc_enabled": 0,
            "dmarc_compliant": 0,
            "dkim_enabled": 0,
            "dkim_aligned": 0,
            "average_security_score": 0.0,
            "tenants": [],
            "recent_failures": [],
            "alerts": [],
        }

        # Build query based on tenant filter
        dmarc_query = self.db.query(DMARCRecord)
        dkim_query = self.db.query(DKIMRecord)
        tenant_query = self.db.query(Tenant).filter(Tenant.is_active)

        if tenant_id:
            dmarc_query = dmarc_query.filter(DMARCRecord.tenant_id == tenant_id)
            dkim_query = dkim_query.filter(DKIMRecord.tenant_id == tenant_id)
            tenant_query = tenant_query.filter(Tenant.id == tenant_id)

        tenants = tenant_query.all()

        for tenant in tenants:
            tenant_dmarc = dmarc_query.filter(DMARCRecord.tenant_id == tenant.id).all()
            tenant_dkim = dkim_query.filter(DKIMRecord.tenant_id == tenant.id).all()

            # Calculate security score
            security_score = self._calculate_tenant_security_score(tenant_dmarc, tenant_dkim)

            tenant_summary = {
                "tenant_id": tenant.id,
                "tenant_name": tenant.name,
                "domain_count": len(tenant_dmarc),
                "dmarc_enabled_count": sum(1 for d in tenant_dmarc if d.policy != "none"),
                "dmarc_reject_count": sum(1 for d in tenant_dmarc if d.policy == "reject"),
                "dkim_enabled_count": sum(1 for d in tenant_dkim if d.is_enabled),
                "dkim_aligned_count": sum(1 for d in tenant_dkim if d.is_aligned),
                "security_score": security_score,
                "dmarc_records": [
                    {
                        "domain": d.domain,
                        "policy": d.policy,
                        "pct": d.pct,
                        "is_valid": d.is_valid,
                    }
                    for d in tenant_dmarc
                ],
                "dkim_records": [
                    {
                        "domain": d.domain,
                        "is_enabled": d.is_enabled,
                        "is_aligned": d.is_aligned,
                        "is_stale": d.is_key_stale,
                    }
                    for d in tenant_dkim
                ],
            }
            summary["tenants"].append(tenant_summary)

        # Aggregate totals
        all_dmarc = dmarc_query.all()
        all_dkim = dkim_query.all()

        summary["total_domains"] = len({d.domain for d in all_dmarc})
        summary["dmarc_enabled"] = sum(1 for d in all_dmarc if d.policy != "none")
        summary["dmarc_compliant"] = sum(1 for d in all_dmarc if d.policy == "reject")
        summary["dkim_enabled"] = sum(1 for d in all_dkim if d.is_enabled)
        summary["dkim_aligned"] = sum(1 for d in all_dkim if d.is_aligned)

        if summary["tenants"]:
            summary["average_security_score"] = sum(
                t["security_score"] for t in summary["tenants"]
            ) / len(summary["tenants"])

        # Get recent failures
        summary["recent_failures"] = await self._get_recent_failures(tenant_id)

        # Get active alerts
        summary["alerts"] = await self._get_active_alerts(tenant_id)

        return summary

    def get_domain_security_score(self, tenant_id: str) -> float:
        """Calculate domain security score (0-100).

        Based on DMARC policy strength, DKIM alignment, and overall
        email authentication configuration.
        """
        dmarc_records = self.db.query(DMARCRecord).filter(DMARCRecord.tenant_id == tenant_id).all()
        dkim_records = self.db.query(DKIMRecord).filter(DKIMRecord.tenant_id == tenant_id).all()

        return self._calculate_tenant_security_score(dmarc_records, dkim_records)

    async def sync_dmarc_reports(self, tenant_id: str) -> list[DMARCReport]:
        """Sync DMARC aggregate reports for a tenant.

        Processes DMARC aggregate reports from configured RUA endpoints.
        """
        reports = []
        tenant = self.db.query(Tenant).filter(Tenant.id == tenant_id).first()

        if not tenant:
            return reports

        try:
            # Get RUA endpoints from DMARC records
            dmarc_records = (
                self.db.query(DMARCRecord)
                .filter(DMARCRecord.tenant_id == tenant_id)
                .filter(DMARCRecord.rua.isnot(None))
                .all()
            )

            for record in dmarc_records:
                # Parse RUA URI and fetch reports
                # In production, this would connect to DMARC report services
                report_data = await self._fetch_dmarc_reports(record.rua)

                for data in report_data:
                    report = DMARCReport(
                        id=str(uuid.uuid4()),
                        tenant_id=tenant_id,
                        report_date=data.get("date", datetime.utcnow()),
                        domain=record.domain,
                        messages_total=data.get("total", 0),
                        messages_passed=data.get("passed", 0),
                        messages_failed=data.get("failed", 0),
                        pct_compliant=data.get("compliance_pct", 0.0),
                        dkim_passed=data.get("dkim_passed", 0),
                        dkim_failed=data.get("dkim_failed", 0),
                        spf_passed=data.get("spf_passed", 0),
                        spf_failed=data.get("spf_failed", 0),
                        both_passed=data.get("both_passed", 0),
                        both_failed=data.get("both_failed", 0),
                        source_ip_count=data.get("source_ips", 0),
                        source_domains=json.dumps(data.get("source_domains", [])),
                        reporter=data.get("reporter"),
                        report_id=data.get("report_id"),
                        synced_at=datetime.utcnow(),
                    )
                    reports.append(report)
                    self.db.merge(report)

            self.db.commit()

        except Exception as e:
            logger.error(f"Error syncing DMARC reports for {tenant_id}: {e}")
            self.db.rollback()

        return reports

    def get_dmarc_records(self, tenant_id: str) -> list[DMARCRecord]:
        """Get DMARC records for a tenant."""
        return (
            self.db.query(DMARCRecord)
            .filter(DMARCRecord.tenant_id == tenant_id)
            .order_by(DMARCRecord.domain)
            .all()
        )

    def get_dkim_records(self, tenant_id: str) -> list[DKIMRecord]:
        """Get DKIM records for a tenant."""
        return (
            self.db.query(DKIMRecord)
            .filter(DKIMRecord.tenant_id == tenant_id)
            .order_by(DKIMRecord.domain)
            .all()
        )

    def get_compliance_trends(
        self, tenant_id: str | None = None, days: int = 30
    ) -> list[dict[str, Any]]:
        """Get DMARC compliance trends over time."""
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)

        query = self.db.query(DMARCReport).filter(
            DMARCReport.report_date >= start_date,
            DMARCReport.report_date <= end_date,
        )

        if tenant_id:
            query = query.filter(DMARCReport.tenant_id == tenant_id)

        reports = query.order_by(DMARCReport.report_date).all()

        # Group by date and calculate trends
        trends = []
        by_date: dict[datetime, list[DMARCReport]] = {}

        for report in reports:
            date_key = report.report_date.replace(hour=0, minute=0, second=0, microsecond=0)
            if date_key not in by_date:
                by_date[date_key] = []
            by_date[date_key].append(report)

        for date_key, date_reports in sorted(by_date.items()):
            total = sum(r.messages_total for r in date_reports)
            passed = sum(r.messages_passed for r in date_reports)
            compliance = (passed / total * 100) if total > 0 else 0

            trends.append(
                {
                    "date": date_key.isoformat(),
                    "messages_total": total,
                    "messages_passed": passed,
                    "messages_failed": sum(r.messages_failed for r in date_reports),
                    "compliance_percentage": round(compliance, 2),
                }
            )

        return trends

    async def create_alert(
        self,
        tenant_id: str,
        alert_type: str,
        severity: str,
        message: str,
        domain: str | None = None,
        details: dict | None = None,
    ) -> DMARCAlert:
        """Create a DMARC/DKIM security alert."""
        alert = DMARCAlert(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            alert_type=alert_type,
            severity=severity,
            domain=domain,
            message=message,
            details=json.dumps(details) if details else None,
            created_at=datetime.utcnow(),
        )
        self.db.add(alert)
        self.db.commit()
        return alert

    async def acknowledge_alert(self, alert_id: str, user: str) -> DMARCAlert | None:
        """Acknowledge a DMARC alert."""
        alert = self.db.query(DMARCAlert).filter(DMARCAlert.id == alert_id).first()
        if alert:
            alert.is_acknowledged = True
            alert.acknowledged_by = user
            alert.acknowledged_at = datetime.utcnow()
            self.db.commit()
        return alert

    async def invalidate_cache(self, tenant_id: str | None = None) -> None:
        """Invalidate DMARC cache after sync."""
        await invalidate_on_sync_completion(tenant_id)

    # Helper methods

    async def _fetch_domains(self, graph_client: GraphClient) -> list[dict]:
        """Fetch domains from Graph API."""
        try:
            # Use Graph domains endpoint
            result = await graph_client._request("GET", "/domains")
            return result.get("value", [])
        except Exception as e:
            logger.warning(f"Failed to fetch domains: {e}")
            return []

    async def _fetch_dkim_config(self, graph_client: GraphClient) -> list[dict]:
        """Fetch DKIM configuration from Graph API."""
        try:
            # DKIM configuration is typically in domain settings
            result = await graph_client._request(
                "GET", "/domains", params={"$select": "id,authenticationType,mailExchangeRecords"}
            )
            domains = result.get("value", [])

            configs = []
            for domain in domains:
                domain_id = domain.get("id", "")
                if not domain_id or "onmicrosoft.com" in domain_id:
                    continue

                # Get DKIM signing config if available
                try:
                    dkim_result = await graph_client._request(
                        "GET", f"/domains/{domain_id}/verificationDnsRecords"
                    )
                    records = dkim_result.get("value", [])

                    # Parse DKIM records
                    dkim_record = next(
                        (
                            r
                            for r in records
                            if r.get("recordType") == "TXT" and "DKIM" in r.get("text", "")
                        ),
                        None,
                    )

                    configs.append(
                        {
                            "domain": domain_id,
                            "enabled": domain.get("isVerified", False),
                            "selector": self._extract_dkim_selector(dkim_record),
                            "status": "active" if domain.get("isVerified") else "pending",
                        }
                    )
                except Exception:
                    # Fallback - domain exists but DKIM details not available
                    configs.append(
                        {
                            "domain": domain_id,
                            "enabled": False,
                            "selector": "default",
                            "status": "unknown",
                        }
                    )

            return configs
        except Exception as e:
            logger.warning(f"Failed to fetch DKIM config: {e}")
            return []

    async def _query_dmarc_dns(self, domain: str) -> str | None:
        """Query DNS for DMARC record."""
        try:
            import dns.resolver

            dmarc_domain = f"_dmarc.{domain}"
            answers = dns.resolver.resolve(dmarc_domain, "TXT")

            for rdata in answers:
                txt_record = "".join(str(r) for r in rdata.strings)
                if "v=DMARC1" in txt_record:
                    return txt_record

            return None
        except Exception as e:
            logger.debug(f"DNS lookup failed for {domain}: {e}")
            return None

    def _parse_dmarc_record(self, tenant_id: str, domain: str, record: str) -> DMARCRecord:
        """Parse DMARC TXT record into DMARCRecord model."""
        # Extract key-value pairs from DMARC record
        pattern = r"(\w+)=([^;\s]+)"
        matches = re.findall(pattern, record)

        params = {key.lower(): value for key, value in matches}

        # Validate required fields
        is_valid = "v" in params and params.get("v") == "DMARC1"
        validation_errors = None

        if not is_valid:
            validation_errors = "Missing or invalid DMARC version"

        return DMARCRecord(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            domain=domain,
            policy=params.get("p", "none").lower(),
            pct=int(params.get("pct", "100")),
            rua=params.get("rua"),
            ruf=params.get("ruf"),
            adkim=params.get("adkim", "r").lower(),
            aspf=params.get("aspf", "r").lower(),
            fo=params.get("fo"),
            rf=params.get("rf"),
            ri=int(params.get("ri", "86400")),
            sp=params.get("sp"),
            is_valid=is_valid,
            validation_errors=validation_errors,
            synced_at=datetime.utcnow(),
        )

    async def _fetch_dmarc_reports(self, rua: str | None) -> list[dict]:
        """Fetch DMARC aggregate reports from RUA endpoint.

        In production, this would connect to a DMARC report service
        or parse reports from a mailbox.
        """
        # Placeholder - implement based on your RUA setup
        return []

    async def _get_recent_failures(self, tenant_id: str | None = None) -> list[dict]:
        """Get recent DMARC authentication failures."""
        query = (
            self.db.query(DMARCReport)
            .filter(DMARCReport.messages_failed > 0)
            .order_by(DMARCReport.report_date.desc())
            .limit(10)
        )

        if tenant_id:
            query = query.filter(DMARCReport.tenant_id == tenant_id)

        reports = query.all()

        return [
            {
                "domain": r.domain,
                "date": r.report_date.isoformat(),
                "failed": r.messages_failed,
                "total": r.messages_total,
                "failure_rate": round((r.messages_failed / r.messages_total * 100), 2)
                if r.messages_total > 0
                else 0,
            }
            for r in reports
        ]

    async def _get_active_alerts(self, tenant_id: str | None = None) -> list[dict]:
        """Get active DMARC/DKIM alerts."""
        query = (
            self.db.query(DMARCAlert)
            .filter(not DMARCAlert.is_acknowledged)
            .order_by(DMARCAlert.created_at.desc())
            .limit(10)
        )

        if tenant_id:
            query = query.filter(DMARCAlert.tenant_id == tenant_id)

        alerts = query.all()

        return [
            {
                "id": a.id,
                "type": a.alert_type,
                "severity": a.severity,
                "domain": a.domain,
                "message": a.message,
                "created_at": a.created_at.isoformat(),
            }
            for a in alerts
        ]

    def _calculate_tenant_security_score(
        self, dmarc_records: list[DMARCRecord], dkim_records: list[DKIMRecord]
    ) -> float:
        """Calculate tenant security score (0-100)."""
        if not dmarc_records and not dkim_records:
            return 0.0

        scores = []

        # DMARC scores (60% weight)
        if dmarc_records:
            dmarc_score = sum(r.policy_score for r in dmarc_records) / len(dmarc_records)
            scores.append(dmarc_score * 0.6)

        # DKIM scores (40% weight)
        if dkim_records:
            dkim_score = sum(
                100 if d.is_enabled and d.is_aligned else 50 if d.is_enabled else 0
                for d in dkim_records
            ) / len(dkim_records)
            scores.append(dkim_score * 0.4)

        return round(sum(scores), 2)

    def _parse_datetime(self, value: str | None) -> datetime | None:
        """Parse ISO datetime string."""
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except Exception:
            return None

    def _extract_dkim_selector(self, record: dict | None) -> str:
        """Extract DKIM selector from DNS record."""
        if not record:
            return "default"

        # Extract selector from TXT record name
        name = record.get("label", "")
        if "._domainkey." in name:
            return name.split("._domainkey.")[0]
        return "default"
