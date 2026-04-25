# arbiter/ — Release-Gate Arbiter Policies

Machine-readable policies consumed by the release-gate arbiter and
executable-mirrored in GitHub Actions workflows.

## Layout

```
arbiter/
├── README.md                 ← you are here
└── policies/
    └── verify.yaml           ← production attestation verification policy
```

## `policies/verify.yaml` — supply-chain verification

Defines the release-critical claims every production image attestation
must satisfy before `deploy-production.yml`'s deploy job will run
`az webapp config container set`:

1. **Subject** — immutable `sha256:...` digest (never a tag)
2. **Predicate type** — both SLSA v1 provenance AND SPDX SBOM required
3. **Signer workflow** — exact workflow path
4. **Source ref** — current deploy ref, limited to `main` / `release/*`
5. **OIDC issuer** — Sigstore Fulcio for GitHub Actions

The policy is the source-of-truth. The workflow steps named under
`spec.enforcement.applies_to.gate_steps` are the executable mirror. If
these two drift apart, the arbiter pre-flight check should fail before
any release submission.

### Why YAML (not JSON)?

Human auditors read this during release-gate reviews. Comments are load-
bearing, so YAML wins over JSON.

### Lifecycle

| Event | Expected action |
|---|---|
| New predicate type added to workflow | Update `spec.claims.predicate_type.required` |
| Deploy gate moved to a different workflow | Update `spec.enforcement.applies_to.workflow` and `spec.claims.certificate_identity.value` |
| Branches/refs allowed to produce prod attestations change | Update `spec.claims.source_ref.allowed_patterns` |
| Verification tool changed (e.g. cosign → GitHub CLI) | Update `spec.enforcement.verification_method`, `spec.enforcement.verification_tool`, and mirrored claim language |
| actions/attest-* major version bump | Update `produced_by` fields + validate claim compatibility |

## Filing new policies

New policy kinds land here as siblings to `verify.yaml`. Suggested kinds:

- `RolloutPolicy` — canary / blast-radius rules
- `RollbackPolicy` — SLA, rehearsal cadence, approval chain
- `SBOMPolicy` — allowed licenses, disallowed components

Each new policy MUST:

1. Be YAML with top-of-file explanation comment
2. Include `apiVersion`, `kind`, `metadata.bd_ticket`
3. Reference the workflow(s) that mirror it under `spec.enforcement`
4. Be linked from this README

## See also

- `.github/workflows/deploy-production.yml` — executable mirror of `verify.yaml`
- `docs/release-gate/verdicts/` — archived arbiter verdict records
- `bd show 7mk8` — origin ticket
