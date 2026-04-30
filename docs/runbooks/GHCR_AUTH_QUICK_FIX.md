# 🔧 GHCR Authentication Quick Fix Guide

**For:** Azure Governance Platform Production 503 Error  
**Created:** 2025-01-28  
**Status:** Ready for Execution

---

## 🎯 Choose Your Fix Path

Two options to resolve the GHCR authentication issue. Pick **ONE** and follow the steps.

---

## Option A: Quick Browser Auth (2 minutes) ⭐ Recommended

Use this if you have `gh` CLI installed and want to refresh your authentication with the required package scopes.

### Step 1: Run the Auth Refresh Command

```bash
gh auth refresh --hostname github.com --scopes read:packages,write:packages
```

### Step 2: Complete Browser Flow

1. The command will display a **device code** (e.g., `ABCD-1234`)
2. Visit: **https://github.com/login/device**
3. Enter the code shown in your terminal
4. Click **Authorize** to grant the package scopes
5. Wait for the CLI to confirm: `✓ Authentication complete`

### Step 3: Verify Token Works

```bash
# Test that you can access the package
gh api /user/packages/container/control-tower
```

If you see package metadata (not a 403 error), the auth is working.

### Step 4: Tell Me You're Done

**Message me:** `auth done`

I'll immediately execute the fix (see "What Happens Next" below).

---

## Option B: GitHub Web UI (1 minute)

Use this if you have admin access to the package settings and want to make the image public.

### Step 1: Navigate to Package Settings

Go to:
```
https://github.com/HTT-BRANDS/control-tower/pkgs/container/control-tower
```

### Step 2: Open Package Settings

1. Click the **gear icon** (⚙️) on the right side labeled **"Package settings"**

### Step 3: Change Visibility

1. Scroll to **"Danger Zone"** section
2. Find **"Change package visibility"**
3. Click **"Change visibility"** button
4. Select **"Public"**
5. Type the package name to confirm: `control-tower`
6. Click **"I understand, change visibility"**

### Step 4: Wait for Propagation

⏱️ **Wait 30 seconds** for the visibility change to propagate through GitHub's CDN.

### Step 5: Tell Me You're Done

**Message me:** `package public`

I'll immediately restart the app service (see "What Happens Next" below).

---

## 🚀 What Happens Next (Auto-Executed by Me)

Once you send `auth done` or `package public`, I will **immediately** execute:

```bash
# ============================================
# AUTOMATED FIX EXECUTION
# Triggered by your completion message
# ============================================

# Step 1: Restart the app service to pull fresh
az webapp restart \
  --name app-governance-prod \
  --resource-group rg-governance-production

echo "⏱️ App service restarting..."

# Step 2: Wait for startup (60 seconds)
sleep 60

echo "✓ Wait complete, verifying health..."

# Step 3: Verify health endpoint
curl -s https://app-governance-prod.azurewebsites.net/health | jq .
```

### Expected Output (Success)

```json
{
  "status": "healthy",
  "timestamp": "2025-01-28T...",
  "version": "1.x.x"
}
```

**HTTP Status:** `200 OK`

---

## ✅ Verification Checklist

After I run the fix, confirm these work:

| Check | Command | Expected |
|-------|---------|----------|
| Health endpoint | `curl https://app-governance-prod.azurewebsites.net/health` | `{"status":"healthy"}` |
| Main site | Open in browser | Loads without 503 error |
| API docs | `/docs` endpoint | Swagger UI loads |

---

## 🆘 If Something Goes Wrong

### Option A Failed (Auth Still 403)

```bash
# Check your current auth status
gh auth status

# If needed, logout and re-login
gh auth logout
gh auth login --scopes read:packages,write:packages
```

### Option B Failed (Still Can't Pull)

1. Double-check the package is actually public:
   ```bash
   curl -I https://ghcr.io/v2/htt-brands/control-tower/manifests/latest
   ```
   Should return `200 OK` (not `401 Unauthorized`)

2. Wait 2-3 minutes for CDN propagation, then retry

### Still Stuck?

- Check Azure status: https://status.azure.com
- Check GitHub status: https://www.githubstatus.com
- Ping me with the error message

---

## 📋 Quick Reference Card

```
┌─────────────────────────────────────────────────────────┐
│  GHCR AUTH FIX - QUICK REFERENCE                        │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  OPTION A: Browser Auth (gh CLI)                       │
│  ────────────────────────────────                       │
│  1. gh auth refresh --hostname github.com \            │
│       --scopes read:packages,write:packages          │
│  2. Visit https://github.com/login/device               │
│  3. Enter code, authorize                              │
│  4. Tell me: "auth done"                                │
│                                                         │
│  OPTION B: Web UI (Make Public)                        │
│  ────────────────────────────────                       │
│  1. Visit package settings URL                          │
│  2. Click gear icon → "Change visibility"              │
│  3. Select "Public" → Confirm                          │
│  4. Wait 30s                                            │
│  5. Tell me: "package public"                           │
│                                                         │
│  WHAT I DO:                                            │
│  ──────────                                            │
│  • Restart app service                                  │
│  • Wait 60s                                             │
│  • Verify /health returns 200                           │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## 🔗 Related Documentation

- Full runbook: [`fix-production-ghcr-auth.md`](./fix-production-ghcr-auth.md)
- Detailed report: [`PRODUCTION_GHCR_FIX_REPORT.md`](../../PRODUCTION_GHCR_FIX_REPORT.md)
- Fix script: [`fix-production-503.sh`](../../fix-production-503.sh)

---

**Ready to execute on your signal.** 🐺

*Choose Option A or B, complete the steps, then message me the completion phrase. I'll handle the rest.*
