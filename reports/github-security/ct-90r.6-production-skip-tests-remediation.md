# ct-90r.6 production skip_tests remediation evidence

Captured: 2026-05-18T15:06:34Z

## Result
Production deploy no longer exposes a normal `workflow_dispatch` input that can skip the QA gate. Playwright browser dependency installation and the full unit/integration suite now always run before production build/deploy.

Security scanning was already non-skippable and remains required via the `security-scan` job.

## Validation commands
- `rg -n "skip_tests" .github/workflows/deploy-production.yml` returns no matches.
- `actionlint .github/workflows/deploy-production.yml` passes.
- YAML assertion confirms `workflow_dispatch.inputs.skip_tests` is absent.
- `uv run pre-commit run --all-files` passes.

## Workflow dispatch inputs after remediation
```json
{
  "reason": {
    "description": "Deployment reason (shown in Teams notification)",
    "required": true,
    "type": "string"
  }
}
```

## Test gate snippets
```yaml
              tenant_id: "00000000-0000-0000-a000-000000000005"
              app_id: "00000000-0000-0000-b000-000000000005"
              admin_email: "admin@example.com"
              domains:
                - "example.com"
              is_active: true
              is_riverside: true
              priority: 5
              oidc_enabled: true
          EOF
          echo "Created config/tenants.yaml with OIDC enabled for all tenants"

      - name: Install Playwright browser dependencies
        run: uv run playwright install chromium --with-deps

      - name: Full test suite
        # ``-m 'not visual'`` deselects browser-required visual-parity
        # tests (see tests/integration/test_sync_status_dark_mode.py).
        # The dedicated ``browser-smoke`` job in ci.yml owns that surface;
        # the production deploy gate validates correctness, not pixels.
        run: uv run pytest tests/unit/ tests/integration/ -q --tb=short -m "not visual"
        env:
          ENVIRONMENT: development
          AZURE_TENANT_ID: ${{ secrets.AZURE_TENANT_ID }}
          AZURE_CLIENT_ID: ${{ secrets.AZURE_CLIENT_ID }}
          AZURE_CLIENT_SECRET: ci-shared-secret-placeholder  # pragma: allowlist secret

  # ===========================================================================
  # Job 2: Security Scan
  # ===========================================================================
  security-scan:
    name: Security Scan
    runs-on: ubuntu-latest
    needs: qa-gate
```
