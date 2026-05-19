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

from app.core.auth import User, get_current_user
from app.core.config import get_settings
from app.core.database import get_db
from app.core.templates import templates
from app.core.tenant_context import get_brand_context_for_request
from app.models.tenant import Tenant
from app.services.lighthouse_client import (
    LighthouseAzureClient,
    LighthouseDelegationError,
)

router = APIRouter(
    prefix="/onboarding",
    tags=["onboarding"],
    # Authentication required: the landing page collects Azure tenant/subscription
    # IDs and the verify endpoint writes new Tenant rows. Per ct-w6b, the page
    # should not be publicly accessible.
    dependencies=[Depends(get_current_user)],
)


def get_delegation_template(settings: Any, org_name: str = "") -> dict[str, Any]:
    """Generate the Lighthouse delegation ARM template.

    Args:
        settings: Application settings with Azure configuration
        org_name: Organization name for customization

    Returns:
        ARM template as a dictionary
    """
    managed_by_tenant_id = settings.azure_ad_tenant_id or settings.azure_tenant_id
    managed_by_principal_id = getattr(settings, "managed_identity_object_id", None)

    return {
        "$schema": "https://schema.management.azure.com/schemas/2019-08-01/subscriptionDeploymentTemplate.json#",
        "contentVersion": "1.0.0.0",
        "metadata": {
            "description": f"Azure Lighthouse delegation for {org_name or 'HTT Control Tower'}",
            "generatedFor": org_name or "Unknown Organization",
            "generatedAt": str(uuid.uuid4())[:8],
        },
        "parameters": {
            "managedByTenantId": {
                "type": "string",
                "defaultValue": managed_by_tenant_id or "",
                "metadata": {"description": "The Azure AD tenant ID of the service provider"},
            },
            "managedByPrincipalId": {
                "type": "string",
                "defaultValue": managed_by_principal_id or "",
                "metadata": {
                    "description": "The Object ID of the Managed Identity from HTT Control Tower"
                },
            },
            "mspOfferName": {
                "type": "string",
                "defaultValue": "HTT Control Tower",
                "metadata": {"description": "Name of the Lighthouse offer"},
            },
            "mspOfferDescription": {
                "type": "string",
                "defaultValue": f"Multi-tenant governance for {org_name or 'your organization'}",
                "metadata": {"description": "Description of the Lighthouse offer"},
            },
            "principalDisplayName": {
                "type": "string",
                "defaultValue": "HTT Control Tower Managed Identity",
                "metadata": {"description": "Display name for the managed identity principal"},
            },
        },
        "variables": {
            "registrationDefinitionName": "[parameters('mspOfferName')]",
            "registrationDefinitionId": "[guid(parameters('mspOfferName'), parameters('managedByTenantId'), subscription().subscriptionId)]",
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
                            "roleDefinitionId": "b24988ac-6180-42a0-ab88-20f7382dd24c",
                        },
                        {
                            "principalId": "[parameters('managedByPrincipalId')]",
                            "principalIdDisplayName": "[concat(parameters('principalDisplayName'), ' - Cost Management Reader')]",
                            "roleDefinitionId": "72fafb9e-0641-4937-9268-a91bfd8191a3",
                        },
                        {
                            "principalId": "[parameters('managedByPrincipalId')]",
                            "principalIdDisplayName": "[concat(parameters('principalDisplayName'), ' - Security Reader')]",
                            "roleDefinitionId": "39bc4728-0917-49c7-9d2c-d95423bc2eb4",
                        },
                    ],
                },
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
                },
            },
        ],
        "outputs": {
            "registrationDefinitionId": {
                "type": "string",
                "value": "[variables('registrationDefinitionId')]",
                "metadata": {"description": "The unique ID of the Lighthouse registration"},
            },
            "delegatedSubscriptionId": {
                "type": "string",
                "value": "[subscription().subscriptionId]",
                "metadata": {"description": "The subscription ID where delegation is applied"},
            },
        },
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
async def onboarding_landing_page(
    request: Request,
    user: User = Depends(get_current_user),
):
    """Landing page for self-service onboarding.

    Renders the Riverside-branded onboarding shell that extends base.html
    (Inter font, design tokens, nav, footer). Form submissions are HTMX POSTs
    to /onboarding/generate-template and /onboarding/verify.
    """
    settings = get_settings()
    brand_context = get_brand_context_for_request(request)

    if not getattr(settings, "lighthouse_enabled", True):
        # Lighthouse disabled: render the same shell with a friendly disabled
        # banner instead of the multi-step form. Keeps brand parity.
        return templates.TemplateResponse(
            request,
            "pages/onboarding_disabled.html",
            {**brand_context, "user": user},
            status_code=503,
        )

    return templates.TemplateResponse(
        request,
        "pages/onboarding.html",
        {**brand_context, "user": user},
    )


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
    if not getattr(settings, "lighthouse_enabled", True):
        return HTMLResponse(
            content='<div class="alert alert-error">Self-service onboarding is disabled.</div>',
            status_code=503,
        )

    # Validate required settings
    managed_by_tenant_id = settings.azure_ad_tenant_id or settings.azure_tenant_id
    getattr(settings, "managed_identity_object_id", None)

    if not managed_by_tenant_id:
        return HTMLResponse(
            content="""
            <div class="alert alert-error">
                <strong>Configuration Error:</strong> Managed by tenant ID is not configured.
                Please contact your administrator.
            </div>
            """,
            status_code=500,
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
    <a href="data:application/json;charset=utf-8,{template_json.replace(chr(34), "&quot;").replace("<", "&lt;").replace(">", "&gt;")}"
       download="lighthouse-delegation-{org_name.replace(" ", "-").lower() if org_name else "template"}.json"
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
            content='<div class="alert alert-error">Tenant name is required.</div>', status_code=400
        )

    if not tenant_id.strip() or len(tenant_id.replace("-", "")) != 32:
        return HTMLResponse(
            content='<div class="alert alert-error">Invalid Azure Tenant ID format.</div>',
            status_code=400,
        )

    if not subscription_id.strip() or len(subscription_id.replace("-", "")) != 32:
        return HTMLResponse(
            content='<div class="alert alert-error">Invalid Azure Subscription ID format.</div>',
            status_code=400,
        )

    # Check for existing tenant
    existing = (
        db.query(Tenant)
        .filter((Tenant.tenant_id == tenant_id) | (Tenant.name == tenant_name))
        .first()
    )

    if existing:
        return HTMLResponse(
            content=f"""
            <div class="alert alert-error">
                <strong>❌ Tenant Already Exists</strong>
                <p>A tenant with this name or Azure Tenant ID already exists.</p>
                <p>Tenant Name: {existing.name}</p>
                <p>Azure Tenant ID: {existing.tenant_id}</p>
            </div>
            """,
            status_code=409,
        )

    # Initialize Lighthouse client and verify delegation
    try:
        client = LighthouseAzureClient()
        delegation_result = await client.verify_delegation(subscription_id)

        if not delegation_result.get("is_delegated"):
            error_msg = delegation_result.get("error", "Unknown error")
            return HTMLResponse(
                content=f"""
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
                """,
                status_code=400,
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
            content=f"""
            <div class="alert alert-success">
                <strong>✅ Tenant Created Successfully!</strong>
                <p>Your Azure subscription has been onboarded to HTT Control Tower.</p>
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
            """,
            status_code=201,
        )

    except LighthouseDelegationError as e:
        return HTMLResponse(
            content=f"""
            <div class="alert alert-error">
                <strong>❌ Lighthouse Delegation Error</strong>
                <p>{str(e)}</p>
                <p>Please ensure the ARM template was deployed correctly before verifying.</p>
            </div>
            """,
            status_code=400,
        )
    except Exception as e:
        return HTMLResponse(
            content=f"""
            <div class="alert alert-error">
                <strong>❌ Unexpected Error</strong>
                <p>An error occurred during verification: {str(e)}</p>
                <p>Please try again or contact support.</p>
            </div>
            """,
            status_code=500,
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
            content={"status": "not_found", "message": f"Tenant with ID {tenant_id} not found"},
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
        },
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

    if not getattr(settings, "lighthouse_enabled", True):
        return JSONResponse(
            status_code=503, content={"error": "Self-service onboarding is disabled"}
        )

    template = get_delegation_template(settings, org_name)

    return JSONResponse(
        status_code=200,
        content={
            "template": template,
            "metadata": {
                "org_name": org_name or "",
                "generated_at": "now",
            },
        },
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
        return JSONResponse(status_code=400, content={"error": "Tenant name is required"})

    # Check for existing tenant
    existing = (
        db.query(Tenant)
        .filter((Tenant.tenant_id == tenant_id) | (Tenant.name == tenant_name))
        .first()
    )

    if existing:
        return JSONResponse(
            status_code=409,
            content={
                "error": "Tenant already exists",
                "existing_tenant": {
                    "id": existing.id,
                    "name": existing.name,
                    "tenant_id": existing.tenant_id,
                },
            },
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
                },
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
                    "created_at": new_tenant.created_at.isoformat()
                    if new_tenant.created_at
                    else None,
                },
                "delegation": delegation_result,
            },
        )

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": str(e),
            },
        )
