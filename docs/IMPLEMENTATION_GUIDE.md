# Azure Multi-Tenant Governance Platform
# Complete Implementation Guide

> **Document Version:** 1.0  
> **Last Updated:** February 2025  
> **Audience:** Cloud administrators, IT professionals, developers  
> **Estimated Time:** 4-8 hours for full setup

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Prerequisites Checklist](#2-prerequisites-checklist)
3. [Understanding the Architecture](#3-understanding-the-architecture)
4. [Phase 1: Azure Tenant Preparation](#4-phase-1-azure-tenant-preparation)
5. [Phase 2: Local Development Setup](#5-phase-2-local-development-setup)
6. [Phase 3: Configuration](#6-phase-3-configuration)
7. [Phase 4: Testing & Validation](#7-phase-4-testing--validation)
8. [Phase 5: Deployment](#8-phase-5-deployment)
9. [Troubleshooting Guide](#9-troubleshooting-guide)
10. [Security Considerations](#10-security-considerations)
11. [Maintenance & Operations](#11-maintenance--operations)
12. [Glossary](#12-glossary)
13. [Appendix](#13-appendix)

---

## 1. Executive Summary

### What This Platform Does

This platform provides a **single dashboard** to monitor and manage **4 Azure/M365 tenants** from one place. Instead of logging into each tenant separately, you get:

- **Cost visibility**: See spending across all tenants, detect anomalies
- **Compliance monitoring**: Track policy compliance and security scores
- **Resource inventory**: Know what resources exist and find waste
- **Identity governance**: Monitor privileged users, guest accounts, MFA status

### Why This Matters

| Without This Platform | With This Platform |
|----------------------|--------------------|
| Log into 4 Azure portals separately | One dashboard for everything |
| Manually export cost reports | Automated cost aggregation |
| Miss compliance drift | Real-time compliance alerts |
| Unknown orphaned resources | Automatic waste detection |
| Scattered identity information | Unified privileged access view |

### Cost to Run

| Component | Monthly Cost |
|-----------|-------------|
| Azure App Service (B1) | ~$13 |
| Azure Key Vault | ~$1-2 |
| **Total** | **~$15-20/month** |

---

## 2. Prerequisites Checklist

### 2.1 Required Access & Permissions

> ⚠️ **CRITICAL**: You MUST have these permissions before starting. Without them, you will get stuck.

| Requirement | Why It's Needed | How to Verify |
|-------------|-----------------|---------------|
| **Global Administrator** or **Application Administrator** role in each of the 4 tenants | To create App Registrations and grant API permissions | Azure Portal → Azure AD → Roles and administrators → Search your name |
| **Owner** or **User Access Administrator** on Azure subscriptions | To assign RBAC roles to the app | Azure Portal → Subscriptions → Access control (IAM) |
| Ability to **consent to API permissions** | Some Graph API permissions require admin consent | Check with your Azure AD admin if unsure |

> 💡 **TIP**: If you don't have Global Admin, you'll need to work with someone who does. Prepare a list of what you need (covered in Section 4) and schedule time with them.

### 2.2 Required Software (Your Computer)

| Software | Version | Download Link | Verification Command |
|----------|---------|---------------|---------------------|
| **Python** | 3.11 or higher | Pre-installed on Mac; Windows: python.org | `python3 --version` |
| **Git** | Any recent version | Pre-installed on Mac; Windows: git-scm.com | `git --version` |
| **uv** (Python package manager) | Latest | `curl -LsSf https://astral.sh/uv/install.sh \| sh` | `uv --version` |
| **Azure CLI** | Latest | `brew install azure-cli` (Mac) | `az --version` |
| **Text Editor** | VS Code recommended | code.visualstudio.com | N/A |

> ⚠️ **WALMART NETWORK NOTE**: If installing via Homebrew fails, try:
> ```bash
> HTTP_PROXY=http://sysproxy.wal-mart.com:8080 HTTPS_PROXY=http://sysproxy.wal-mart.com:8080 brew install azure-cli
> ```

### 2.3 Information You Need to Gather

Before starting, collect this information for **each of your 4 tenants**:

| Information | Where to Find It | Tenant 1 | Tenant 2 | Tenant 3 | Tenant 4 |
|-------------|------------------|----------|----------|----------|----------|
| **Tenant ID** (GUID) | Azure Portal → Azure AD → Overview | __________ | __________ | __________ | __________ |
| **Tenant Name** | Azure Portal → Azure AD → Overview | __________ | __________ | __________ | __________ |
| **Subscription IDs** | Azure Portal → Subscriptions | __________ | __________ | __________ | __________ |
| **Primary Contact** | Your records | __________ | __________ | __________ | __________ |

> 💡 **TIP**: Create a secure document (not plain text!) to store this information. You'll reference it throughout setup.

### 2.4 Decision Point: Authentication Method

You have **two options** for how the platform authenticates to your tenants:

| Option | Best For | Pros | Cons |
|--------|----------|------|------|
| **A: Azure Lighthouse** | Organizations with centralized IT | Single app registration, delegated access, no secrets per tenant | More complex initial setup, requires ARM templates |
| **B: Per-Tenant App Registrations** | Decentralized orgs, simpler setup | Straightforward, each tenant independent | 4 app registrations to manage, 4 secrets to rotate |

> 📋 **RECOMMENDATION**: For your first implementation, use **Option B (Per-Tenant App Registrations)**. It's simpler to understand and troubleshoot. You can migrate to Lighthouse later.

---

## 3. Understanding the Architecture

### 3.1 How It Works (Simple Explanation)

```
┌─────────────────────────────────────────────────────────────────┐
│                         YOUR COMPUTER                            │
│                    (or Azure App Service)                        │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │              GOVERNANCE PLATFORM                             ││
│  │                                                              ││
│  │   1. Background jobs run every few hours                     ││
│  │   2. They call Azure APIs for each tenant                    ││
│  │   3. Data is stored in a local database                      ││
│  │   4. You view dashboards in your web browser                 ││
│  │                                                              ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
                              │
          Authenticates using App Registrations
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
   ┌─────────┐          ┌─────────┐           ┌─────────┐
   │Tenant A │          │Tenant B │           │Tenant C │ ... etc
   │  Azure  │          │  Azure  │           │  Azure  │
   └─────────┘          └─────────┘           └─────────┘
```

### 3.2 What Data Is Collected

| Data Type | Source API | Refresh Frequency | Storage |
|-----------|-----------|-------------------|----------|
| Cost data | Azure Cost Management API | Every 24 hours | Local SQLite database |
| Compliance | Azure Policy Insights API | Every 4 hours | Local SQLite database |
| Resources | Azure Resource Manager API | Every 1 hour | Local SQLite database |
| Identity | Microsoft Graph API | Every 24 hours | Local SQLite database |

> 🔒 **SECURITY NOTE**: All data stays on your machine (or in your Azure subscription if deployed). Nothing is sent to external services.

### 3.3 Key Terminology

| Term | Definition |
|------|------------|
| **Tenant** | An Azure AD directory - your organization's identity boundary |
| **Subscription** | A billing container within a tenant - where Azure resources live |
| **App Registration** | An identity for the platform to authenticate to Azure |
| **Service Principal** | The "user account" that the App Registration uses |
| **RBAC** | Role-Based Access Control - how you grant permissions in Azure |
| **API Permissions** | What the app is allowed to read from Microsoft Graph |

---

## 4. Phase 1: Azure Tenant Preparation

> ⏱️ **Estimated Time**: 30-60 minutes per tenant (2-4 hours total)

### 4.1 Overview of What You'll Do

For **each of your 4 tenants**, you will:

1. Create an App Registration (the platform's identity)
2. Create a Client Secret (the platform's password)
3. Grant API Permissions (what the platform can read)
4. Assign Azure RBAC Roles (access to subscriptions)

> ⚠️ **IMPORTANT**: Do NOT skip any tenant. The platform needs access to all 4 to provide unified visibility.

### 4.2 Step-by-Step: Create App Registration

**Repeat these steps for each tenant:**

#### Step 1: Navigate to App Registrations

1. Go to [Azure Portal](https://portal.azure.com)
2. Make sure you're in the **correct tenant** (check top-right corner)
3. Search for "App registrations" in the search bar
4. Click **"+ New registration"**

#### Step 2: Configure the App Registration

| Field | Value | Notes |
|-------|-------|-------|
| **Name** | `governance-platform-reader` | Use the same name in all tenants for consistency |
| **Supported account types** | "Accounts in this organizational directory only" | Single tenant - most secure |
| **Redirect URI** | Leave blank | Not needed for this app |

5. Click **"Register"**

#### Step 3: Record Important Values

After registration, you'll see an overview page. **Record these values:**

| Value | Where to Find | Your Value |
|-------|---------------|------------|
| **Application (client) ID** | Overview page, top section | __________________ |
| **Directory (tenant) ID** | Overview page, top section | __________________ |

> ⚠️ **CRITICAL**: Store these securely! You'll need them for configuration.

#### Step 4: Create a Client Secret

1. In the App Registration, click **"Certificates & secrets"** in the left menu
2. Click **"+ New client secret"**
3. Enter description: `governance-platform-secret`
4. Choose expiration: **24 months** (maximum)
5. Click **"Add"**

> ⚠️ **CRITICAL**: Copy the **Value** immediately! It will only be shown once.

| Value | Your Value |
|-------|------------|
| **Client Secret Value** | __________________ |
| **Secret Expiration Date** | __________________ |

> 📅 **CALENDAR REMINDER**: Set a reminder to rotate this secret before it expires!

### 4.3 Step-by-Step: Grant API Permissions

#### Required Microsoft Graph Permissions

1. In the App Registration, click **"API permissions"** in the left menu
2. Click **"+ Add a permission"**
3. Select **"Microsoft Graph"**
4. Select **"Application permissions"** (NOT Delegated)
5. Search for and add each of these permissions:

| Permission | Category | What It Allows |
|------------|----------|----------------|
| `User.Read.All` | User | Read all user profiles |
| `Group.Read.All` | Group | Read all groups |
| `Directory.Read.All` | Directory | Read directory data |
| `RoleManagement.Read.All` | RoleManagement | Read role assignments |
| `Policy.Read.All` | Policy | Read policies |
| `AuditLog.Read.All` | AuditLog | Read audit logs |
| `Reports.Read.All` | Reports | Read usage reports |

6. After adding all permissions, click **"Grant admin consent for [Your Tenant]"**

> ⚠️ **REQUIRES ADMIN**: If the "Grant admin consent" button is grayed out, you need a Global Administrator to click it.

#### Verify Permissions Are Granted

After granting consent, the permissions table should show a **green checkmark** next to each permission under the "Status" column.

| Status | Meaning |
|--------|----------|
| ✅ Granted for [Tenant] | Good - permission is active |
| ⚠️ Not granted | Bad - admin consent still needed |

### 4.4 Step-by-Step: Assign Azure RBAC Roles

The App Registration also needs access to read Azure resources (VMs, storage, etc.). This is separate from Graph API permissions.

#### For Each Subscription in Each Tenant:

1. Go to **Subscriptions** in the Azure Portal
2. Select a subscription
3. Click **"Access control (IAM)"** in the left menu
4. Click **"+ Add"** → **"Add role assignment"**
5. Assign these roles:

| Role | Purpose |
|------|----------|
| **Reader** | View all resources |
| **Cost Management Reader** | View cost data |
| **Security Reader** | View security recommendations |

6. On the "Members" tab, select **"User, group, or service principal"**
7. Click **"+ Select members"**
8. Search for your app name: `governance-platform-reader`
9. Select it and click **"Review + assign"**

> ⚠️ **COMMON MISTAKE**: People forget to do this for ALL subscriptions. If you have 3 subscriptions in a tenant, you need to repeat this 3 times.

### 4.5 Verification Checklist

Before moving on, verify you've completed these for **ALL 4 TENANTS**:

| Checkpoint | Tenant 1 | Tenant 2 | Tenant 3 | Tenant 4 |
|------------|----------|----------|----------|----------|
| App Registration created | ☐ | ☐ | ☐ | ☐ |
| Client ID recorded | ☐ | ☐ | ☐ | ☐ |
| Client Secret created & recorded | ☐ | ☐ | ☐ | ☐ |
| Graph API permissions added (7 total) | ☐ | ☐ | ☐ | ☐ |
| Admin consent granted (green checkmarks) | ☐ | ☐ | ☐ | ☐ |
| Reader role assigned to ALL subscriptions | ☐ | ☐ | ☐ | ☐ |
| Cost Management Reader assigned | ☐ | ☐ | ☐ | ☐ |
| Security Reader assigned | ☐ | ☐ | ☐ | ☐ |

---

## 5. Phase 2: Local Development Setup

> ⏱️ **Estimated Time**: 15-30 minutes

### 5.1 Clone or Navigate to the Project

If you received this as a folder:
```bash
cd /path/to/control-tower
```

If cloning from a repository:
```bash
git clone https://github.com/HTT-BRANDS/control-tower.git
cd control-tower
```

### 5.2 Create Python Virtual Environment

> 💡 **What is a virtual environment?** It's an isolated Python installation so this project's dependencies don't conflict with other Python projects on your computer.

```bash
# Create the virtual environment
uv venv --index-url https://pypi.ci.artifacts.walmart.com/artifactory/api/pypi/external-pypi/simple --allow-insecure-host pypi.ci.artifacts.walmart.com

# Activate it (Mac/Linux)
source .venv/bin/activate

# Activate it (Windows PowerShell)
.venv\Scripts\Activate.ps1

# Activate it (Windows CMD)
.venv\Scripts\activate.bat
```

> ✅ **Success Indicator**: Your terminal prompt should now show `(.venv)` at the beginning.

### 5.3 Install Dependencies

```bash
uv pip install -e . --index-url https://pypi.ci.artifacts.walmart.com/artifactory/api/pypi/external-pypi/simple --allow-insecure-host pypi.ci.artifacts.walmart.com
```

> ⏱️ This may take 2-5 minutes as it downloads packages.

#### Common Installation Errors

| Error | Solution |
|-------|----------|
| `Connection timeout` | You may be behind a firewall. Try adding proxy settings. |
| `Permission denied` | Don't use `sudo`. Make sure your venv is activated. |
| `Python version not found` | Install Python 3.11+ first. |

### 5.4 Verify Installation

```bash
# Check that the app can at least import
python -c "from app.main import app; print('✅ Installation successful!')"
```

Expected output:
```
✅ Installation successful!
```

---

## 6. Phase 3: Configuration

> ⏱️ **Estimated Time**: 15-30 minutes

### 6.1 Create Environment File

```bash
# Copy the template
cp .env.example .env
```

### 6.2 Edit the Environment File

Open `.env` in your text editor and configure each section:

#### Basic Settings (Usually No Changes Needed)

```bash
# These defaults are fine for local development
DEBUG=true
LOG_LEVEL=INFO
HOST=0.0.0.0
PORT=8000
DATABASE_URL=sqlite:///./data/governance.db
```

#### Primary Tenant Credentials

> ⚠️ **IMPORTANT**: Choose ONE tenant as your "primary" tenant. This is typically your main production tenant or the tenant where you have the most admin access.

```bash
# Replace with your actual values from Phase 1
AZURE_TENANT_ID=11111111-1111-1111-1111-111111111111
AZURE_CLIENT_ID=22222222-2222-2222-2222-222222222222
AZURE_CLIENT_SECRET=your-secret-value-here
```

> 🔒 **SECURITY WARNING**: Never commit the `.env` file to Git! It's already in `.gitignore`, but double-check.

### 6.3 Register Additional Tenants

The platform stores additional tenant credentials in the database. You'll add these after the first run via the API or by running a setup script.

For now, the primary tenant configuration is enough to verify the platform works.

### 6.4 Configuration Reference

| Variable | Required | Description | Default |
|----------|----------|-------------|---------|
| `AZURE_TENANT_ID` | ✅ Yes | Your primary Azure AD tenant ID | None |
| `AZURE_CLIENT_ID` | ✅ Yes | App Registration client ID | None |
| `AZURE_CLIENT_SECRET` | ✅ Yes | App Registration secret | None |
| `DATABASE_URL` | No | SQLite connection string | `sqlite:///./data/governance.db` |
| `DEBUG` | No | Enable debug mode | `false` |
| `LOG_LEVEL` | No | Logging verbosity | `INFO` |
| `COST_SYNC_INTERVAL_HOURS` | No | How often to sync cost data | `24` |
| `COMPLIANCE_SYNC_INTERVAL_HOURS` | No | How often to sync compliance | `4` |
| `TEAMS_WEBHOOK_URL` | No | For sending alerts to Teams | None |

---

## 7. Phase 4: Testing & Validation

> ⏱️ **Estimated Time**: 30-60 minutes

### 7.1 Start the Application

```bash
# Make sure your venv is activated
source .venv/bin/activate  # Mac/Linux

# Start the application
uvicorn app.main:app --reload
```

Expected output:
```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to stop)
INFO:     Started reloader process
INFO:     Started server process
INFO:     Application startup complete.
```

### 7.2 Verify the Dashboard Loads

1. Open your web browser
2. Go to: **http://localhost:8000**
3. You should see the governance dashboard (it will be empty initially)

> ⚠️ **If you see an error**: Check the terminal for error messages. Common issues are covered in the Troubleshooting section.

### 7.3 Test the Health Endpoints

```bash
# In a new terminal window (keep the app running)
curl http://localhost:8000/health
```

Expected output:
```json
{"status":"healthy","version":"0.1.0"}
```

### 7.4 Test Azure Connectivity

```bash
# Test that the app can authenticate to Azure
curl http://localhost:8000/health/detailed
```

Look for:
```json
{
  "status": "healthy",
  "components": {
    "database": "healthy",
    "scheduler": "running",
    "azure_configured": true
  }
}
```

> ⚠️ **If `azure_configured` is `false`**: Your `.env` file is missing Azure credentials.

### 7.5 Load Sample Data (For Testing)

To see the dashboard with data before connecting to real Azure:

```bash
# Stop the app (Ctrl+C) then run:
python scripts/seed_data.py

# Start the app again
uvicorn app.main:app --reload
```

Now refresh http://localhost:8000 - you should see sample data!

### 7.6 Register Your Tenants via API

Once the app is running, register your 4 tenants:

```bash
# Register Tenant 1
curl -X POST http://localhost:8000/api/v1/tenants \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Production Tenant",
    "tenant_id": "YOUR-TENANT-1-GUID-HERE",
    "description": "Main production workloads"
  }'

# Repeat for Tenants 2, 3, 4 with appropriate names and IDs
```

### 7.7 Trigger a Manual Sync

```bash
# Sync cost data
curl -X POST http://localhost:8000/api/v1/sync/costs

# Sync compliance data
curl -X POST http://localhost:8000/api/v1/sync/compliance

# Sync resource inventory
curl -X POST http://localhost:8000/api/v1/sync/resources

# Sync identity data
curl -X POST http://localhost:8000/api/v1/sync/identity
```

### 7.8 Validation Checklist

| Test | Status |
|------|--------|
| App starts without errors | ☐ |
| Dashboard loads at http://localhost:8000 | ☐ |
| Health endpoint returns "healthy" | ☐ |
| Azure configured = true | ☐ |
| Sample data shows on dashboard | ☐ |
| All 4 tenants registered | ☐ |
| Manual sync completes without errors | ☐ |

---

## 8. Phase 5: Deployment

> ⏱️ **Estimated Time**: 1-2 hours

### 8.1 Deployment Options

| Option | Cost | Difficulty | Best For |
|--------|------|------------|----------|
| **Run locally** | Free | Easy | Development, personal use |
| **Azure App Service** | ~$13/mo | Medium | Production, team use |
| **Azure Container Apps** | ~$30-50/mo | Medium | Scalability needs |
| **Docker on a VM** | Varies | Medium | Existing infrastructure |

### 8.2 Azure App Service Deployment (Recommended)

#### Prerequisites
- Azure CLI installed and logged in
- A subscription where you can create resources

#### Step 1: Login to Azure CLI

```bash
az login
```

#### Step 2: Create App Service

```bash
# Set variables
RESOURCE_GROUP="rg-governance-platform"
APP_NAME="governance-platform-$(date +%s)"  # Unique name
LOCATION="eastus"

# Create resource group
az group create --name $RESOURCE_GROUP --location $LOCATION

# Create App Service Plan (B1 = ~$13/month)
az appservice plan create \
  --name "${APP_NAME}-plan" \
  --resource-group $RESOURCE_GROUP \
  --sku B1 \
  --is-linux

# Create Web App
az webapp create \
  --name $APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --plan "${APP_NAME}-plan" \
  --runtime "PYTHON:3.11"
```

#### Step 3: Configure Environment Variables

```bash
az webapp config appsettings set \
  --name $APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --settings \
    AZURE_TENANT_ID="your-tenant-id" \
    AZURE_CLIENT_ID="your-client-id" \
    AZURE_CLIENT_SECRET="your-secret" \
    SCM_DO_BUILD_DURING_DEPLOYMENT="true"
```

#### Step 4: Deploy the Code

```bash
# From the project directory
az webapp up --name $APP_NAME --resource-group $RESOURCE_GROUP
```

#### Step 5: Verify Deployment

```bash
# Get the URL
az webapp show --name $APP_NAME --resource-group $RESOURCE_GROUP --query "defaultHostName" -o tsv
```

Open that URL in your browser!

### 8.3 Post-Deployment Security

> ⚠️ **CRITICAL**: After deploying, complete these security steps:

1. **Enable HTTPS Only**:
   ```bash
   az webapp update --name $APP_NAME --resource-group $RESOURCE_GROUP --https-only true
   ```

2. **Restrict Network Access** (if possible):
   - Consider adding IP restrictions if only certain users/networks should access

3. **Enable Azure AD Authentication** (optional but recommended):
   - Azure Portal → App Service → Authentication → Add identity provider

---

## 9. Troubleshooting Guide

### 9.1 Installation Issues

| Problem | Possible Cause | Solution |
|---------|---------------|----------|
| `uv: command not found` | uv not installed | Run: `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| `Connection timed out` during pip install | Corporate firewall | Use Walmart proxy (see Section 2.2) |
| `Permission denied` | Running without venv | Activate virtual environment first |
| `Python 3.11+ required` | Old Python version | Install Python 3.11 from python.org |

### 9.2 Azure Authentication Issues

| Error Message | Cause | Solution |
|---------------|-------|----------|
| `AADSTS7000215: Invalid client secret` | Wrong or expired secret | Generate a new secret in Azure Portal |
| `AADSTS700016: Application not found` | Wrong tenant ID or client ID | Double-check IDs in .env |
| `AADSTS65001: User or admin has not consented` | Missing admin consent | Go to API permissions and grant admin consent |
| `Authorization_RequestDenied` | Missing Graph permissions | Add the required permissions and grant consent |

### 9.3 Azure RBAC Issues

| Error Message | Cause | Solution |
|---------------|-------|----------|
| `AuthorizationFailed` | App doesn't have Reader role | Assign Reader role on the subscription |
| `No subscriptions found` | App can't list subscriptions | Check RBAC assignments in each tenant |
| `Cost data not available` | Missing Cost Management Reader | Assign the role on each subscription |

### 9.4 Runtime Issues

| Problem | Cause | Solution |
|---------|-------|----------|
| Dashboard shows no data | Sync hasn't run yet | Trigger manual sync or wait for scheduled sync |
| `Database is locked` | Multiple processes writing | Restart the application |
| High memory usage | Too much data cached | Reduce sync frequency or add pagination |
| Slow dashboard load | Large dataset | Add database indexes (see ARCHITECTURE.md) |

### 9.5 Getting Help

If you're stuck:

1. **Check the logs**: Look at the terminal where the app is running
2. **Enable debug mode**: Set `DEBUG=true` in `.env` for more detailed logs
3. **Search the error**: Copy the exact error message and search online
4. **Contact support**: Reach out to the team that provided this platform

---

## 10. Security Considerations

### 10.1 Sensitive Data Handling

| Data Type | Risk Level | Mitigation |
|-----------|------------|------------|
| Client Secrets | 🔴 High | Store in Key Vault for production |
| Cost Data | 🟡 Medium | Access controls, no PII |
| User Lists | 🟡 Medium | Read-only access, no passwords |
| Compliance Data | 🟢 Low | Non-sensitive metrics |

### 10.2 Secret Rotation Schedule

| Secret | Rotation Frequency | Reminder |
|--------|-------------------|----------|
| Client Secrets | Every 12 months (before expiry) | Set calendar reminder |
| Database backups | Weekly | Automate if deployed |

### 10.3 Least Privilege Principle

The App Registrations should have **read-only** access:

✅ **Correct**: Reader, Cost Management Reader, Security Reader  
❌ **Wrong**: Contributor, Owner, User Access Administrator

> ⚠️ **WARNING**: Never grant write permissions unless absolutely necessary. This platform only needs to READ data.

### 10.4 Network Security

For production deployment:

- Enable HTTPS only
- Consider VNet integration
- Use Private Endpoints for Azure services
- Implement IP allowlisting if possible

---

## 11. Maintenance & Operations

### 11.1 Regular Maintenance Tasks

| Task | Frequency | How To |
|------|-----------|--------|
| Check sync status | Daily | Dashboard or `/api/v1/sync/status` |
| Review cost anomalies | Weekly | Dashboard alerts section |
| Rotate client secrets | Annually | Azure Portal → App Registrations |
| Update platform | Monthly | `git pull` and redeploy |
| Backup database | Weekly | Copy `data/governance.db` |

### 11.2 Monitoring Sync Jobs

```bash
# Check scheduled job status
curl http://localhost:8000/api/v1/sync/status
```

Expected output:
```json
{
  "status": "running",
  "jobs": [
    {"id": "sync_costs", "name": "Sync Cost Data", "next_run": "2025-02-26T00:00:00"},
    {"id": "sync_compliance", "name": "Sync Compliance Data", "next_run": "2025-02-25T20:00:00"}
  ]
}
```

### 11.3 Backup and Recovery

#### Backing Up

```bash
# The database is a single file
cp data/governance.db data/governance-backup-$(date +%Y%m%d).db
```

#### Restoring

```bash
# Stop the app first!
cp data/governance-backup-YYYYMMDD.db data/governance.db
# Restart the app
```

### 11.4 Updating the Platform

```bash
# Navigate to the project
cd control-tower

# Pull latest changes
git pull

# Update dependencies
uv pip install -e . --index-url https://pypi.ci.artifacts.walmart.com/artifactory/api/pypi/external-pypi/simple --allow-insecure-host pypi.ci.artifacts.walmart.com

# Restart the application
# (Ctrl+C if running locally, then start again)
uvicorn app.main:app --reload
```

---

## 12. Glossary

| Term | Definition |
|------|------------|
| **API** | Application Programming Interface - how software communicates |
| **App Registration** | An identity in Azure AD that applications use to authenticate |
| **Client ID** | The unique identifier for an App Registration |
| **Client Secret** | A password for an App Registration |
| **CRUD** | Create, Read, Update, Delete - basic data operations |
| **Endpoint** | A URL where an API can be accessed |
| **GUID** | Globally Unique Identifier - a 36-character ID like `12345678-1234-1234-1234-123456789012` |
| **HTMX** | A library that makes web pages interactive without JavaScript |
| **RBAC** | Role-Based Access Control - Azure's permission system |
| **REST API** | A standard way to build web APIs |
| **Service Principal** | The identity that acts on behalf of an App Registration |
| **SQLite** | A lightweight database stored as a single file |
| **Tenant** | An Azure AD directory representing an organization |
| **Virtual Environment** | An isolated Python installation for a project |

---

## 13. Appendix

### 13.1 Complete API Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Main dashboard |
| `/health` | GET | Basic health check |
| `/health/detailed` | GET | Detailed health with components |
| `/api/v1/tenants` | GET | List all tenants |
| `/api/v1/tenants` | POST | Create a tenant |
| `/api/v1/tenants/{id}` | GET | Get a specific tenant |
| `/api/v1/tenants/{id}` | PATCH | Update a tenant |
| `/api/v1/tenants/{id}` | DELETE | Delete a tenant |
| `/api/v1/costs/summary` | GET | Cost summary across tenants |
| `/api/v1/costs/by-tenant` | GET | Costs broken down by tenant |
| `/api/v1/costs/trends` | GET | Daily cost trends |
| `/api/v1/costs/anomalies` | GET | Cost anomalies |
| `/api/v1/compliance/summary` | GET | Compliance summary |
| `/api/v1/compliance/scores` | GET | Compliance scores by tenant |
| `/api/v1/compliance/non-compliant` | GET | Non-compliant policies |
| `/api/v1/resources` | GET | Resource inventory |
| `/api/v1/resources/orphaned` | GET | Orphaned resources |
| `/api/v1/resources/tagging` | GET | Tagging compliance |
| `/api/v1/identity/summary` | GET | Identity summary |
| `/api/v1/identity/privileged` | GET | Privileged accounts |
| `/api/v1/identity/guests` | GET | Guest accounts |
| `/api/v1/identity/stale` | GET | Stale accounts |
| `/api/v1/sync/{type}` | POST | Trigger manual sync |
| `/api/v1/sync/status` | GET | Sync job status |

### 13.2 Required Azure Permissions Summary

#### Microsoft Graph API Permissions (Application)

| Permission | Type | Admin Consent |
|------------|------|---------------|
| User.Read.All | Application | Yes |
| Group.Read.All | Application | Yes |
| Directory.Read.All | Application | Yes |
| RoleManagement.Read.All | Application | Yes |
| Policy.Read.All | Application | Yes |
| AuditLog.Read.All | Application | Yes |
| Reports.Read.All | Application | Yes |

#### Azure RBAC Roles (Per Subscription)

| Role | Scope | Purpose |
|------|-------|----------|
| Reader | Subscription | View all resources |
| Cost Management Reader | Subscription | View cost data |
| Security Reader | Subscription | View security info |

### 13.3 Environment Variables Reference

```bash
# Required
AZURE_TENANT_ID=           # Primary Azure AD tenant GUID
AZURE_CLIENT_ID=           # App Registration client ID
AZURE_CLIENT_SECRET=       # App Registration secret

# Optional - Application
DEBUG=false                # Enable debug mode
LOG_LEVEL=INFO             # DEBUG, INFO, WARNING, ERROR
HOST=0.0.0.0              # Server bind address
PORT=8000                  # Server port

# Optional - Database
DATABASE_URL=sqlite:///./data/governance.db

# Optional - Sync Intervals
COST_SYNC_INTERVAL_HOURS=24
COMPLIANCE_SYNC_INTERVAL_HOURS=4
RESOURCE_SYNC_INTERVAL_HOURS=1
IDENTITY_SYNC_INTERVAL_HOURS=24

# Optional - Alerting
TEAMS_WEBHOOK_URL=         # Microsoft Teams webhook for alerts
COST_ANOMALY_THRESHOLD_PERCENT=20.0
COMPLIANCE_ALERT_THRESHOLD_PERCENT=5.0

# Optional - Security
KEY_VAULT_URL=             # Azure Key Vault for secrets (production)
CORS_ORIGINS=http://localhost:3000,http://localhost:8000
```

### 13.4 Support Contacts

| Issue Type | Contact |
|------------|----------|
| Platform bugs/issues | [Your team's contact] |
| Azure permissions | Your Azure AD administrator |
| Network/firewall | Your network team |
| Security questions | Your security team |

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|----------|
| 1.0 | February 2025 | Cloud Governance Team | Initial release |

---

**End of Implementation Guide**
