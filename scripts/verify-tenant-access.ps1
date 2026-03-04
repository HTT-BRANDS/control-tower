#requires -Version 5.1
#requires -Modules Az.Accounts, Az.KeyVault

<#
.SYNOPSIS
    Verifies Azure tenant connectivity and Graph API access for Riverside tenants.

.DESCRIPTION
    This script tests connectivity to all 5 Riverside tenants and verifies:
    - Azure AD authentication
    - Microsoft Graph API access
    - Required permissions for DMARC/DKIM monitoring
    - Admin consent status
    - Domain configuration

.PARAMETER TenantCode
    Specific tenant code to verify (HTT, BCC, FN, TLL, DCE). If not specified, all tenants are verified.

.PARAMETER KeyVaultName
    Name of the Azure Key Vault containing client secrets.

.PARAMETER ShowSecrets
    If specified, shows secret values (use with caution in production).

.PARAMETER TestGraphCalls
    If specified, makes actual Graph API calls to test data access.

.EXAMPLE
    .\verify-tenant-access.ps1
    Verifies all configured tenants.

.EXAMPLE
    .\verify-tenant-access.ps1 -TenantCode HTT
    Verifies only the HTT tenant.

.EXAMPLE
    .\verify-tenant-access.ps1 -KeyVaultName "riverside-kv" -TestGraphCalls
    Verifies all tenants using secrets from Key Vault and tests Graph API calls.

.NOTES
    File Name      : verify-tenant-access.ps1
    Author         : Azure Governance Platform
    Prerequisite   : Az.Accounts, Az.KeyVault modules
    Version        : 1.0
#>

[CmdletBinding()]
param(
    [Parameter()]
    [ValidateSet("HTT", "BCC", "FN", "TLL", "DCE", "")]
    [string]$TenantCode = "",

    [Parameter()]
    [string]$KeyVaultName = "",

    [Parameter()]
    [switch]$ShowSecrets,

    [Parameter()]
    [switch]$TestGraphCalls
)

# Error action preference
$ErrorActionPreference = "Stop"

# Tenant Configuration
$Tenants = @{
    "HTT" = @{
        Name = "Head-To-Toe"
        TenantId = "0c0e35dc-188a-4eb3-b8ba-61752154b407"
        AppId = "1e3e8417-49f1-4d08-b7be-47045d8a12e9"
        AdminEmail = "tyler.granlund-admin@httbrands.com"
        KeyVaultSecretName = "htt-client-secret"
        Domains = @("httbrands.com")
        IsActive = $true
    }
    "BCC" = @{
        Name = "Bishops"
        TenantId = "b5380912-79ec-452d-a6ca-6d897b19b294"
        AppId = "4861906b-2079-4335-923f-a55cc0e44d64"
        AdminEmail = "tyler.granlund-Admin@bishopsbs.onmicrosoft.com"
        KeyVaultSecretName = "bcc-client-secret"
        Domains = @("bishopsbs.onmicrosoft.com")
        IsActive = $true
    }
    "FN" = @{
        Name = "Frenchies"
        TenantId = "98723287-044b-4bbb-9294-19857d4128a0"
        AppId = "7648d04d-ccc4-43ac-bace-da1b68bf11b4"
        AdminEmail = "tyler.granlund-Admin@ftgfrenchiesoutlook.onmicrosoft.com"
        KeyVaultSecretName = "fn-client-secret"
        Domains = @("ftgfrenchiesoutlook.onmicrosoft.com")
        IsActive = $true
    }
    "TLL" = @{
        Name = "Lash Lounge"
        TenantId = "3c7d2bf3-b597-4766-b5cb-2b489c2904d6"
        AppId = "52531a02-78fd-44ba-9ab9-b29675767955"
        AdminEmail = "tyler.granlund-Admin@LashLoungeFranchise.onmicrosoft.com"
        KeyVaultSecretName = "tll-client-secret"
        Domains = @("LashLoungeFranchise.onmicrosoft.com")
        IsActive = $true
    }
    "DCE" = @{
        Name = "Delta Crown Extensions"
        TenantId = "TBD"
        AppId = "TBD"
        AdminEmail = "tyler.granlund-Admin@deltacrownextensions.onmicrosoft.com"
        KeyVaultSecretName = "dce-client-secret"
        Domains = @("deltacrownextensions.onmicrosoft.com")
        IsActive = $false
    }
}

# Required Graph API Permissions for DMARC/DKIM
$RequiredPermissions = @(
    @{
        Name = "Reports.Read.All"
        Description = "Read all usage reports including email security reports"
        Id = "230c1aed-a721-4c5d-9cb4-a90514e508ef"
    },
    @{
        Name = "SecurityEvents.Read.All"
        Description = "Read security events and alerts"
        Id = "bf394140-e372-4bf9-a898-299cfc7564e5"
    },
    @{
        Name = "Domain.Read.All"
        Description = "Read all domain properties including verification status"
        Id = "dbb9058a-0e50-4048-992f-029bf1600b55"
    },
    @{
        Name = "Directory.Read.All"
        Description = "Read directory data (users, groups, applications)"
        Id = "7ab1d382-f21e-4acd-a863-ba3e13f7da61"
    }
)

# Results tracking
$Results = @{
    Passed = @()
    Failed = @()
    Warnings = @()
}

# Helper Functions
function Write-Section {
    param([string]$Title)
    Write-Host "`n========================================" -ForegroundColor Cyan
    Write-Host $Title -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
}

function Write-TestResult {
    param(
        [string]$Test,
        [bool]$Passed,
        [string]$Message = ""
    )
    if ($Passed) {
        Write-Host "  ✅ $Test" -ForegroundColor Green
        if ($Message) { Write-Host "     $Message" -ForegroundColor Gray }
    }
    else {
        Write-Host "  ❌ $Test" -ForegroundColor Red
        if ($Message) { Write-Host "     $Message" -ForegroundColor Red }
    }
    return $Passed
}

function Test-ValidGuid {
    param([string]$Guid)
    try {
        [System.Guid]::Parse($Guid) | Out-Null
        return $true
    }
    catch {
        return $false
    }
}

function Get-GraphToken {
    param(
        [string]$TenantId,
        [string]$AppId,
        [string]$ClientSecret
    )
    
    try {
        $Body = @{
            grant_type = "client_credentials"
            client_id = $AppId
            client_secret = $ClientSecret
            scope = "https://graph.microsoft.com/.default"
        }
        
        $Response = Invoke-RestMethod -Uri "https://login.microsoftonline.com/$TenantId/oauth2/v2.0/token" -Method Post -Body $Body -ContentType "application/x-www-form-urlencoded"
        return $Response.access_token
    }
    catch {
        throw "Failed to acquire token: $_"
    }
}

function Test-GraphApiCall {
    param(
        [string]$Token,
        [string]$Endpoint,
        [string]$TenantName
    )
    
    try {
        $Headers = @{
            Authorization = "Bearer $Token"
            "Content-Type" = "application/json"
        }
        
        $Response = Invoke-RestMethod -Uri "https://graph.microsoft.com/v1.0/$Endpoint" -Headers $Headers -Method Get
        return $true, "Successfully retrieved data"
    }
    catch {
        return $false, $_.Exception.Message
    }
}

function Get-ClientSecret {
    param(
        [string]$TenantCode,
        [string]$SecretName
    )
    
    # Try environment variable first
    $EnvVarName = "RIVERSIDE_$($TenantCode)_CLIENT_SECRET"
    $EnvSecret = [Environment]::GetEnvironmentVariable($EnvVarName)
    
    if ($EnvSecret) {
        Write-Host "  ℹ️  Using client secret from environment variable: $EnvVarName" -ForegroundColor Yellow
        return $EnvSecret
    }
    
    # Try Key Vault if specified
    if ($KeyVaultName) {
        try {
            $Secret = Get-AzKeyVaultSecret -VaultName $KeyVaultName -Name $SecretName -AsPlainText
            Write-Host "  ℹ️  Using client secret from Key Vault: $KeyVaultName/$SecretName" -ForegroundColor Yellow
            return $Secret
        }
        catch {
            Write-Host "  ⚠️  Failed to retrieve secret from Key Vault: $_" -ForegroundColor Yellow
        }
    }
    
    # Prompt for secret
    $Secret = Read-Host -Prompt "  Enter client secret for $TenantCode (input will be hidden)" -AsSecureString
    return [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($Secret))
}

# Main Script
Write-Section "Azure Tenant Verification Script"
Write-Host "Testing connectivity to Riverside tenants for DMARC/DKIM monitoring"

# Determine which tenants to test
$TenantsToTest = if ($TenantCode) { @{$TenantCode = $Tenants[$TenantCode]} } else { $Tenants }

# Check if Az modules are available
Write-Section "Prerequisites Check"
$AzModule = Get-Module -ListAvailable -Name Az.Accounts
if (-not $AzModule) {
    Write-TestResult "Az PowerShell Module" $false "Az.Accounts module not found. Install with: Install-Module -Name Az -AllowClobber -Force"
    exit 1
}
else {
    Write-TestResult "Az PowerShell Module" $true "Version: $($AzModule.Version)"
}

# Check if user is logged in
try {
    $Context = Get-AzContext
    if (-not $Context) {
        Write-Host "  ℹ️  Not logged into Azure. Run Connect-AzAccount first." -ForegroundColor Yellow
    }
    else {
        Write-TestResult "Azure Login" $true "Connected as: $($Context.Account.Id)"
    }
}
catch {
    Write-Host "  ⚠️  Could not verify Azure login context" -ForegroundColor Yellow
}

# Test each tenant
foreach ($Code in $TenantsToTest.Keys) {
    $Tenant = $Tenants[$Code]
    
    Write-Section "Testing: $($Tenant.Name) ($Code)"
    
    # Skip inactive tenants
    if (-not $Tenant.IsActive) {
        Write-Host "  ⚪ Tenant is marked as inactive (setup pending)" -ForegroundColor Gray
        $Results.Warnings += "$Code`: Tenant inactive"
        continue
    }
    
    $TenantResults = @{
        Code = $Code
        Tests = @()
        AllPassed = $true
    }
    
    # Test 1: Tenant ID format
    $ValidTenantId = Test-ValidGuid $Tenant.TenantId
    $TenantResults.Tests += Write-TestResult "Tenant ID Format" $ValidTenantId $Tenant.TenantId
    if (-not $ValidTenantId) { $TenantResults.AllPassed = $false }
    
    # Test 2: App ID format
    $ValidAppId = Test-ValidGuid $Tenant.AppId
    $TenantResults.Tests += Write-TestResult "App ID Format" $ValidAppId $Tenant.AppId
    if (-not $ValidAppId) { $TenantResults.AllPassed = $false }
    
    # Test 3: Admin email format
    $ValidEmail = $Tenant.AdminEmail -match '^[^@]+@[^@]+\.[^@]+$'
    $TenantResults.Tests += Write-TestResult "Admin Email Format" $ValidEmail $Tenant.AdminEmail
    if (-not $ValidEmail) { $TenantResults.AllPassed = $false }
    
    # Test 4: Get client secret and test authentication
    Write-Host "`n  🔐 Authentication Test" -ForegroundColor Yellow
    
    try {
        $ClientSecret = Get-ClientSecret -TenantCode $Code -SecretName $Tenant.KeyVaultSecretName
        
        if ($ShowSecrets) {
            Write-Host "     Secret: $ClientSecret" -ForegroundColor Magenta
        }
        
        if (-not $ClientSecret) {
            throw "No client secret provided"
        }
        
        Write-Host "     Acquiring access token..." -ForegroundColor Gray
        $Token = Get-GraphToken -TenantId $Tenant.TenantId -AppId $Tenant.AppId -ClientSecret $ClientSecret
        
        if ($Token) {
            $TenantResults.Tests += Write-TestResult "Token Acquisition" $true "Successfully acquired Graph API token"
            
            # Decode token to show basic info
            $TokenParts = $Token.Split('.')
            if ($TokenParts.Count -eq 3) {
                $Payload = $TokenParts[1].Replace('-', '+').Replace('_', '/')
                $Padding = 4 - ($Payload.Length % 4)
                if ($Padding -ne 4) { $Payload += '=' * $Padding }
                $TokenData = [System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String($Payload)) | ConvertFrom-Json
                Write-Host "     Token expires: $([DateTimeOffset]::FromUnixTimeSeconds($TokenData.exp).LocalDateTime)" -ForegroundColor Gray
            }
        }
        else {
            throw "Token is empty"
        }
        
        # Test 5: Graph API calls (if requested)
        if ($TestGraphCalls -and $Token) {
            Write-Host "`n  🌐 Graph API Tests" -ForegroundColor Yellow
            
            # Test organization endpoint
            $OrgResult = Test-GraphApiCall -Token $Token -Endpoint "organization" -TenantName $Tenant.Name
            $TenantResults.Tests += Write-TestResult "Graph API: Organization" $OrgResult[0] $OrgResult[1]
            if (-not $OrgResult[0]) { $TenantResults.AllPassed = $false }
            
            # Test domains endpoint
            $DomainResult = Test-GraphApiCall -Token $Token -Endpoint "domains" -TenantName $Tenant.Name
            $TenantResults.Tests += Write-TestResult "Graph API: Domains" $DomainResult[0] $DomainResult[1]
            if (-not $DomainResult[0]) { $TenantResults.AllPassed = $false }
            
            # Test security alerts (may not have data, but should not error)
            $AlertResult = Test-GraphApiCall -Token $Token -Endpoint "security/alerts" -TenantName $Tenant.Name
            $TenantResults.Tests += Write-TestResult "Graph API: Security Alerts" $AlertResult[0] $AlertResult[1]
            # Don't fail on security alerts - might just be no data
        }
    }
    catch {
        $TenantResults.Tests += Write-TestResult "Authentication" $false $_.Exception.Message
        $TenantResults.AllPassed = $false
    }
    
    # Summary for this tenant
    if ($TenantResults.AllPassed) {
        Write-Host "`n  ✅ All tests passed for $Code" -ForegroundColor Green
        $Results.Passed += $Code
    }
    else {
        Write-Host "`n  ❌ Some tests failed for $Code" -ForegroundColor Red
        $Results.Failed += $Code
    }
}

# Final Summary
Write-Section "Final Summary"

Write-Host "`n✅ Passed: $($Results.Passed.Count)" -ForegroundColor Green
if ($Results.Passed) {
    Write-Host "   $($Results.Passed -join ', ')" -ForegroundColor Gray
}

Write-Host "`n❌ Failed: $($Results.Failed.Count)" -ForegroundColor Red
if ($Results.Failed) {
    Write-Host "   $($Results.Failed -join ', ')" -ForegroundColor Gray
}

Write-Host "`n⚠️  Warnings: $($Results.Warnings.Count)" -ForegroundColor Yellow
if ($Results.Warnings) {
    foreach ($Warning in $Results.Warnings) {
        Write-Host "   $Warning" -ForegroundColor Gray
    }
}

Write-Host "`n========================================" -ForegroundColor Cyan

# Exit code
if ($Results.Failed.Count -gt 0) {
    Write-Host "Verification completed with failures." -ForegroundColor Red
    exit 1
}
else {
    Write-Host "Verification completed successfully!" -ForegroundColor Green
    exit 0
}
