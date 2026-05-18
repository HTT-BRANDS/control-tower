# ct-90r.5 GitHub environment sprawl evidence - after

Captured: 2026-05-18T15:08:29Z

## Result
Deleted empty, unused GitHub environments:
- production-production
- production-staging
- staging-production
- staging-staging

Retained active/owned environments:
- development
- github-pages
- production
- production-backup
- staging

## Active OIDC federated credentials on GitHub OIDC service principal
Name                                            Subject                                                      Issuer
----------------------------------------------  -----------------------------------------------------------  -------------------------------------------
github-actions-control-tower-production-backup  repo:HTT-BRANDS/control-tower:environment:production-backup  https://token.actions.githubusercontent.com
github-actions-control-tower-pr                 repo:HTT-BRANDS/control-tower:pull_request                   https://token.actions.githubusercontent.com
github-actions-control-tower-main               repo:HTT-BRANDS/control-tower:ref:refs/heads/main            https://token.actions.githubusercontent.com
github-actions-control-tower-production         repo:HTT-BRANDS/control-tower:environment:production         https://token.actions.githubusercontent.com
github-actions-control-tower-staging            repo:HTT-BRANDS/control-tower:environment:staging            https://token.actions.githubusercontent.com

## Ghost OIDC subject query
[]

## Validation
- Target environments return absent via GitHub API.
- No active OIDC FIC subjects reference target names.
- Active workflow references use retained environments only.
