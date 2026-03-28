# Azure SDK Coverage by Language

**Source**: https://azure.github.io/azure-sdk/releases/latest/
**Date**: Last updated March 2026
**Authority**: Official Microsoft Azure SDK team

## SDK Languages Supported
.NET, Java, JavaScript/TypeScript, Python, Go, C++, Rust, Embedded C, Android, iOS

## Management Libraries Required by This Platform

The governance platform uses these Azure management SDKs:

### Python (Current — all stable)
```
azure-identity>=1.15.0          ✅ Stable
azure-mgmt-resource>=23.0.0    ✅ Stable
azure-mgmt-costmanagement>=4.0 ✅ Stable
azure-mgmt-policyinsights>=1.0 ✅ Stable
azure-mgmt-security>=5.0.0     ✅ Stable
azure-mgmt-authorization>=4.0  ✅ Stable
azure-mgmt-subscription>=3.1.1 ✅ Stable
azure-keyvault-secrets>=4.7.0  ✅ Stable
```

### .NET Equivalents
```
Azure.Identity                          ✅ Stable
Azure.ResourceManager                   ✅ Stable
Azure.ResourceManager.CostManagement    ✅ Stable
Azure.ResourceManager.PolicyInsights    ✅ Stable
Azure.ResourceManager.SecurityCenter    ✅ Stable
Azure.ResourceManager.Authorization     ✅ Stable
Azure.ResourceManager.Subscription      ✅ Stable (via Resources)
Azure.Security.KeyVault.Secrets         ✅ Stable
```

### Go Equivalents
```
azidentity                              ✅ Stable (module 1.x)
armresources                            ✅ Stable
armcostmanagement                       ❌ NOT AVAILABLE
armpolicyinsights                       ❌ NOT AVAILABLE
armsecurity                             ❌ NOT AVAILABLE
armauthorization                        ✅ Stable
armsubscriptions                        ✅ Stable
azkeys / azsecrets                      ✅ Stable
```
**3 of 8 critical libraries are missing for Go.**

### Rust Equivalents
```
azure_core                              ⚠️ Beta 0.33.0
azure_identity                          ⚠️ Beta (via azure_core)
azure-mgmt-*                            ❌ NONE AVAILABLE
azure_data_cosmos                       ⚠️ Beta 0.31.0
azure_security_keyvault                 ⚠️ Beta (partial)
```
**Zero management libraries available for Rust. All core libraries are beta.**

### JavaScript/TypeScript Equivalents
```
@azure/identity                         ✅ Stable
@azure/arm-resources                    ✅ Stable
@azure/arm-costmanagement               ✅ Stable
@azure/arm-policy                       ✅ Stable
@azure/arm-security                     ✅ Stable
@azure/arm-authorization                ✅ Stable
@azure/arm-subscriptions                ✅ Stable
@azure/keyvault-secrets                 ✅ Stable
```

## Coverage Summary

| Language | Management Libs Available | Critical Libs Missing | Production Ready |
|----------|--------------------------|----------------------|-----------------|
| **.NET** | ~200+ | 0 | ✅ Yes — Best coverage |
| **Python** | ~180+ | 0 | ✅ Yes — Second best |
| **JavaScript** | ~160+ | 0 | ✅ Yes — Complete |
| **Java** | ~150+ | 0 | ✅ Yes — Complete |
| **Go** | ~100+ | 3 critical | ⚠️ Partial — Gaps in governance |
| **Rust** | 0 | All | ❌ No — Not production ready |

## Key Observation

For **Azure governance tooling specifically**, only Python, .NET, JavaScript, and Java have complete SDK coverage. Go is missing the exact libraries needed for cost management and compliance monitoring — the core function of this platform.
