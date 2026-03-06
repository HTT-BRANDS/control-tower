# Accessibility API Contract

**Version:** 1.0  
**Status:** Active  
**Last Updated:** March 6, 2026  
**Owner:** Experience Architect  
**Scope:** Azure Governance Platform API

---

## Table of Contents

1. [Overview](#overview)
2. [Why Accessibility Metadata Matters](#why-accessibility-metadata-matters)
3. [Error Response Contract](#error-response-contract)
4. [ARIA Metadata Specification](#aria-metadata-specification)
5. [Focus Management](#focus-management)
6. [Field-Level Errors](#field-level-errors)
7. [Success Responses](#success-responses)
8. [HTTP Status Code Mapping](#http-status-code-mapping)
9. [FastAPI Implementation Guide](#fastapi-implementation-guide)
10. [Frontend Integration Guide](#frontend-integration-guide)
11. [Testing Guide](#testing-guide)
12. [Error Code Reference](#error-code-reference)
13. [Migration Guide](#migration-guide)
14. [Best Practices](#best-practices)

---

## Overview

This document defines the **Accessibility API Contract** for the Azure Governance Platform. All API endpoints MUST return error responses that include accessibility metadata conforming to WCAG 2.2 Level AA requirements.

### Goals

1. **Enable assistive technology support** - Screen readers can announce errors appropriately
2. **Support focus management** - Guide users to error locations for quick correction
3. **Provide actionable guidance** - Include suggestions for error resolution
4. **Ensure consistency** - Standardized format across all API endpoints
5. **Meet compliance requirements** - Satisfy WCAG 2.2 and accessibility audits

### Scope

This contract applies to:

- All HTTP error responses (4xx, 5xx)
- Form validation errors
- Authentication/authorization failures
- Success responses that require user notification
- All API versions (v1 and future versions)

### Related Documents

- [JSON Schema Definition](./accessibility-error-schema.json)
- [API Documentation](../API.md)
- [WCAG 2.2 Compliance Guide](https://www.w3.org/WAI/WCAG22/quickref/)
- [ARIA Authoring Practices Guide](https://www.w3.org/WAI/ARIA/apg/)

---

## Why Accessibility Metadata Matters

### The Problem

Traditional API error responses only provide machine-readable error codes and messages:

```json
{
  "error": "VALIDATION_ERROR",
  "message": "Invalid email format"
}
```

**Issues:**
- Screen readers don't know how urgently to announce the error
- No guidance on which form field caused the error
- No instructions for keyboard-only users on where to focus
- Missing context for assistive technologies

### The Solution

Accessibility-enhanced responses include ARIA metadata:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid email format",
    "aria": {
      "live": "assertive",
      "atomic": true,
      "role": "alert"
    },
    "fields": [
      {
        "id": "email",
        "message": "Please enter a valid email address",
        "aria": {
          "describedBy": "email-hint",
          "errormessage": "email-error",
          "invalid": true
        }
      }
    ],
    "focus": {
      "target": "#email",
      "action": "set"
    }
  }
}
```

**Benefits:**
- Screen reader announces error immediately ("assertive")
- Frontend knows to set `aria-invalid="true"` on the email field
- Focus automatically moves to the problematic field
- Error message is programmatically linked via `aria-describedby`

### Impact on Users

| User Group | Without Metadata | With Metadata |
|------------|------------------|---------------|
| **Screen reader users** | May not hear error announcement | Error announced immediately and clearly |
| **Keyboard-only users** | Must manually find error location | Focus automatically moves to error |
| **Cognitive disabilities** | Generic error message | Specific field-level guidance |
| **Mobile users** | Must scroll to find errors | Focused directly on problem |
| **All users** | Trial-and-error fixing | Clear path to resolution |

---

## Error Response Contract

### Standard Structure

All error responses MUST follow this structure:

```json
{
  "error": {
    "code": "string",              // REQUIRED: Machine-readable error code
    "message": "string",           // REQUIRED: Human-readable message
    "details": "string",           // OPTIONAL: Additional context
    "aria": {                      // REQUIRED: ARIA metadata
      "live": "assertive|polite|off",
      "atomic": true|false,
      "relevant": "string",
      "role": "alert|status|log",
      "label": "string"
    },
    "fields": [],                  // OPTIONAL: Field-level errors
    "focus": {},                   // OPTIONAL: Focus management
    "suggestions": [],             // OPTIONAL: Suggested actions
    "help_url": "string",          // OPTIONAL: Documentation URL
    "request_id": "string",        // REQUIRED: Request identifier
    "timestamp": "string",         // REQUIRED: ISO 8601 timestamp
    "trace_id": "string"           // OPTIONAL: Distributed trace ID
  }
}
```

### Required Fields

#### `error.code`

- **Type:** String
- **Pattern:** `^[A-Z_]+$`
- **Description:** Machine-readable error code in SCREAMING_SNAKE_CASE
- **Examples:** `VALIDATION_ERROR`, `UNAUTHORIZED`, `NOT_FOUND`

#### `error.message`

- **Type:** String
- **Min Length:** 1
- **Description:** User-friendly error message suitable for display
- **Requirements:**
  - Written in plain language (reading level: Grade 8 or below)
  - Avoid technical jargon
  - Be concise but informative
  - Use active voice

**Good Examples:**
- ✅ "Please enter a valid email address."
- ✅ "Your session has expired. Please log in again."
- ✅ "This resource was not found."

**Bad Examples:**
- ❌ "Validation constraint violation on field 'email'"
- ❌ "HTTP 401: Unauthorized access denied"
- ❌ "NullPointerException in UserService.authenticate()"

#### `error.aria`

- **Type:** Object
- **Required Fields:** `live`
- **Description:** ARIA metadata for assistive technologies

#### `error.request_id`

- **Type:** String
- **Pattern:** `^[a-zA-Z0-9_-]+$`
- **Description:** Unique identifier for support and debugging
- **Format:** Use ULID or UUID for uniqueness

#### `error.timestamp`

- **Type:** String
- **Format:** ISO 8601 date-time (UTC)
- **Example:** `"2026-03-06T10:30:00Z"`

### Optional Fields

#### `error.details`

Additional technical context about the error. Use this for:
- Root cause explanation
- Aggregated summary (e.g., "3 fields contain errors")
- Next steps guidance

#### `error.fields`

Array of field-level validation errors. See [Field-Level Errors](#field-level-errors).

#### `error.focus`

Focus management instructions. See [Focus Management](#focus-management).

#### `error.suggestions`

Array of suggested actions to resolve the error. Each suggestion includes:

```json
{
  "action": "retry",
  "label": "Try again",
  "href": "/api/v1/resource",
  "method": "GET"
}
```

#### `error.help_url`

URL to documentation explaining this error and resolution steps.

#### `error.trace_id`

Distributed tracing ID for correlating logs across services. Use OpenTelemetry format.

---

## ARIA Metadata Specification

### Overview

ARIA (Accessible Rich Internet Applications) metadata tells assistive technologies **how** and **when** to announce changes to users.

### `aria.live`

**Purpose:** Controls the urgency of announcements.

| Value | Behavior | Use Cases |
|-------|----------|----------|
| `"off"` | No announcement | Background processes, non-critical updates |
| `"polite"` | Announce when user is idle | Success messages, informational notices, 404 errors |
| `"assertive"` | Interrupt and announce immediately | Validation errors, authentication failures, critical alerts |

**Decision Tree:**

```
Is this error blocking the user's workflow?
├─ YES → Use "assertive"
│   Examples: Login failed, form validation error, payment declined
│
└─ NO → Use "polite"
    Examples: Resource not found, background sync failed, optional field warning
```

**Default:** Use `"assertive"` for all error responses unless specifically documented otherwise.

### `aria.atomic`

**Purpose:** Determines whether the entire region is announced or just the change.

- `true` (default): Announce the entire error message
- `false`: Announce only the changed portion

**Recommendation:** Always use `true` for error messages to ensure complete context.

### `aria.relevant`

**Purpose:** Specifies what types of changes trigger announcements.

- `"additions"`: Announce added nodes
- `"text"`: Announce text changes
- `"removals"`: Announce removed nodes
- `"all"`: Announce all changes

**Default:** `"additions text"` (announce when content is added or text changes)

### `aria.role`

**Purpose:** Identifies the type of notification.

| Role | Meaning | Use Cases |
|------|---------|----------|
| `"alert"` | Important, time-sensitive information | Errors, critical warnings |
| `"status"` | Advisory information | Success messages, process completion |
| `"log"` | Sequential updates | Multi-step process updates |

**Recommendation:**
- Use `"alert"` for 4xx and 5xx errors
- Use `"status"` for informational responses

### `aria.label`

**Purpose:** Provides an accessible name for the error region.

**Examples:**
- `"Validation errors"`
- `"Authentication error"`
- `"Server error notification"`

---

## Focus Management

### Purpose

When an error occurs, keyboard and screen reader users need to know **where** to go to fix it. Focus management provides this guidance.

### Structure

```json
{
  "focus": {
    "target": "#email",
    "action": "set"
  }
}
```

### `focus.target`

**Type:** String (CSS selector or element ID)

**Examples:**
- `"#email"` - Focus the email input field
- `".error-summary"` - Focus the error summary container
- `"#main-content"` - Focus the main content region

### `focus.action`

**Type:** Enum

| Action | Behavior | Use Case |
|--------|----------|----------|
| `"set"` | Move focus to the target element | Single field error, specific correction needed |
| `"trap"` | Trap focus within a region (modal behavior) | Modal dialogs, critical errors requiring immediate action |
| `"release"` | Release focus trap | Dismiss modal, return to normal navigation |

### Implementation Rules

1. **Single Field Error:** Set `target` to the field ID
   ```json
   {"focus": {"target": "#password", "action": "set"}}
   ```

2. **Multiple Field Errors:** Set `target` to the error summary
   ```json
   {"focus": {"target": "#error-summary", "action": "set"}}
   ```

3. **Critical Errors:** Use focus trap for blocking errors
   ```json
   {"focus": {"target": "#critical-error-modal", "action": "trap"}}
   ```

4. **Informational Errors:** No focus change needed
   ```json
   {"focus": null}
   ```

---

## Field-Level Errors

### Purpose

Form validation errors must specify **which fields** are invalid and **what's wrong** with each.

### Structure

```json
{
  "fields": [
    {
      "id": "email",
      "name": "email",
      "label": "Email Address",
      "message": "Please enter a valid email address",
      "value": "not-an-email",
      "aria": {
        "describedBy": "email-hint",
        "errormessage": "email-error",
        "invalid": true
      },
      "constraints": {
        "required": true,
        "format": "email"
      }
    }
  ]
}
```

### Required Fields

#### `id`

- **Type:** String
- **Description:** Matches the HTML `id` attribute of the input field
- **Requirement:** MUST be unique within the form

#### `message`

- **Type:** String
- **Description:** User-friendly error message specific to this field
- **Requirements:**
  - Explain what's wrong
  - Suggest how to fix it
  - Avoid technical jargon

**Good Examples:**
- ✅ "Please enter a valid email address (e.g., user@example.com)"
- ✅ "Password must be at least 8 characters long"
- ✅ "This field is required"

**Bad Examples:**
- ❌ "Invalid"
- ❌ "Validation failed"
- ❌ "Pattern mismatch: ^[a-z]+$"

### Optional Fields

#### `name`

The field's `name` attribute (may differ from `id`).

#### `label`

Human-readable field label for context in error summaries.

#### `value`

The submitted value (sanitized for security). Useful for debugging but avoid exposing sensitive data.

#### `aria`

ARIA attributes for the field:

- `describedBy`: ID of hint text element
- `errormessage`: ID of error message element
- `invalid`: Always `true` for field errors

#### `constraints`

Validation constraints that failed:

```json
{
  "required": true,
  "min_length": 8,
  "max_length": 100,
  "pattern": "^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$",
  "format": "email",
  "min": 0,
  "max": 100
}
```

### Example: Multiple Field Errors

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Please correct the errors below",
    "details": "The form contains 3 fields with validation errors.",
    "aria": {
      "live": "assertive",
      "atomic": true,
      "role": "alert"
    },
    "fields": [
      {
        "id": "email",
        "message": "Please enter a valid email address",
        "aria": {"describedBy": "email-hint", "invalid": true}
      },
      {
        "id": "password",
        "message": "Password must be at least 8 characters",
        "aria": {"describedBy": "password-requirements", "invalid": true}
      },
      {
        "id": "tenant_id",
        "message": "Please select a tenant",
        "aria": {"invalid": true}
      }
    ],
    "focus": {"target": "#email", "action": "set"},
    "request_id": "req_abc123",
    "timestamp": "2026-03-06T10:30:00Z"
  }
}
```

---

## Success Responses

### Purpose

Success responses that require user notification (e.g., "Resource created", "Action completed") should also include ARIA metadata.

### Structure

```json
{
  "data": {
    "id": "tenant-123",
    "name": "Contoso Ltd.",
    "status": "active"
  },
  "message": {
    "text": "Tenant created successfully",
    "aria": {
      "live": "polite",
      "role": "status"
    }
  }
}
```

### Guidelines

1. **Use `"polite"`** - Success messages are informational, not urgent
2. **Use `role="status"`** - Indicates advisory information
3. **Include descriptive text** - "Tenant created successfully" is better than "Success"
4. **Optional for GET requests** - Only include for actions that modify state

### Example Use Cases

| Action | Success Message |
|--------|----------------|
| POST /tenants | "Tenant created successfully" |
| PUT /users/{id} | "User profile updated" |
| DELETE /resources/{id} | "Resource deleted" |
| POST /sync/start | "Synchronization started" |
| POST /auth/logout | "You have been logged out" |

---

## HTTP Status Code Mapping

### ARIA Live Settings by Status Code

| Status Code | Category | Default `aria.live` | Rationale |
|-------------|----------|---------------------|----------|
| **400** | Bad Request | `assertive` | User input error, needs immediate correction |
| **401** | Unauthorized | `assertive` | Blocks workflow, requires login |
| **403** | Forbidden | `assertive` | Blocks workflow, permission issue |
| **404** | Not Found | `polite` | Informational, doesn't block all workflows |
| **409** | Conflict | `assertive` | User action needed to resolve |
| **422** | Unprocessable | `assertive` | Validation error, similar to 400 |
| **429** | Rate Limited | `polite` | Temporary, will resolve automatically |
| **500** | Server Error | `assertive` | Unexpected, user should retry or contact support |
| **503** | Service Unavailable | `assertive` | Service down, critical information |

### Error Code to HTTP Status Mapping

| Error Code | HTTP Status | Message Template |
|------------|-------------|------------------|
| `VALIDATION_ERROR` | 400 | "Please check your input and try again." |
| `REQUIRED_FIELD` | 400 | "{field} is required." |
| `INVALID_FORMAT` | 400 | "{field} format is invalid." |
| `UNAUTHORIZED` | 401 | "Authentication is required to access this resource." |
| `TOKEN_EXPIRED` | 401 | "Your session has expired. Please log in again." |
| `FORBIDDEN` | 403 | "You don't have permission to access this resource." |
| `NOT_FOUND` | 404 | "The requested resource was not found." |
| `CONFLICT` | 409 | "This resource already exists or conflicts with an existing resource." |
| `RATE_LIMITED` | 429 | "Too many requests. Please try again later." |
| `INTERNAL_ERROR` | 500 | "An unexpected error occurred. Please try again later." |
| `SERVICE_UNAVAILABLE` | 503 | "The service is temporarily unavailable. Please try again later." |

---

## FastAPI Implementation Guide

### Step 1: Create Exception Classes

Create a new file `app/core/exceptions.py`:

```python
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from datetime import datetime
from fastapi import Request
import uuid

class AriaMetadata(BaseModel):
    """ARIA accessibility metadata."""
    live: str = "assertive"
    atomic: bool = True
    relevant: str = "additions text"
    role: Optional[str] = "alert"
    label: Optional[str] = None

class FocusInstruction(BaseModel):
    """Focus management instructions."""
    target: str
    action: str = "set"

class FieldError(BaseModel):
    """Field-level validation error."""
    id: str
    name: Optional[str] = None
    label: Optional[str] = None
    message: str
    value: Optional[str] = None
    aria: Optional[Dict[str, Any]] = None
    constraints: Optional[Dict[str, Any]] = None

class Suggestion(BaseModel):
    """Suggested action to resolve error."""
    action: str
    label: str
    href: Optional[str] = None
    method: str = "GET"

class AccessibilityException(Exception):
    """Base exception with accessibility metadata."""
    
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        details: Optional[str] = None,
        fields: Optional[List[FieldError]] = None,
        focus: Optional[FocusInstruction] = None,
        suggestions: Optional[List[Suggestion]] = None,
        help_url: Optional[str] = None,
        request: Optional[Request] = None
    ):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details
        self.fields = fields or []
        self.focus = focus
        self.suggestions = suggestions or []
        self.help_url = help_url
        self.request_id = str(uuid.uuid4())
        self.timestamp = datetime.utcnow().isoformat() + "Z"
        super().__init__(message)
    
    def to_response(self) -> Dict[str, Any]:
        """Convert to JSON response."""
        aria = self._get_aria_metadata()
        
        response = {
            "error": {
                "code": self.code,
                "message": self.message,
                "aria": {
                    "live": aria.live,
                    "atomic": aria.atomic,
                    "relevant": aria.relevant,
                },
                "request_id": self.request_id,
                "timestamp": self.timestamp,
            }
        }
        
        if aria.role:
            response["error"]["aria"]["role"] = aria.role
        if aria.label:
            response["error"]["aria"]["label"] = aria.label
        
        if self.details:
            response["error"]["details"] = self.details
        
        if self.fields:
            response["error"]["fields"] = [
                {
                    "id": f.id,
                    "name": f.name,
                    "label": f.label,
                    "message": f.message,
                    "value": f.value,
                    "aria": f.aria or {"invalid": True},
                    "constraints": f.constraints,
                }
                for f in self.fields
            ]
        
        if self.focus:
            response["error"]["focus"] = {
                "target": self.focus.target,
                "action": self.focus.action,
            }
        
        if self.suggestions:
            response["error"]["suggestions"] = [
                {
                    "action": s.action,
                    "label": s.label,
                    "href": s.href,
                    "method": s.method,
                }
                for s in self.suggestions
            ]
        
        if self.help_url:
            response["error"]["help_url"] = self.help_url
        
        return response
    
    def _get_aria_metadata(self) -> AriaMetadata:
        """Determine ARIA metadata based on status code."""
        if self.status_code == 404:
            return AriaMetadata(live="polite", role="status")
        elif self.status_code == 429:
            return AriaMetadata(live="polite", role="status")
        else:
            return AriaMetadata(live="assertive", role="alert")

class ValidationException(AccessibilityException):
    """Validation error with field-level details."""
    
    def __init__(self, fields: List[FieldError], **kwargs):
        # Determine focus target (first field with error)
        focus = FocusInstruction(target=f"#{fields[0].id}") if fields else None
        
        super().__init__(
            code="VALIDATION_ERROR",
            message="Please correct the errors below.",
            status_code=400,
            details=f"The form contains {len(fields)} field(s) with validation errors.",
            fields=fields,
            focus=focus,
            **kwargs
        )
```

### Step 2: Create Exception Handler

Create `app/core/error_handlers.py`:

```python
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException
from app.core.exceptions import AccessibilityException
import logging

logger = logging.getLogger(__name__)

async def accessibility_exception_handler(
    request: Request,
    exc: AccessibilityException
) -> JSONResponse:
    """Handle accessibility exceptions."""
    
    logger.error(
        f"Accessibility exception: {exc.code}",
        extra={
            "request_id": exc.request_id,
            "code": exc.code,
            "status_code": exc.status_code,
            "path": request.url.path,
        }
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_response()
    )

async def http_exception_handler(
    request: Request,
    exc: HTTPException
) -> JSONResponse:
    """Convert standard HTTP exceptions to accessibility format."""
    
    # Map to accessibility exception
    code_map = {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        409: "CONFLICT",
        422: "VALIDATION_ERROR",
        429: "RATE_LIMITED",
        500: "INTERNAL_ERROR",
        503: "SERVICE_UNAVAILABLE",
    }
    
    mapped = AccessibilityException(
        code=code_map.get(exc.status_code, "UNKNOWN_ERROR"),
        message=str(exc.detail),
        status_code=exc.status_code,
        request=request
    )
    
    return await accessibility_exception_handler(request, mapped)

def register_error_handlers(app):
    """Register all error handlers with FastAPI app."""
    
    app.add_exception_handler(AccessibilityException, accessibility_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
```

### Step 3: Register Handlers in `main.py`

```python
from app.core.error_handlers import register_error_handlers

app = FastAPI(title="Azure Governance Platform")

# Register error handlers
register_error_handlers(app)
```

### Step 4: Use in Route Handlers

```python
from fastapi import APIRouter, HTTPException
from app.core.exceptions import ValidationException, FieldError, AccessibilityException

router = APIRouter()

@router.post("/api/v1/tenants")
async def create_tenant(tenant_data: dict):
    # Validate input
    errors = []
    
    if not tenant_data.get("name"):
        errors.append(FieldError(
            id="name",
            name="name",
            label="Tenant Name",
            message="Tenant name is required.",
            aria={"invalid": True, "describedBy": "name-hint"},
            constraints={"required": True}
        ))
    
    if not tenant_data.get("tenant_id"):
        errors.append(FieldError(
            id="tenant_id",
            name="tenant_id",
            label="Tenant ID",
            message="Tenant ID is required.",
            aria={"invalid": True},
            constraints={"required": True}
        ))
    
    if errors:
        raise ValidationException(fields=errors)
    
    # Create tenant...
    return {"data": {"id": "tenant-123"}}
```

---

## Frontend Integration Guide

### Step 1: Create Error Handler Class

Create `static/js/error-handler.js`:

```javascript
class AccessibilityErrorHandler {
  constructor() {
    this.errorContainer = null;
    this.setup();
  }
  
  setup() {
    this.createErrorContainer();
    this.interceptFetch();
  }
  
  createErrorContainer() {
    this.errorContainer = document.createElement('div');
    this.errorContainer.id = 'accessibility-error-container';
    this.errorContainer.setAttribute('role', 'region');
    this.errorContainer.setAttribute('aria-live', 'assertive');
    this.errorContainer.setAttribute('aria-atomic', 'true');
    this.errorContainer.setAttribute('hidden', '');
    document.body.insertBefore(this.errorContainer, document.body.firstChild);
  }
  
  interceptFetch() {
    const originalFetch = window.fetch;
    
    window.fetch = async (...args) => {
      const response = await originalFetch(...args);
      
      if (!response.ok) {
        try {
          const errorData = await response.json();
          if (errorData.error) {
            this.handleErrorResponse(errorData.error);
          }
        } catch (e) {
          // Not JSON response
        }
      }
      
      return response;
    };
  }
  
  handleErrorResponse(error) {
    this.renderError(error);
    this.applyFieldErrors(error.fields || []);
    this.setFocus(error);
  }
  
  renderError(error) {
    const container = this.errorContainer;
    container.setAttribute('aria-live', error.aria?.live || 'assertive');
    
    container.innerHTML = `
      <div class="error-summary" role="alert" tabindex="-1" id="error-summary">
        <h2>${this.escapeHtml(error.message)}</h2>
        ${error.details ? `<p>${this.escapeHtml(error.details)}</p>` : ''}
        ${this.renderFieldErrors(error.fields || [])}
      </div>
    `;
    
    container.removeAttribute('hidden');
  }
  
  renderFieldErrors(fields) {
    if (!fields.length) return '';
    
    return `
      <ul class="error-list">
        ${fields.map(f => `
          <li>
            <a href="#${f.id}">${this.escapeHtml(f.message)}</a>
          </li>
        `).join('')}
      </ul>
    `;
  }
  
  applyFieldErrors(fields) {
    fields.forEach(field => {
      const element = document.getElementById(field.id);
      if (element) {
        element.setAttribute('aria-invalid', 'true');
        if (field.aria?.describedBy) {
          element.setAttribute('aria-describedby', field.aria.describedBy);
        }
        element.classList.add('input--error');
      }
    });
  }
  
  setFocus(error) {
    if (error.focus?.target) {
      const target = document.querySelector(error.focus.target);
      if (target) {
        target.focus();
      }
    } else if (error.fields?.length) {
      const firstField = document.getElementById(error.fields[0].id);
      if (firstField) firstField.focus();
    } else {
      const summary = document.getElementById('error-summary');
      if (summary) summary.focus();
    }
  }
  
  clearErrors() {
    this.errorContainer.setAttribute('hidden', '');
    this.errorContainer.innerHTML = '';
    
    document.querySelectorAll('.input--error').forEach(el => {
      el.classList.remove('input--error');
      el.removeAttribute('aria-invalid');
    });
  }
  
  escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
  window.errorHandler = new AccessibilityErrorHandler();
});
```

### Step 2: Add CSS Styles

Create `static/css/error-styles.css`:

```css
#accessibility-error-container {
  position: relative;
  margin-bottom: 1rem;
}

.error-summary {
  background-color: #f8d7da;
  border: 2px solid #dc3545;
  border-radius: 0.25rem;
  padding: 1rem;
  margin-bottom: 1rem;
}

.error-summary h2 {
  color: #721c24;
  font-size: 1.25rem;
  margin: 0 0 0.5rem 0;
}

.error-summary p {
  color: #721c24;
  margin: 0.5rem 0;
}

.error-list {
  margin: 0.5rem 0 0 1.5rem;
  padding: 0;
}

.error-list li {
  color: #721c24;
  margin: 0.25rem 0;
}

.error-list a {
  color: #721c24;
  text-decoration: underline;
  font-weight: 600;
}

.error-list a:hover,
.error-list a:focus {
  color: #491217;
}

.input--error {
  border-color: #dc3545 !important;
  background-color: #fff5f5;
}

.input--error:focus {
  box-shadow: 0 0 0 0.2rem rgba(220, 53, 69, 0.25);
}

.error-message {
  display: block;
  color: #dc3545;
  font-size: 0.875rem;
  margin-top: 0.25rem;
}
```

---

## Testing Guide

### Unit Tests

Test exception classes:

```python
import pytest
from app.core.exceptions import AccessibilityException, ValidationException, FieldError

class TestAccessibilityException:
    def test_basic_error_response(self):
        exc = AccessibilityException(
            code="VALIDATION_ERROR",
            message="Invalid input",
            status_code=400
        )
        
        response = exc.to_response()
        
        assert response["error"]["code"] == "VALIDATION_ERROR"
        assert response["error"]["message"] == "Invalid input"
        assert response["error"]["aria"]["live"] == "assertive"
        assert "request_id" in response["error"]
        assert "timestamp" in response["error"]
    
    def test_validation_exception_with_fields(self):
        fields = [
            FieldError(id="email", message="Invalid email format"),
            FieldError(id="password", message="Password too short"),
        ]
        
        exc = ValidationException(fields=fields)
        response = exc.to_response()
        
        assert len(response["error"]["fields"]) == 2
        assert response["error"]["focus"]["target"] == "#email"
    
    def test_404_uses_polite_aria(self):
        exc = AccessibilityException(
            code="NOT_FOUND",
            message="Resource not found",
            status_code=404
        )
        
        response = exc.to_response()
        assert response["error"]["aria"]["live"] == "polite"
```

### Integration Tests

Test API endpoints:

```python
from fastapi.testclient import TestClient

class TestErrorContract:
    def test_validation_error_structure(self, client: TestClient):
        response = client.post("/api/v1/tenants", json={})
        
        assert response.status_code == 400
        data = response.json()
        
        # Verify structure
        assert "error" in data
        assert "code" in data["error"]
        assert "message" in data["error"]
        assert "aria" in data["error"]
        assert "request_id" in data["error"]
        assert "timestamp" in data["error"]
        
        # Verify ARIA metadata
        assert data["error"]["aria"]["live"] in ["off", "polite", "assertive"]
        assert isinstance(data["error"]["aria"]["atomic"], bool)
    
    def test_field_errors_include_aria(self, client: TestClient):
        response = client.post("/api/v1/tenants", json={"name": ""})
        
        data = response.json()
        
        if "fields" in data["error"]:
            for field in data["error"]["fields"]:
                assert "id" in field
                assert "message" in field
                assert "aria" in field
                assert field["aria"]["invalid"] is True
```

### End-to-End Tests

Test with assistive technology simulators:

```javascript
// tests/e2e/test_accessibility_errors.js
describe('Accessibility Error Handling', () => {
  it('should announce validation errors to screen readers', async () => {
    // Submit invalid form
    await page.fill('#email', 'invalid-email');
    await page.click('button[type="submit"]');
    
    // Check error container exists
    const errorContainer = await page.locator('#accessibility-error-container');
    await expect(errorContainer).toBeVisible();
    
    // Check ARIA attributes
    await expect(errorContainer).toHaveAttribute('aria-live', 'assertive');
    await expect(errorContainer).toHaveAttribute('aria-atomic', 'true');
    
    // Check field has aria-invalid
    const emailInput = await page.locator('#email');
    await expect(emailInput).toHaveAttribute('aria-invalid', 'true');
  });
  
  it('should set focus to first error field', async () => {
    await page.fill('#email', 'invalid');
    await page.click('button[type="submit"]');
    
    // Check focus is on email field
    const focused = await page.evaluate(() => document.activeElement.id);
    expect(focused).toBe('email');
  });
});
```

---

## Error Code Reference

### Validation Errors (400)

| Code | Message Template | Use Case |
|------|-----------------|----------|
| `VALIDATION_ERROR` | "Please correct the errors below." | Generic form validation |
| `REQUIRED_FIELD` | "{field} is required." | Missing required field |
| `INVALID_FORMAT` | "{field} format is invalid." | Pattern mismatch |
| `TOO_SHORT` | "{field} must be at least {min} characters." | Length constraint |
| `TOO_LONG` | "{field} must be no more than {max} characters." | Length constraint |
| `INVALID_EMAIL` | "Please enter a valid email address." | Email validation |
| `INVALID_UUID` | "Invalid identifier format." | UUID validation |

### Authentication Errors (401)

| Code | Message Template |
|------|------------------|
| `UNAUTHORIZED` | "Authentication is required to access this resource." |
| `TOKEN_EXPIRED` | "Your session has expired. Please log in again." |
| `INVALID_CREDENTIALS` | "The email or password you entered is incorrect." |
| `MFA_REQUIRED` | "Multi-factor authentication is required." |

### Authorization Errors (403)

| Code | Message Template |
|------|------------------|
| `FORBIDDEN` | "You don't have permission to access this resource." |
| `INSUFFICIENT_PERMISSIONS` | "Your account doesn't have the required permissions." |
| `TENANT_ACCESS_DENIED` | "You don't have access to this tenant." |

### Resource Errors (404, 409)

| Code | Message Template |
|------|------------------|
| `NOT_FOUND` | "The requested resource was not found." |
| `TENANT_NOT_FOUND` | "Tenant '{id}' was not found." |
| `CONFLICT` | "This resource already exists or conflicts with an existing resource." |

### Server Errors (500, 503)

| Code | Message Template |
|------|------------------|
| `INTERNAL_ERROR` | "An unexpected error occurred. Please try again later." |
| `SERVICE_UNAVAILABLE` | "The service is temporarily unavailable. Please try again later." |
| `TIMEOUT` | "The request timed out. Please try again." |

---

## Migration Guide

### For Existing Endpoints

1. **Identify endpoints returning errors** - Use `grep -r "HTTPException" app/api/routes/`
2. **Replace with `AccessibilityException`**
3. **Add field-level errors for validation**
4. **Test with screen reader**

### Example Migration

**Before:**

```python
@router.post("/api/v1/tenants")
async def create_tenant(data: dict):
    if not data.get("name"):
        raise HTTPException(status_code=400, detail="Name is required")
    # ...
```

**After:**

```python
@router.post("/api/v1/tenants")
async def create_tenant(data: dict):
    errors = []
    
    if not data.get("name"):
        errors.append(FieldError(
            id="name",
            message="Tenant name is required.",
            aria={"invalid": True},
            constraints={"required": True}
        ))
    
    if errors:
        raise ValidationException(fields=errors)
    # ...
```

---

## Best Practices

### 1. Write User-Friendly Messages

✅ **Good:**
- "Please enter a valid email address (e.g., user@example.com)"
- "Password must be at least 8 characters long"
- "This field is required"

❌ **Bad:**
- "Invalid"
- "Validation failed"
- "Error: NullPointerException"

### 2. Always Include ARIA Metadata

Every error response MUST include `aria` object with at least `live` property.

### 3. Provide Actionable Suggestions

Include `suggestions` array with specific actions:

```json
{
  "suggestions": [
    {"action": "retry", "label": "Try again", "href": "/resource"},
    {"action": "support", "label": "Contact support", "href": "/support"}
  ]
}
```

### 4. Use Consistent Error Codes

Follow the [Error Code Reference](#error-code-reference) for standard codes.

### 5. Test with Real Assistive Technology

Use screen readers (NVDA, JAWS, VoiceOver) to verify announcements.

### 6. Include Request IDs

Always include `request_id` for support and debugging.

### 7. Focus Management

- Single field error → Focus the field
- Multiple errors → Focus error summary
- Critical errors → Use focus trap

---

## References

- **JSON Schema:** [accessibility-error-schema.json](./accessibility-error-schema.json)
- **WCAG 2.2:** https://www.w3.org/WAI/WCAG22/quickref/
- **ARIA Live Regions:** https://www.w3.org/WAI/ARIA/apg/patterns/alert/
- **ARIA Error Pattern:** https://www.w3.org/WAI/tutorials/forms/notifications/
- **FastAPI Docs:** https://fastapi.tiangolo.com/tutorial/handling-errors/

---

**Document Version:** 1.0  
**Last Reviewed:** March 6, 2026  
**Next Review:** June 6, 2026
