"""Abstract base class for preflight checks.

Provides async support for checks with result caching capability.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Any

from app.preflight.models import (
    CheckCategory,
    CheckResult,
    CheckStatus,
)

logger = logging.getLogger(__name__)


class CheckCache:
    """Simple in-memory cache for check results."""

    def __init__(self, ttl_seconds: int = 300):
        self._cache: dict[str, tuple[CheckResult, datetime]] = {}
        self._ttl = ttl_seconds

    def get(self, check_id: str) -> CheckResult | None:
        """Get cached result if available and not expired."""
        if check_id in self._cache:
            result, cached_at = self._cache[check_id]
            if datetime.utcnow() - cached_at < timedelta(seconds=self._ttl):
                logger.debug(f"Cache hit for check: {check_id}")
                return result
            else:
                del self._cache[check_id]
                logger.debug(f"Cache expired for check: {check_id}")
        return None

    def set(self, check_id: str, result: CheckResult) -> None:
        """Cache a check result."""
        self._cache[check_id] = (result, datetime.utcnow())
        logger.debug(f"Cached result for check: {check_id}")

    def invalidate(self, check_id: str | None = None) -> None:
        """Invalidate cache for a specific check or all checks."""
        if check_id:
            self._cache.pop(check_id, None)
        else:
            self._cache.clear()

    def get_stats(self) -> dict[str, int]:
        """Get cache statistics."""
        return {
            "total_cached": len(self._cache),
            "ttl_seconds": self._ttl,
        }


class BasePreflightCheck(ABC):
    """Abstract base class for all preflight checks.

    Subclasses must implement the `_execute_check` method to define
    the actual check logic.
    """

    # Class-level cache shared across all check instances
    _cache = CheckCache(ttl_seconds=300)

    def __init__(
        self,
        check_id: str,
        name: str,
        category: CheckCategory,
        description: str = "",
        timeout_seconds: float = 30.0,
        use_cache: bool = True,
    ):
        """Initialize a preflight check.

        Args:
            check_id: Unique identifier for this check
            name: Human-readable name
            category: Category this check belongs to
            description: Detailed description of what this check verifies
            timeout_seconds: Timeout for check execution
            use_cache: Whether to cache results between runs
        """
        self.check_id = check_id
        self.name = name
        self.category = category
        self.description = description
        self.timeout_seconds = timeout_seconds
        self.use_cache = use_cache

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}({self.check_id}, {self.category})>"

    async def run(self, tenant_id: str | None = None, force: bool = False) -> CheckResult:
        """Run the preflight check with caching support.

        Args:
            tenant_id: Optional tenant ID for tenant-specific checks
            force: If True, bypass cache and execute the check

        Returns:
            CheckResult with the check outcome
        """
        cache_key = f"{self.check_id}:{tenant_id or 'global'}"

        # Check cache unless forced
        if self.use_cache and not force:
            cached = self._cache.get(cache_key)
            if cached:
                # Return a fresh timestamp but cached content
                cached.timestamp = datetime.utcnow()
                return cached

        # Return running status while executing
        CheckResult(
            check_id=self.check_id,
            name=self.name,
            category=self.category,
            status=CheckStatus.RUNNING,
            message="Check is executing...",
            tenant_id=tenant_id,
        )

        try:
            # Execute the check with timeout
            result = await asyncio.wait_for(
                self._execute_check(tenant_id),
                timeout=self.timeout_seconds,
            )

            # Update cache
            if self.use_cache:
                self._cache.set(cache_key, result)

            logger.info(
                f"Check {self.check_id} completed: {result.status.value} "
                f"({result.duration_ms:.2f}ms)"
            )
            return result

        except TimeoutError:
            logger.warning(f"Check {self.check_id} timed out after {self.timeout_seconds}s")
            return CheckResult(
                check_id=self.check_id,
                name=self.name,
                category=self.category,
                status=CheckStatus.FAIL,
                message=f"Check timed out after {self.timeout_seconds} seconds",
                details={"timeout": self.timeout_seconds},
                recommendations=[
                    "Check the Azure API response times",
                    "Consider increasing the timeout value",
                    "Verify network connectivity to Azure services",
                ],
                tenant_id=tenant_id,
            )

        except Exception as e:
            logger.error(f"Check {self.check_id} failed with exception: {e}")
            return CheckResult(
                check_id=self.check_id,
                name=self.name,
                category=self.category,
                status=CheckStatus.FAIL,
                message=str(e),
                details=self._sanitize_error_details(e),
                recommendations=self._get_recommendations(e),
                tenant_id=tenant_id,
            )

    @abstractmethod
    async def _execute_check(self, tenant_id: str | None = None) -> CheckResult:
        """Execute the actual check logic.

        Subclasses must implement this method to define the check logic.

        Args:
            tenant_id: Optional tenant ID for tenant-specific checks

        Returns:
            CheckResult with the check outcome
        """
        pass

    def _sanitize_error_details(self, error: Exception) -> dict[str, Any]:
        """Sanitize error details to avoid exposing sensitive information.

        Args:
            error: The exception that occurred

        Returns:
            Sanitized dictionary of error details
        """
        error_details = {"error_type": type(error).__name__}

        # Get error message but redact potential secrets
        error_msg = str(error)
        # Common patterns that might contain secrets
        sensitive_patterns = [
            "password",
            "secret",
            "token",
            "key",
            "credential",
            "connectionstring",
        ]

        for pattern in sensitive_patterns:
            if pattern.lower() in error_msg.lower():
                # Redact the sensitive information
                error_msg = f"[Redacted {pattern} found in error message]"
                break

        error_details["message"] = error_msg

        return error_details

    def _get_recommendations(self, error: Exception) -> list[str]:
        """Generate recommendations based on the error type.

        Args:
            error: The exception that occurred

        Returns:
            List of recommendation strings
        """
        error_msg = str(error).lower()

        recommendations = []

        # Authentication-related errors
        if any(term in error_msg for term in ["authentication", "unauthorized", "401", "auth"]):
            recommendations.extend(
                [
                    "Verify Azure credentials are correctly configured",
                    "Check that the service principal has required permissions",
                    "Ensure tenant ID is correct",
                ]
            )

        # Permission-related errors
        if any(term in error_msg for term in ["forbidden", "403", "permission", "access"]):
            recommendations.extend(
                [
                    "Verify the service principal has the necessary role assignments",
                    "Check Azure RBAC permissions for the target scope",
                    "Confirm the user has Graph API permissions",
                ]
            )

        # Resource not found
        if any(term in error_msg for term in ["not found", "404", "does not exist"]):
            recommendations.extend(
                [
                    "Verify the resource exists in the Azure tenant",
                    "Check that the subscription is still active",
                    "Ensure the tenant is properly registered",
                ]
            )

        # Rate limiting
        if any(term in error_msg for term in ["rate", "429", "throttle"]):
            recommendations.extend(
                [
                    "Azure API rate limit hit - wait before retrying",
                    "Consider implementing exponential backoff",
                    "Check if too many parallel requests are being made",
                ]
            )

        # Network errors
        if any(term in error_msg for term in ["connection", "timeout", "network", "dns", "ssl"]):
            recommendations.extend(
                [
                    "Check network connectivity to Azure",
                    "Verify firewall rules allow outbound HTTPS",
                    "Check proxy configuration if applicable",
                ]
            )

        # Generic fallback
        if not recommendations:
            recommendations.append("Check Azure service status and try again later")

        return recommendations

    @classmethod
    def clear_cache(cls, check_id: str | None = None) -> None:
        """Clear the cache for this check or all checks."""
        cls._cache.invalidate(check_id)

    def get_cache_stats(self) -> dict[str, Any]:
        """Get statistics about cache usage."""
        return self._cache.get_stats()

    @property
    def default_recommendations(self) -> list[str]:
        """Get default recommendations for this check.

        Can be overridden by subclasses for custom recommendations.
        """
        return [
            "Review Azure portal for the specific service status",
            "Check service principal permissions",
            "Verify tenant configuration in settings",
        ]
