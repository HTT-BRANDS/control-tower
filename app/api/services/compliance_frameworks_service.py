"""Compliance frameworks service — regulatory framework mapping (CM-003).

Loads SOC2 and NIST CSF framework definitions from a static YAML file at
startup, caches them in memory, and exposes read-only lookup methods.

Security requirements (ADR-0006):
- yaml.safe_load() ONLY — yaml.load() enables RCE via !!python/object tags
- File size limit (512 KB) enforced before parsing — prevents anchor bomb DoS
- SHA-256 content hash logged at startup for audit trail
"""

from __future__ import annotations

import hashlib
import logging
from functools import cached_property
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

# Hard limit before parsing — guards against YAML anchor/alias bombs
_MAX_YAML_SIZE_BYTES: int = 512_000  # 512 KB

# Default path relative to project root
_DEFAULT_YAML_PATH = Path("config/compliance_frameworks.yaml")


def _load_frameworks_yaml(path: Path) -> dict[str, Any]:
    """Load and validate the compliance frameworks YAML file.

    Security guards (ADR-0006):
    - File size limited to 512 KB before parsing
    - Must use yaml.safe_load() — yaml.load() is prohibited (RCE risk)
    - SHA-256 content hash logged for audit trail

    Args:
        path: Absolute or relative path to the YAML file.

    Returns:
        Parsed YAML data as a dict.

    Raises:
        FileNotFoundError: If the YAML file does not exist.
        ValueError: If the file exceeds 512 KB or has invalid structure.
    """
    if not path.exists():
        raise FileNotFoundError(f"compliance_frameworks.yaml not found at: {path.resolve()}")

    content: bytes = path.read_bytes()

    # Guard: file size limit prevents anchor bomb DoS (checked BEFORE parsing)
    if len(content) > _MAX_YAML_SIZE_BYTES:
        raise ValueError(
            f"compliance_frameworks.yaml exceeds 512KB limit: {len(content)} bytes. "
            "Reduce file size or raise the limit with Security Auditor approval."
        )

    # Audit: log content hash for SOC2 evidence trail
    file_hash = hashlib.sha256(content).hexdigest()
    logger.info(
        "Loading compliance frameworks YAML: path=%s size=%d sha256=%s",
        path,
        len(content),
        file_hash,
    )

    # SECURITY: yaml.safe_load() ONLY — never yaml.load(), yaml.full_load(), or yaml.unsafe_load()
    data: Any = yaml.safe_load(content)

    if not isinstance(data, dict):
        raise ValueError(
            "compliance_frameworks.yaml must be a YAML mapping at root level, "
            f"got {type(data).__name__}."
        )

    if "frameworks" not in data:
        raise ValueError("compliance_frameworks.yaml must have a 'frameworks' root key.")

    logger.info(
        "Compliance frameworks loaded successfully: %d frameworks, sha256=%s",
        len(data.get("frameworks", {})),
        file_hash,
    )
    return data


class ComplianceFrameworksService:
    """Read-only service for regulatory framework definitions.

    Loads config/compliance_frameworks.yaml once at construction and caches
    the data in memory.  All methods are O(1) or O(k) where k is the number
    of tags/controls — no file I/O per request.

    Usage:
        # Module-level singleton (loaded at import time):
        _service = ComplianceFrameworksService()

        # Or with a custom path (useful in tests):
        svc = ComplianceFrameworksService(yaml_path=Path("tests/fixtures/fw.yaml"))
    """

    def __init__(self, yaml_path: Path | None = None) -> None:
        self._yaml_path: Path = yaml_path or _DEFAULT_YAML_PATH
        self._raw: dict[str, Any] = _load_frameworks_yaml(self._yaml_path)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @cached_property
    def _frameworks(self) -> dict[str, dict[str, Any]]:
        """Raw frameworks dict from YAML, keyed by framework_id."""
        return self._raw.get("frameworks", {})

    @cached_property
    def _all_control_ids(self) -> set[str]:
        """Set of all fully-qualified control tags: ``{framework_id}.{control_id}``."""
        ids: set[str] = set()
        for fw_id, fw in self._frameworks.items():
            for ctrl_id in fw.get("controls", {}):
                ids.add(f"{fw_id}.{ctrl_id}")
        return ids

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_all_frameworks(self) -> list[dict[str, Any]]:
        """Return a summary list of all loaded frameworks.

        Returns:
            List of dicts with keys: id, name, version, authority, control_count.

        Example::

            [
                {"id": "SOC2_2017", "name": "SOC 2 Trust Services Criteria",
                 "version": "2017 (Revised Points of Focus 2022)",
                 "authority": "AICPA", "control_count": 36},
                ...
            ]
        """
        result: list[dict[str, Any]] = []
        for fw_id, fw in self._frameworks.items():
            result.append(
                {
                    "id": fw_id,
                    "name": fw.get("name", fw_id),
                    "version": fw.get("version", ""),
                    "authority": fw.get("authority", ""),
                    "control_count": len(fw.get("controls", {})),
                }
            )
        return result

    def get_framework(self, framework_id: str) -> dict[str, Any]:
        """Return full framework detail including all controls.

        Args:
            framework_id: e.g. ``"SOC2_2017"`` or ``"NIST_CSF_2.0"``.

        Returns:
            Dict with framework metadata and a ``controls`` mapping.

        Raises:
            KeyError: If *framework_id* is not in the loaded YAML.
        """
        if framework_id not in self._frameworks:
            raise KeyError(
                f"Framework '{framework_id}' not found. Available: {sorted(self._frameworks)}"
            )
        fw = dict(self._frameworks[framework_id])
        fw["id"] = framework_id
        fw["control_count"] = len(fw.get("controls", {}))
        return fw

    def get_control(self, framework_id: str, control_id: str) -> dict[str, Any]:
        """Return a single control's detail.

        Args:
            framework_id: e.g. ``"SOC2_2017"``.
            control_id: e.g. ``"CC6.1"`` or ``"PR.DS-01"``.

        Returns:
            Control detail dict with an added ``id`` key.

        Raises:
            KeyError: If *framework_id* or *control_id* is not found.
        """
        fw = self.get_framework(framework_id)
        controls: dict[str, Any] = fw.get("controls", {})
        if control_id not in controls:
            raise KeyError(
                f"Control '{control_id}' not found in framework '{framework_id}'. "
                f"Available: {sorted(controls)}"
            )
        control = dict(controls[control_id])
        control["id"] = control_id
        control["framework_id"] = framework_id
        return control

    def map_tags_to_controls(self, tags: list[str]) -> dict[str, list[dict[str, Any]]]:
        """Resolve a list of compliance tags to their control definitions.

        Tag format: ``{framework_id}.{control_id}``
        Example: ``["SOC2_2017.CC6.1", "NIST_CSF_2.0.PR.DS-01"]``

        Unknown or malformed tags are silently skipped (graceful degradation)
        so that a single bad tag never blocks the entire response.

        Args:
            tags: List of fully-qualified control tag strings.

        Returns:
            Dict keyed by framework_id, each value a list of matched control
            dicts.  Frameworks with no matches are omitted.

        Example::

            {
                "SOC2_2017": [{"id": "CC6.1", "name": "...", ...}],
                "NIST_CSF_2.0": [{"id": "PR.DS-01", "name": "...", ...}],
            }
        """
        result: dict[str, list[dict[str, Any]]] = {}

        for tag in tags:
            # Resolve framework_id by matching against known framework IDs.
            # We can't simply split on the first "." because framework IDs like
            # "NIST_CSF_2.0" contain dots themselves.
            fw_id: str | None = None
            control_id: str | None = None

            for candidate_fw_id in self._frameworks:
                prefix = f"{candidate_fw_id}."
                if tag.startswith(prefix):
                    fw_id = candidate_fw_id
                    control_id = tag[len(prefix) :]
                    break

            if fw_id is None or control_id is None:
                logger.debug("map_tags_to_controls: unrecognised tag '%s' — skipping", tag)
                continue

            try:
                ctrl = self.get_control(fw_id, control_id)
            except KeyError:
                logger.debug(
                    "map_tags_to_controls: control '%s' not found in framework '%s' — skipping",
                    control_id,
                    fw_id,
                )
                continue

            result.setdefault(fw_id, []).append(ctrl)

        return result

    def get_frameworks_for_rule(self, rule_tags: list[str]) -> dict[str, list[dict[str, Any]]]:
        """Convenience method: resolve a CustomComplianceRule's compliance_tags.

        Equivalent to :meth:`map_tags_to_controls` — provided as a named
        alias to make call-site intent explicit when working with rule objects.

        Args:
            rule_tags: The ``compliance_tags`` list from a
                ``CustomComplianceRule`` instance.

        Returns:
            Same structure as :meth:`map_tags_to_controls`.
        """
        return self.map_tags_to_controls(rule_tags)

    def is_valid_tag(self, tag: str) -> bool:
        """Check whether *tag* refers to a known framework control.

        Useful for validating ``compliance_tags`` at API write time (ADR-0006
        FF-3: fabricated tags must be rejected).

        Args:
            tag: A fully-qualified control tag string.

        Returns:
            ``True`` if the tag resolves to a known control, ``False``
            otherwise.
        """
        return tag in self._all_control_ids


# ---------------------------------------------------------------------------
# Module-level singleton — loaded once at import time, cached for the lifetime
# of the process.  Import this from route handlers and other services.
# ---------------------------------------------------------------------------
try:
    compliance_frameworks_service = ComplianceFrameworksService()
except Exception as _e:
    logger.warning(
        "ComplianceFrameworksService failed to initialise at import time: %s. "
        "The service will be unavailable until the YAML is fixed.",
        _e,
    )
    compliance_frameworks_service = None  # type: ignore[assignment]
