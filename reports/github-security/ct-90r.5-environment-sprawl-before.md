# ct-90r.5 GitHub environment sprawl evidence - before

Captured: 2026-05-18T15:07:36Z

## Repository environments
{"created_at":"2026-03-05T06:51:45Z","deployment_branch_policy":null,"name":"development","protection_rules":[],"updated_at":"2026-03-05T06:51:45Z"}
{"created_at":"2026-04-01T14:59:26Z","deployment_branch_policy":{"custom_branch_policies":true,"protected_branches":false},"name":"github-pages","protection_rules":[{"id":51319710,"node_id":"GA_kwDORZyJE84DDxOe","type":"branch_policy"}],"updated_at":"2026-04-01T14:59:26Z"}
{"created_at":"2026-03-05T06:51:46Z","deployment_branch_policy":{"custom_branch_policies":true,"protected_branches":false},"name":"production","protection_rules":[{"id":53629102,"node_id":"GA_kwDORZyJE84DMlCu","prevent_self_review":false,"reviewers":[{"reviewer":{"avatar_url":"https://avatars.githubusercontent.com/u/195047338?v=4","events_url":"https://api.github.com/users/t-granlund/events{/privacy}","followers_url":"https://api.github.com/users/t-granlund/followers","following_url":"https://api.github.com/users/t-granlund/following{/other_user}","gists_url":"https://api.github.com/users/t-granlund/gists{/gist_id}","gravatar_id":"","html_url":"https://github.com/t-granlund","id":195047338,"login":"t-granlund","node_id":"U_kgDOC6Avqg","organizations_url":"https://api.github.com/users/t-granlund/orgs","received_events_url":"https://api.github.com/users/t-granlund/received_events","repos_url":"https://api.github.com/users/t-granlund/repos","site_admin":false,"starred_url":"https://api.github.com/users/t-granlund/starred{/owner}{/repo}","subscriptions_url":"https://api.github.com/users/t-granlund/subscriptions","type":"User","url":"https://api.github.com/users/t-granlund","user_view_type":"public"},"type":"User"},{"reviewer":{"avatar_url":"https://avatars.githubusercontent.com/u/209549562?v=4","events_url":"https://api.github.com/users/htt-db/events{/privacy}","followers_url":"https://api.github.com/users/htt-db/followers","following_url":"https://api.github.com/users/htt-db/following{/other_user}","gists_url":"https://api.github.com/users/htt-db/gists{/gist_id}","gravatar_id":"","html_url":"https://github.com/htt-db","id":209549562,"login":"htt-db","node_id":"U_kgDODH14-g","organizations_url":"https://api.github.com/users/htt-db/orgs","received_events_url":"https://api.github.com/users/htt-db/received_events","repos_url":"https://api.github.com/users/htt-db/repos","site_admin":false,"starred_url":"https://api.github.com/users/htt-db/starred{/owner}{/repo}","subscriptions_url":"https://api.github.com/users/htt-db/subscriptions","type":"User","url":"https://api.github.com/users/htt-db","user_view_type":"public"},"type":"User"}],"type":"required_reviewers"},{"id":53629103,"node_id":"GA_kwDORZyJE84DMlCv","type":"branch_policy"}],"updated_at":"2026-03-05T06:51:46Z"}
{"created_at":"2026-05-01T17:12:23Z","deployment_branch_policy":null,"name":"production-backup","protection_rules":[],"updated_at":"2026-05-01T17:12:23Z"}
{"created_at":"2026-04-15T21:26:34Z","deployment_branch_policy":null,"name":"production-production","protection_rules":[],"updated_at":"2026-04-15T21:26:34Z"}
{"created_at":"2026-03-31T16:07:58Z","deployment_branch_policy":null,"name":"production-staging","protection_rules":[],"updated_at":"2026-03-31T16:07:58Z"}
{"created_at":"2026-03-05T06:51:46Z","deployment_branch_policy":null,"name":"staging","protection_rules":[],"updated_at":"2026-03-05T06:51:46Z"}
{"created_at":"2026-04-15T21:26:35Z","deployment_branch_policy":null,"name":"staging-production","protection_rules":[],"updated_at":"2026-04-15T21:26:35Z"}
{"created_at":"2026-04-15T21:26:34Z","deployment_branch_policy":null,"name":"staging-staging","protection_rules":[],"updated_at":"2026-04-15T21:26:34Z"}

## Workflow environment references
.github/workflows/pages.yml:25:    environment:
.github/workflows/deploy-staging.yml:226:    environment: staging
.github/workflows/deploy-staging.yml:282:    environment:
.github/workflows/deploy-production.yml:264:    environment: production
.github/workflows/deploy-production.yml:389:    environment:
.github/workflows/backup.yml:21:      environment:
.github/workflows/backup.yml:45:    # repo:HTT-BRANDS/control-tower:environment:production-backup
.github/workflows/backup.yml:46:    environment: ${{ (github.event.inputs.environment || 'production') == 'production' && 'production-backup' || 'staging' }}
.github/workflows/backup.yml:85:            *) echo "Unsupported backup environment: $BACKUP_ENVIRONMENT" >&2; exit 1 ;;
.github/workflows/backup.yml:218:    environment: staging
.github/workflows/bacpac-export.yml:12:      environment:
.github/workflows/bacpac-export.yml:33:    environment: ${{ github.event.inputs.environment || 'production' }}
.github/workflows/bacpac-export.yml:71:              echo "Unsupported environment: $TARGET_ENV" >&2
.github/workflows/deploy-dev.yml:8:#   but no explicit GitHub environment:development federated credential. This
.github/workflows/deploy-dev.yml:9:#   workflow intentionally does NOT set `environment: development` until that

## Ghost-name repository search
docs/release-gate/ci-cd-oidc-remediation-evidence-2026-05-17.md:18:| Ghost GitHub environments | Confirmed: production-production, production-staging, staging-production, staging-staging | `ct-90r.5` |
docs/release-gate/ci-cd-oidc-remediation-evidence-2026-05-17.md:56:| environment-staging-production | repo:HTT-BRANDS/azure-governance-platform:environment:staging-production | https://token.actions.githubusercontent.com |
docs/release-gate/ci-cd-oidc-remediation-evidence-2026-05-17.md:57:| environment-staging-staging | repo:HTT-BRANDS/azure-governance-platform:environment:staging-staging | https://token.actions.githubusercontent.com |
docs/release-gate/ci-cd-oidc-remediation-evidence-2026-05-17.md:58:| environment-production-production | repo:HTT-BRANDS/azure-governance-platform:environment:production-production | https://token.actions.githubusercontent.com |
docs/release-gate/ci-cd-oidc-remediation-evidence-2026-05-17.md:59:| environment-production-staging | repo:HTT-BRANDS/azure-governance-platform:environment:production-staging | https://token.actions.githubusercontent.com |
docs/release-gate/ci-cd-oidc-remediation-evidence-2026-05-17.md:92:| production-production | yes | none |
docs/release-gate/ci-cd-oidc-remediation-evidence-2026-05-17.md:93:| production-staging | yes | none |
docs/release-gate/ci-cd-oidc-remediation-evidence-2026-05-17.md:95:| staging-production | yes | none |
docs/release-gate/ci-cd-oidc-remediation-evidence-2026-05-17.md:96:| staging-staging | yes | none |
docs/release-gate/ci-cd-oidc-remediation-evidence-2026-05-17.md:257:rg -n "skip_tests|azure/login|environment:|AZURE_CLIENT_ID|BCC_CLIENT_ID|FN_CLIENT_ID|TLL_CLIENT_ID|BCC_TENANT_ID|FN_TENANT_ID|TLL_TENANT_ID|production-production|production-staging|staging-production|staging-staging|production-backup|HTT-BRANDS/azure-governance-platform" .github app infrastructure scripts config docs control-tower
docs/release-gate/ci-cd-oidc-remediation-evidence-2026-05-17.md:265:control-tower/Ops/CI-CD/GitHub-Environments.md:22:| `production-production` | nothing | none | ❌ sprawl |
docs/release-gate/ci-cd-oidc-remediation-evidence-2026-05-17.md:266:control-tower/Ops/CI-CD/GitHub-Environments.md:23:| `production-staging` | nothing | none | ❌ sprawl |
docs/release-gate/ci-cd-oidc-remediation-evidence-2026-05-17.md:267:control-tower/Ops/CI-CD/GitHub-Environments.md:24:| `staging-production` | nothing | none | ❌ sprawl |
docs/release-gate/ci-cd-oidc-remediation-evidence-2026-05-17.md:268:control-tower/Ops/CI-CD/GitHub-Environments.md:25:| `staging-staging` | nothing | none | ❌ sprawl |
docs/release-gate/ci-cd-oidc-remediation-evidence-2026-05-17.md:294:control-tower/Ops/CI-CD/GitHub-OIDC-Federation.md:61:| 12 | `environment-staging-staging` | `repo:HTT-BRANDS/azure-governance-platform:environment:staging-staging` |
docs/release-gate/ci-cd-oidc-remediation-evidence-2026-05-17.md:295:control-tower/Ops/CI-CD/GitHub-OIDC-Federation.md:62:| 13 | `environment-staging-production` | `repo:HTT-BRANDS/azure-governance-platform:environment:staging-production` |
docs/release-gate/ci-cd-oidc-remediation-evidence-2026-05-17.md:296:control-tower/Ops/CI-CD/GitHub-OIDC-Federation.md:63:| 14 | `environment-production-staging` | `repo:HTT-BRANDS/azure-governance-platform:environment:production-staging` |
docs/release-gate/ci-cd-oidc-remediation-evidence-2026-05-17.md:297:control-tower/Ops/CI-CD/GitHub-OIDC-Federation.md:64:| 15 | `environment-production-production` | `repo:HTT-BRANDS/azure-governance-platform:environment:production-production` |
docs/release-gate/ci-cd-oidc-remediation-evidence-2026-05-17.md:300:control-tower/Ops/CI-CD/Findings-and-Drift.md:33:  environment-staging-staging
docs/release-gate/ci-cd-oidc-remediation-evidence-2026-05-17.md:301:control-tower/Ops/CI-CD/Findings-and-Drift.md:34:  environment-staging-production
docs/release-gate/ci-cd-oidc-remediation-evidence-2026-05-17.md:302:control-tower/Ops/CI-CD/Findings-and-Drift.md:35:  environment-production-staging
docs/release-gate/ci-cd-oidc-remediation-evidence-2026-05-17.md:303:control-tower/Ops/CI-CD/Findings-and-Drift.md:36:  environment-production-production
docs/release-gate/ci-cd-oidc-remediation-evidence-2026-05-17.md:307:control-tower/Ops/CI-CD/Findings-and-Drift.md:120:`production-production`, `production-staging`, `staging-production`, `staging-staging` aren't referenced by any current workflow.
docs/release-gate/ci-cd-oidc-remediation-evidence-2026-05-17.md:308:control-tower/Ops/CI-CD/Findings-and-Drift.md:126:for env in production-production production-staging staging-production staging-staging; do
docs/release-gate/ci-cd-oidc-remediation-evidence-2026-05-17.md:351:control-tower/Ops/CI-CD/Overview.md:47:4. **4 ghost GitHub environments** (`production-production`, `production-staging`, `staging-production`, `staging-staging`) — not used by any current workflow.
