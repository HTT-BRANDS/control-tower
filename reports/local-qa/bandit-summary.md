# Bandit Summary

Command: `uvx bandit -r app -f json -o reports/local-qa/bandit-report.json`

Result after remediation:

- High severity findings: 0
- Medium severity findings: 5
- Low severity findings: 29

Remediation performed during `ct-432`:

- `app/core/cache/manager.py` cache-key MD5 was explicitly marked `usedforsecurity=False` because the digest is used only for non-security cache-key shortening, not cryptography or integrity.

Raw Bandit JSON was intentionally not committed because it includes source snippets and trips secret-keyword detection. This summary is the committed evidence artifact.
