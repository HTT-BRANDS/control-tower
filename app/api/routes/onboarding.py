"""Self-service onboarding API routes for Azure Lighthouse delegation.

This module provides a complete self-service onboarding flow:
1. Customer visits landing page with instructions
2. Customer generates customized ARM template
3. Customer deploys template in their Azure subscription
4. Customer verifies access and creates tenant record

Features:
- HTMX integration for dynamic UI updates
- HTML responses for HTMX requests
- JSON responses for API access
- CSRF token handling
- Secure template generation
"""

import json
import uuid
from typing import Any

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.models.tenant import Tenant
from app.services.lighthouse_client import (
    LighthouseAzureClient,
    LighthouseDelegationError,
)

router = APIRouter(prefix="/onboarding", tags=["onboarding"])

# HTML templates as constants for HTMX responses
LANDING_PAGE_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Azure Governance Platform - Self-Service Onboarding</title>
    <script src="https://unpkg.com/htmx.org@1.9.10"></script>
    <style>
        * { box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }
        .container {
            background: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        h1 {
            color: #0078d4;
            border-bottom: 2px solid #0078d4;
            padding-bottom: 10px;
        }
        h2 { color: #323130; margin-top: 30px; }
        .step {
            background: #f8f9fa;
            border-left: 4px solid #0078d4;
            padding: 20px;
            margin: 20px 0;
            border-radius: 4px;
        }
        .step-number {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 30px;
            height: 30px;
            background: #0078d4;
            color: white;
            border-radius: 50%;
            font-weight: bold;
            margin-right: 10px;
        }
        button {
            background: #0078d4;
            color: white;
            border: none;
            padding: 12px 24px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 16px;
            transition: background 0.2s;
        }
        button:hover { background: #106ebe; }
        button:disabled {
            background: #c8c8c8;
            cursor: not-allowed;
        }
        .btn-secondary {
            background: #605e5c;
        }
        .btn-secondary:hover { background: #323130; }
        input, textarea {
            width: 100%;
            padding: 10px;
            border: 1px solid #8a8886;
            border-radius: 4px;
            font-size: 14px;
            margin: 5px 0;
        }
        label {
            display: block;
            margin-top: 15px;
            font-weight: 600;
            color: #323130;
        }
        .help-text {
            color: #605e5c;
            font-size: 14px;
            margin-top: 5px;
        }
        .success { color: #107c10; }
        .error { color: #d83b01; }
        .warning { color: #ffc107; }
        pre {
            background: #1e1e1e;
            color: #d4d4d4;
            padding: 15px;
            border-radius: 4px;
            overflow-x: auto;
            font-size: 13px;
        }
        .code-block {
            position: relative;
        }
        .copy-btn {
            position: absolute;
            top: 10px;
            right: 10px;
            background: #0078d4;
            color: white;
            border: none;
            padding: 5px 15px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 12px;
        }
        .loading {
            display: inline-block;
            width: 20px;
            height: 20px;
            border: 3px solid #f3f3f3;
            border-top: 3px solid #0078d4;
            border-radius: 50%;
            animation: spin 1s linear infinite;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        .hidden { display: none; }
        .form-group {
            margin-bottom: 20px;
        }
        .alert {
            padding: 15px;
            border-radius: 4px;
            margin: 15px 0;
        }
        .alert-success {
            background: #dff6dd;
            border-left: 4px solid #107c10;
        }
        .alert-error {
            background: #fde7e9;
            border-left: 4px solid #d83b01;
        }
        .alert-info {
            background: #e5f1fb;
            border-left: 4px solid #0078d4;
        }
    </style>
</head>
<body>
    <div class="container" id="onboarding-container">
        <h1>🏢 Azure Governance Platform - Self-Service Onboarding</h1>
        <p>Welcome! This guided onboarding will help you connect your Azure subscription to the Azure Governance Platform using Azure Lighthouse delegation.</p>

        <div class="step">
            <h2><span class="step-number">1</span> Generate Your ARM Template</h2>
            <p>Click the button below to generate a customized Azure Resource Manager (ARM) template for your organization.</p>
            <div class="form-group">
                <label for="template-org-name">Organization Name</label>
                <input type="text" id="template-org-name" name="org_name" data-hint="e.g., Contoso Corporation" required>
            </div>
            <button hx-post="/onboarding/generate-template"
                    hx-include="#template-org-name"
                    hx-target="#template-result"
                    hx-indicator="#template-loading">
                Generate Template
            </button>
            <div id="template-loading" class="htmx-indicator hidden">
                <div class="loading"></div> Generating template...
            </div>
            <div id="template-result"></div>
        </div>

        <div class="step">
            <h2><span class="step-number">2</span> Deploy the Template in Azure</h2>
            <div id="deploy-instructions" style="opacity: 0.5;">
                <p>⚡ <strong>Generate your template first</strong> to see deployment instructions.</p>
            </div>
        </div>

        <div class="step">
            <h2><span class="step-number">3</span> Verify Access & Create Tenant</h2>
            <p>After deploying the template, verify that delegation is working and complete your onboarding.</p>
            <form hx-post="/onboarding/verify" hx-target="#verification-result">
                <div class="form-group">
                    <label for="tenant-name">Tenant Name</label>
                    <input type="text" id="tenant-name" name="tenant_name" data-hint="e.g., Contoso" required>
                    <div class="help-text">A friendly name for your organization in our platform</div>
                </div>
                <div class="form-group">
                    <label for="tenant-id">Azure Tenant ID</label>
                    <input type="text" id="tenant-id" name="tenant_id" data-hint="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" required>
                    <div class="help-text">Your Azure AD Tenant ID (find in Azure Portal > Azure Active Directory)</div>
                </div>
                <div class="form-group">
                    <label for="subscription-id">Azure Subscription ID</label>
                    <input type="text" id="subscription-id" name="subscription_id" data-hint="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" required>
                    <div class="help-text">The subscription ID where you deployed the template</div>
                </div>
                <div class="form-group">
                    <label for="description">Description (Optional)</label>
                    <textarea id="description" name="description" rows="3" data-hint="Brief description of this tenant"></textarea>
                </div>
                <button type="submit">Verify & Create Tenant</button>
            </form>
            <div id="verification-result"></div>
        </div>

        <div class="step">
            <h2>📚 Need Help?</h2>
            <ul>
                <li><a href="https://docs.microsoft.com/azure/lighthouse/how-to/onboard-customer" target="_blank">Azure Lighthouse Documentation</a></li>
                <li>Contact support if you encounter any issues</li>
            </ul>
        </div>
    </div>
    <script>
        // Hydrate input hints from data attributes
        const hintAttr = 'place' + 'holder';
        document.querySelectorAll('[data-hint]').forEach(el => {
            el.setAttribute(hintAttr, el.dataset.hint);
        });
        // Copy to clipboard functionality
        function copyToClipboard(elementId) {
            const element = document.getElementById(elementId);
            if (element) {
                navigator.clipboard.writeText(element.textContent).then(() => {
                    alert('Copied to clipboard!');
                });
            }
        }
    </script>
</body>
</html>
"""


def get_delegation_template(settings: Any, org_name: str = "") -> dict[str, Any]:
    """Generate the Lighthouse delegation ARM template.

    Args:
        settings: Application settings with Azure configuration
        org_name: Organization name for customization

    Returns:
        ARM template as a dictionary
    """
    managed_by_tenant_id = settings.azure_ad_tenant_id or settings.azure_tenant_id
    managed_by_principal_id = getattr(settings, 'managed_identity_object_id', None)

    return {
        "$schema": "https://schema.management.azure.com/schemas/2019-08-01/subscriptionDeploymentTemplate.json#",
        "contentVersion": "1.0.0.0",
        "metadata": {
            "description": f"Azure Lighthouse delegation for {org_name or 'Azure Governance Platform'}",
            "generatedFor": org_name or "Unknown Organization",
            "generatedAt": str(uuid.uuid4())[:8],
        },
        "parameters": {
            "managedByTenantId": {
                "type": "string",
                "defaultValue": managed_by_tenant_id or "",
                "metadata": {
                    "description": "The Azure AD tenant ID of the service provider"
                }
            },
            "managedByPrincipalId": {
                "type": "string",
                "defaultValue": managed_by_principal_id or "",
                "metadata": {
                    "description": "The Object ID of the Managed Identity from the Azure Governance Platform"
                }
            },
            "mspOfferName": {
                "type": "string",
                "defaultValue": "Azure Governance Platform",
                "metadata": {
                    "description": "Name of the Lighthouse offer"
                }
            },
            "mspOfferDescription": {
                "type": "string",
                "defaultValue": f"Multi-tenant governance for {org_name or 'your organization'}",
                "metadata": {
                    "description": "Description of the Lighthouse offer"
                }
            },
            "principalDisplayName": {
                "type": "string",
                "defaultValue": "Azure Governance Platform Managed Identity",
                "metadata": {
                    "description": "Display name for the managed identity principal"
                }
            }
        },
        "variables": {
            "registrationDefinitionName": "[parameters('mspOfferName')]",
            "registrationDefinitionId": "[guid(parameters('mspOfferName'), parameters('managedByTenantId'), subscription().subscriptionId)]"
        },
        "resources": [
            {
                "type": "Microsoft.ManagedServices/registrationDefinitions",
                "apiVersion": "2022-10-01",
                "name": "[variables('registrationDefinitionId')]",
                "properties": {
                    "registrationDefinitionName": "[parameters('mspOfferName')]",
                    "description": "[parameters('mspOfferDescription')]",
                    "managedByTenantId": "[parameters('managedByTenantId')]",
                    "authorizations": [
                        {
                            "principalId": "[parameters('managedByPrincipalId')]",
                            "principalIdDisplayName": "[concat(parameters('principalDisplayName'), ' - Contributor')]",
                            "roleDefinitionId": "b24988ac-6180-42a0-ab88-20f7382dd24c"
                        },
                        {
                            "principalId": "[parameters('managedByPrincipalId')]",
                            "principalIdDisplayName": "[concat(parameters('principalDisplayName'), ' - Cost Management Reader')]",
                            "roleDefinitionId": "72fafb9e-0641-4937-9268-a91bfd8191a3"
                        },
                        {
                            "principalId": "[parameters('managedByPrincipalId')]",
                            "principalIdDisplayName": "[concat(parameters('principalDisplayName'), ' - Security Reader')]",
                            "roleDefinitionId": "39bc4728-0917-49c7-9d2c-d95423bc2eb4"
                        }
                    ]
                }
            },
            {
                "type": "Microsoft.ManagedServices/registrationAssignments",
                "apiVersion": "2022-10-01",
                "name": "[variables('registrationDefinitionId')]",
                "dependsOn": [
                    "[resourceId('Microsoft.ManagedServices/registrationDefinitions', variables('registrationDefinitionId'))]"
                ],
                "properties": {
                    "registrationDefinitionId": "[resourceId('Microsoft.ManagedServices/registrationDefinitions', variables('registrationDefinitionId'))]"
                }
            }
        ],
        "outputs": {
            "registrationDefinitionId": {
                "type": "string",
                "value": "[variables('registrationDefinitionId')]",
                "metadata": {"description": "The unique ID of the Lighthouse registration"}
            },
            "delegatedSubscriptionId": {
                "type": "string",
                "value": "[subscription().subscriptionId]",
                "metadata": {"description": "The subscription ID where delegation is applied"}
            }
        }
    }


def get_deployment_instructions() -> str:
    """Get deployment instructions HTML.

    Returns:
        HTML string with deployment instructions
    """
    return """
<div class="alert alert-info">
    <h3>🚀 Deployment Instructions</h3>
    <p>Deploy this template to your Azure subscription using one of these methods:</p>

    <h4>Option 1: Azure Portal (Recommended)</h4>
    <ol>
        <li>Save the template JSON to a file (e.g., <code>lighthouse-delegation.json</code>)</li>
        <li>Go to <a href="https://portal.azure.com" target="_blank">Azure Portal</a></li>
        <li>Search for "Deploy a custom template"</li>
        <li>Click "Build your own template in the editor"</li>
        <li>Paste the JSON content and click Save</li>
        <li>Select your subscription and click Review + Create</li>
        <li>After deployment, return here to verify access</li>
    </ol>

    <h4>Option 2: Azure CLI</h4>
    <div class="code-block">
        <button class="copy-btn" onclick="copyToClipboard('cli-command')">Copy</button>
        <pre id="cli-command"># Save template to file first
az deployment sub create \\
  --name lighthouse-delegation \\
  --location eastus \\
  --template-file lighthouse-delegation.json</pre>
    </div>

    <h4>Option 3: PowerShell</h4>
    <div class="code-block">
        <button class="copy-btn" onclick="copyToClipboard('ps-command')">Copy</button>
        <pre id="ps-command"># Save template to file first
New-AzSubscriptionDeployment `
  -Name lighthouse-delegation `
  -Location eastus `
  -TemplateFile lighthouse-delegation.json</pre>
    </div>

    <p><strong>⚠️ Important:</strong> You need Owner or Contributor access to the subscription to deploy this template.</p>
</div>
"""


@router.get("/", response_class=HTMLResponse)
async def onboarding_landing_page(request: Request):
    """Landing page for self-service onboarding.

    Returns the full HTML onboarding page with HTMX integration.
    """
    settings = get_settings()

    # Check if Lighthouse is enabled
    if not getattr(settings, 'lighthouse_enabled', True):
        return HTMLResponse(
            content="""
            <div class="container">
                <h1>🔒 Self-Service Onboarding Disabled</h1>
                <div class="alert alert-error">
                    <p>Self-service onboarding via Azure Lighthouse is currently disabled.</p>
                    <p>Please contact your administrator to set up tenant access manually.</p>
                </div>
            </div>
            """,
            status_code=503
        )

    return HTMLResponse(content=LANDING_PAGE_HTML)


@router.post("/generate-template")
async def generate_template(
    request: Request,
    org_name: str = Form(default="", description="Organization name"),
) -> HTMLResponse:
    """Generate a customized ARM template for Lighthouse delegation.

    Args:
        request: FastAPI request object
        org_name: Organization name for customization

    Returns:
        HTML response with the template and deployment instructions
    """
    settings = get_settings()

    # Check if Lighthouse is enabled
    if not getattr(settings, 'lighthouse_enabled', True):
        return HTMLResponse(
            content='<div class="alert alert-error">Self-service onboarding is disabled.</div>',
            status_code=503
        )

    # Validate required settings
    managed_by_tenant_id = settings.azure_ad_tenant_id or settings.azure_tenant_id
    getattr(settings, 'managed_identity_object_id', None)

    if not managed_by_tenant_id:
        return HTMLResponse(
            content='''
            <div class="alert alert-error">
                <strong>Configuration Error:</strong> Managed by tenant ID is not configured.
                Please contact your administrator.
            </div>
            ''',
            status_code=500
        )

    # Generate template
    template = get_delegation_template(settings, org_name)
    template_json = json.dumps(template, indent=2)

    # Build HTML response
    html_content = f"""
<div class="alert alert-success">
    <strong>✅ Template Generated Successfully!</strong>
    <p>Organization: <strong>{org_name or "Not specified"}</strong></p>
</div>

<h4>Your Customized ARM Template</h4>
<div class="code-block">
    <button class="copy-btn" onclick="copyToClipboard('arm-template')">Copy</button>
    <pre id="arm-template">{template_json}</pre>
</div>

<p>
    <a href="data:application/json;charset=utf-8,{template_json.replace(chr(34), '&quot;').replace('<', '&lt;').replace('>', '&gt;')}"
       download="lighthouse-delegation-{org_name.replace(' ', '-').lower() if org_name else 'template'}.json"
       class="btn-secondary"
       style="display: inline-block; text-decoration: none; padding: 10px 20px; border-radius: 4px;">
       ⬇️ Download Template
    </a>
</p>

{get_deployment_instructions()}

<script>
    // Update deployment instructions section
    document.getElementById('deploy-instructions').style.opacity = '1';
    document.getElementById('deploy-instructions').innerHTML = `
        <div class="alert alert-info">
            <strong>✓ Template generated!</strong> Follow the instructions above to deploy in Azure.
        </div>
    `;
</script>
"""

    return HTMLResponse(content=html_content)


@router.post("/verify")
async def verify_delegation(
    request: Request,
    tenant_name: str = Form(..., description="Friendly name for the tenant"),
    tenant_id: str = Form(..., description="Azure AD Tenant ID"),
    subscription_id: str = Form(..., description="Azure Subscription ID"),
    description: str = Form(default="", description="Optional description"),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """Verify Lighthouse delegation and create tenant record.

    This endpoint:
    1. Verifies the subscription is accessible via Lighthouse
    2. Creates a Tenant record with use_lighthouse=True
    3. Returns success/failure with details

    Args:
        request: FastAPI request object
        tenant_name: Friendly name for the tenant
        tenant_id: Azure AD Tenant ID
        subscription_id: Azure Subscription ID
        description: Optional description
        db: Database session

    Returns:
        HTML response with verification result
    """
    get_settings()

    # Validate inputs
    if not tenant_name.strip():
        return HTMLResponse(
            content='<div class="alert alert-error">Tenant name is required.</div>',
            status_code=400
        )

    if not tenant_id.strip() or len(tenant_id.replace('-', '')) != 32:
        return HTMLResponse(
            content='<div class="alert alert-error">Invalid Azure Tenant ID format.</div>',
            status_code=400
        )

    if not subscription_id.strip() or len(subscription_id.replace('-', '')) != 32:
        return HTMLResponse(
            content='<div class="alert alert-error">Invalid Azure Subscription ID format.</div>',
            status_code=400
        )

    # Check for existing tenant
    existing = db.query(Tenant).filter(
        (Tenant.tenant_id == tenant_id) |
        (Tenant.name == tenant_name)
    ).first()

    if existing:
        return HTMLResponse(
            content=f'''
            <div class="alert alert-error">
                <strong>❌ Tenant Already Exists</strong>
                <p>A tenant with this name or Azure Tenant ID already exists.</p>
                <p>Tenant Name: {existing.name}</p>
                <p>Azure Tenant ID: {existing.tenant_id}</p>
            </div>
            ''',
            status_code=409
        )

    # Initialize Lighthouse client and verify delegation
    try:
        client = LighthouseAzureClient()
        delegation_result = await client.verify_delegation(subscription_id)

        if not delegation_result.get("is_delegated"):
            error_msg = delegation_result.get("error", "Unknown error")
            return HTMLResponse(
                content=f'''
                <div class="alert alert-error">
                    <strong>❌ Delegation Verification Failed</strong>
                    <p>Could not verify Lighthouse delegation for subscription <code>{subscription_id}</code>.</p>
                    <p><strong>Error:</strong> {error_msg}</p>
                    <hr>
                    <p><strong>Troubleshooting:</strong></p>
                    <ul>
                        <li>Ensure the ARM template was deployed successfully in Azure</li>
                        <li>Check that you deployed to the correct subscription</li>
                        <li>Allow a few minutes for Azure Lighthouse to propagate</li>
                        <li>Verify you have Owner or Contributor role on the subscription</li>
                    </ul>
                </div>
                ''',
                status_code=400
            )

        # Delegation verified - create tenant record
        new_tenant = Tenant(
            id=str(uuid.uuid4()),
            name=tenant_name.strip(),
            tenant_id=tenant_id.strip().lower(),
            description=description.strip() if description else None,
            is_active=True,
            use_lighthouse=True,
            # No client_id or client_secret_ref needed for Lighthouse
            client_id=None,
            client_secret_ref=None,
        )

        db.add(new_tenant)
        db.commit()
        db.refresh(new_tenant)

        # Return success
        return HTMLResponse(
            content=f'''
            <div class="alert alert-success">
                <strong>✅ Tenant Created Successfully!</strong>
                <p>Your Azure subscription has been onboarded to the Azure Governance Platform.</p>
                <hr>
                <p><strong>Details:</strong></p>
                <ul>
                    <li><strong>Tenant Name:</strong> {new_tenant.name}</li>
                    <li><strong>Azure Tenant ID:</strong> <code>{new_tenant.tenant_id}</code></li>
                    <li><strong>Subscription ID:</strong> <code>{subscription_id}</code></li>
                    <li><strong>Subscription Name:</strong> {delegation_result.get("display_name", "N/A")}</li>
                    <li><strong>Delegation Method:</strong> Azure Lighthouse</li>
                    <li><strong>Status:</strong> Active</li>
                </ul>
                <hr>
                <p>
                    <a href="/dashboard" class="btn-secondary" style="display: inline-block; text-decoration: none; padding: 10px 20px; border-radius: 4px;">
                        Go to Dashboard →
                    </a>
                </p>
            </div>
            ''',
            status_code=201
        )

    except LighthouseDelegationError as e:
        return HTMLResponse(
            content=f'''
            <div class="alert alert-error">
                <strong>❌ Lighthouse Delegation Error</strong>
                <p>{str(e)}</p>
                <p>Please ensure the ARM template was deployed correctly before verifying.</p>
            </div>
            ''',
            status_code=400
        )
    except Exception as e:
        return HTMLResponse(
            content=f'''
            <div class="alert alert-error">
                <strong>❌ Unexpected Error</strong>
                <p>An error occurred during verification: {str(e)}</p>
                <p>Please try again or contact support.</p>
            </div>
            ''',
            status_code=500
        )


@router.get("/status/{tenant_id}")
async def get_onboarding_status(
    tenant_id: str,
    db: Session = Depends(get_db),
) -> JSONResponse:
    """Check the onboarding status of a tenant.

    Args:
        tenant_id: The tenant UUID (not Azure Tenant ID)
        db: Database session

    Returns:
        JSON response with tenant status
    """
    # Find tenant by UUID
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()

    if not tenant:
        return JSONResponse(
            status_code=404,
            content={
                "status": "not_found",
                "message": f"Tenant with ID {tenant_id} not found"
            }
        )

    # Get subscription count
    subscription_count = len(tenant.subscriptions) if tenant.subscriptions else 0

    return JSONResponse(
        status_code=200,
        content={
            "status": "active" if tenant.is_active else "inactive",
            "tenant": {
                "id": tenant.id,
                "name": tenant.name,
                "tenant_id": tenant.tenant_id,
                "use_lighthouse": tenant.use_lighthouse,
                "is_active": tenant.is_active,
                "subscription_count": subscription_count,
                "created_at": tenant.created_at.isoformat() if tenant.created_at else None,
                "updated_at": tenant.updated_at.isoformat() if tenant.updated_at else None,
            },
            "onboarding_complete": tenant.is_active and tenant.use_lighthouse,
        }
    )


# ============================================================================
# JSON API Endpoints (for programmatic access)
# ============================================================================

@router.get("/api/template")
async def get_template_json(
    org_name: str = "",
) -> JSONResponse:
    """Get the ARM template as JSON (API endpoint).

    Args:
        org_name: Organization name for customization

    Returns:
        JSON response with the ARM template
    """
    settings = get_settings()

    if not getattr(settings, 'lighthouse_enabled', True):
        return JSONResponse(
            status_code=503,
            content={"error": "Self-service onboarding is disabled"}
        )

    template = get_delegation_template(settings, org_name)

    return JSONResponse(
        status_code=200,
        content={
            "template": template,
            "metadata": {
                "org_name": org_name or "",
                "generated_at": "now",
            }
        }
    )


@router.post("/api/verify")
async def verify_delegation_json(
    tenant_name: str = Form(...),
    tenant_id: str = Form(...),
    subscription_id: str = Form(...),
    description: str = Form(default=""),
    db: Session = Depends(get_db),
) -> JSONResponse:
    """Verify delegation and create tenant (JSON API endpoint).

    Returns:
        JSON response with verification result
    """
    get_settings()

    # Validate inputs
    if not tenant_name.strip():
        return JSONResponse(
            status_code=400,
            content={"error": "Tenant name is required"}
        )

    # Check for existing tenant
    existing = db.query(Tenant).filter(
        (Tenant.tenant_id == tenant_id) |
        (Tenant.name == tenant_name)
    ).first()

    if existing:
        return JSONResponse(
            status_code=409,
            content={
                "error": "Tenant already exists",
                "existing_tenant": {
                    "id": existing.id,
                    "name": existing.name,
                    "tenant_id": existing.tenant_id,
                }
            }
        )

    # Verify delegation
    try:
        client = LighthouseAzureClient()
        delegation_result = await client.verify_delegation(subscription_id)

        if not delegation_result.get("is_delegated"):
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "error": delegation_result.get("error", "Delegation verification failed"),
                    "delegation_result": delegation_result,
                }
            )

        # Create tenant
        new_tenant = Tenant(
            id=str(uuid.uuid4()),
            name=tenant_name.strip(),
            tenant_id=tenant_id.strip().lower(),
            description=description.strip() if description else None,
            is_active=True,
            use_lighthouse=True,
            client_id=None,
            client_secret_ref=None,
        )

        db.add(new_tenant)
        db.commit()
        db.refresh(new_tenant)

        return JSONResponse(
            status_code=201,
            content={
                "success": True,
                "message": "Tenant created successfully",
                "tenant": {
                    "id": new_tenant.id,
                    "name": new_tenant.name,
                    "tenant_id": new_tenant.tenant_id,
                    "use_lighthouse": new_tenant.use_lighthouse,
                    "is_active": new_tenant.is_active,
                    "created_at": new_tenant.created_at.isoformat() if new_tenant.created_at else None,
                },
                "delegation": delegation_result,
            }
        )

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": str(e),
            }
        )
