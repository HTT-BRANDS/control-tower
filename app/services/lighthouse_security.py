"""LighthouseSecurityMixin implementation for LighthouseAzureClient."""

import logging
from typing import Any

from app.services.lighthouse_support import lighthouse_module

logger = logging.getLogger(__name__)


class LighthouseSecurityMixin:
    async def get_security_assessments(
        self,
        subscription_id: str,
    ) -> dict[str, Any]:
        """Get security assessments for a delegated subscription.

        Retrieves security score and assessment results from Azure Security Center.

        Args:
            subscription_id: The delegated subscription ID

        Returns:
            Dictionary with security data:
            {
                "success": bool,
                "subscription_id": str,
                "secure_score": float | None,
                "max_score": float | None,
                "percentage": float,
                "assessments": list[dict],
                "recommendations_count": int,
                "error": str | None
            }

        Raises:
            LighthouseDelegationError: If delegation verification fails

        Example:
            security = await client.get_security_assessments("sub-123")
            print(f"Secure Score: {security['percentage']:.1f}%")
        """
        logger.debug(f"Retrieving security assessments for subscription: {subscription_id}")

        # Verify delegation first
        delegation_check = await self.verify_delegation(subscription_id)
        if not delegation_check["is_delegated"]:
            raise lighthouse_module().LighthouseDelegationError(
                subscription_id, delegation_check.get("error", "Delegation not verified")
            )

        try:
            security_data = await lighthouse_module().resilient_api_call(
                func=self._get_security_assessments_sync,
                api_name="security",
                max_retries=3,
                subscription_id=subscription_id,
            )

            logger.info(
                f"Retrieved security data for {subscription_id}: score={security_data.get('percentage', 0):.1f}%"
            )
            return security_data

        except Exception as e:
            logger.error(f"Failed to get security assessments for {subscription_id}: {e}")
            raise

    def _get_security_assessments_sync(self, subscription_id: str) -> dict[str, Any]:
        """Synchronous helper to get security assessments.

        Args:
            subscription_id: The Azure subscription ID

        Returns:
            Dictionary with security assessment data
        """
        # Security Center requires a location parameter
        asc_location = "centralus"
        client = lighthouse_module().SecurityCenter(self.credential, subscription_id, asc_location)

        assessments = []
        secure_score = None
        max_score = None
        percentage = 0.0

        try:
            # Get secure scores
            scores = list(client.secure_scores.list())
            if scores:
                score = scores[0]
                secure_score = float(score.score.current) if score.score else 0.0
                max_score = float(score.max) if hasattr(score, "max") else 100.0
                percentage = (secure_score / max_score * 100) if max_score > 0 else 0.0

        except Exception as e:
            logger.warning(f"Could not retrieve secure score: {e}")

        try:
            # Get security assessments
            for assessment in client.assessments.list():
                assessments.append(
                    {
                        "id": assessment.id,
                        "name": assessment.name,
                        "display_name": assessment.display_name,
                        "resource_details": assessment.resource_details,
                        "status": assessment.status.code if assessment.status else None,
                        "severity": assessment.status.severity if assessment.status else None,
                    }
                )

        except Exception as e:
            logger.warning(f"Could not retrieve all assessments: {e}")

        return {
            "success": True,
            "subscription_id": subscription_id,
            "secure_score": secure_score,
            "max_score": max_score,
            "percentage": percentage,
            "assessments": assessments,
            "recommendations_count": len(assessments),
            "error": None,
        }
