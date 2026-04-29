"""Documentation routes and custom OpenAPI generation."""

import json
from pathlib import Path

from fastapi import Request
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse


def register_docs_routes(app, settings, jwt_manager) -> None:
    """Register protected Swagger UI and ReDoc routes."""

    @app.get("/docs", include_in_schema=False)
    async def swagger_ui_html(request: Request):
        """Swagger UI documentation with auth protection in production."""
        auth_error = _production_docs_auth_error(request, settings, jwt_manager)
        if auth_error:
            return auth_error

        return get_swagger_ui_html(
            openapi_url="/openapi.json",
            title=f"{settings.app_name} - Swagger UI",
            swagger_js_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js",
            swagger_css_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css",
        )

    @app.get("/redoc", include_in_schema=False)
    async def redoc_html(request: Request):
        """ReDoc documentation with auth protection in production."""
        auth_error = _production_docs_auth_error(request, settings, jwt_manager)
        if auth_error:
            return auth_error

        return get_redoc_html(
            openapi_url="/openapi.json",
            title=f"{settings.app_name} - ReDoc",
            redoc_js_url="https://cdn.jsdelivr.net/npm/redoc@2/bundles/redoc.standalone.js",
        )


def _production_docs_auth_error(request: Request, settings, jwt_manager):
    if not settings.is_production:
        return None

    token = None
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:]
    if not token:
        token = request.cookies.get("access_token")

    if not token:
        return JSONResponse(
            status_code=401,
            content={"detail": "Authentication required to access API documentation"},
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        jwt_manager.decode_token(token)
    except Exception:
        return JSONResponse(
            status_code=401,
            content={"detail": "Invalid or expired token"},
            headers={"WWW-Authenticate": "Bearer"},
        )
    return None


def load_openapi_examples(logger) -> dict:
    """Load OpenAPI examples from docs/openapi-examples directory."""
    examples_dir = Path(__file__).parent.parent / "docs" / "openapi-examples"
    examples = {"auth": {}, "requests": {}, "responses": {}}

    if not examples_dir.exists():
        logger.warning(f"OpenAPI examples directory not found: {examples_dir}")
        return examples

    try:
        for category in examples:
            category_dir = examples_dir / category
            if not category_dir.exists():
                continue
            for file in category_dir.glob("*.json"):
                with open(file) as handle:
                    examples[category][file.stem] = json.load(handle)

        logger.info(
            f"Loaded OpenAPI examples: {len(examples['auth'])} auth, "
            f"{len(examples['requests'])} requests, "
            f"{len(examples['responses'])} responses"
        )
    except Exception as exc:
        logger.warning(f"Failed to load OpenAPI examples: {exc}")

    return examples


def create_custom_openapi(app, logger):
    """Build a FastAPI custom OpenAPI generator bound to app state."""

    def custom_openapi() -> dict:
        if app.openapi_schema:
            return app.openapi_schema

        openapi_schema = get_openapi(
            title=app.title,
            version=app.version,
            openapi_version=app.openapi_version,
            description=app.description,
            routes=app.routes,
            tags=app.openapi_tags,
            contact=app.contact,
            license_info=app.license_info,
        )

        openapi_schema["components"]["securitySchemes"] = {
            "bearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
                "description": "JWT token obtained from Azure AD OAuth2 flow",
            },
            "oauth2": {
                "type": "oauth2",
                "flows": {
                    "authorizationCode": {
                        "authorizationUrl": "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
                        "tokenUrl": "https://login.microsoftonline.com/common/oauth2/v2.0/token",
                        "refreshUrl": "https://login.microsoftonline.com/common/oauth2/v2.0/token",
                        "scopes": {
                            "openid": "Authenticate user identity",
                            "profile": "Access user profile",
                            "email": "Access user email",
                            "User.Read": "Read user profile from Microsoft Graph",
                        },
                    }
                },
                "description": "Azure AD OAuth2 authentication",
            },
            "apiKey": {
                "type": "apiKey",
                "in": "header",
                "name": "X-API-Key",
                "description": "API key for service-to-service authentication",
            },
        }
        openapi_schema["security"] = [
            {"bearerAuth": []},
            {"oauth2": ["openid", "profile", "email", "User.Read"]},
        ]
        openapi_schema["externalDocs"] = {
            "description": "Full Documentation",
            "url": "https://github.com/htt-brands/azure-governance-platform/tree/main/docs",
        }
        openapi_schema["servers"] = [
            {"url": "/", "description": "Current server"},
            {"url": "https://api-staging.example.com", "description": "Staging server"},
            {"url": "https://api.example.com", "description": "Production server"},
        ]

        inject_openapi_examples(openapi_schema, app, logger)
        app.openapi_schema = openapi_schema
        return app.openapi_schema

    return custom_openapi


def inject_openapi_examples(openapi_schema: dict, app, logger) -> None:
    """Inject loaded examples into OpenAPI schema for key endpoints."""
    try:
        examples = getattr(app.state, "openapi_examples", {})
        if not examples:
            return

        responses = examples.get("responses", {})
        requests = examples.get("requests", {})
        endpoint_examples = {
            "/api/v1/costs/summary": {
                "response": responses.get("cost_summary", {}),
                "request_params": requests.get("cost_summary_query", {}),
            },
            "/api/v1/compliance/summary": {
                "response": responses.get("compliance_summary", {}),
                "request_params": requests.get("compliance_summary_query", {}),
            },
            "/api/v1/resources/{resource_id}/history": {
                "response": responses.get("resource_lifecycle_history", {}),
                "request_params": requests.get("resource_lifecycle_query", {}),
            },
        }

        for path, example_data in endpoint_examples.items():
            if path not in openapi_schema.get("paths", {}):
                continue
            for method, operation in openapi_schema["paths"][path].items():
                if method not in ("get", "post", "put", "patch", "delete"):
                    continue
                _add_response_example(operation, example_data.get("response"))
                _add_parameter_examples(operation, example_data.get("request_params"))
    except Exception as exc:
        logger.warning(f"Failed to inject OpenAPI examples: {exc}")


def _add_response_example(operation: dict, response_example) -> None:
    if not response_example or not isinstance(response_example, dict):
        return

    if "value" in response_example:
        example_value = response_example["value"]
    elif "example_response" in response_example:
        example_value = response_example["example_response"]
    else:
        example_value = response_example

    operation.setdefault("responses", {})
    operation["responses"].setdefault("200", {"description": "Successful response"})
    operation["responses"]["200"].setdefault(
        "content", {"application/json": {"schema": {"type": "object"}}}
    )
    json_content = operation["responses"]["200"]["content"]["application/json"]
    json_content["example"] = example_value

    if "summary" in response_example:
        json_content["schema"]["title"] = response_example["summary"]


def _add_parameter_examples(operation: dict, params_example) -> None:
    if not (isinstance(params_example, dict) and "value" in params_example):
        return

    for param_name, param_value in params_example["value"].items():
        for param in operation.get("parameters", []):
            if param.get("name") == param_name:
                param["example"] = param_value
                break
        else:
            operation.setdefault("parameters", []).append(
                {
                    "name": param_name,
                    "in": "query",
                    "schema": {"type": infer_schema_type(param_value)},
                    "example": param_value,
                }
            )


def infer_schema_type(value) -> str:
    """Infer JSON Schema type from a Python value."""
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return "string"
