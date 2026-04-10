# Security Headers Implementation

This document describes the comprehensive security headers implementation in the Azure Governance Platform, including their purpose, configuration, and troubleshooting.

## Overview

Security headers are HTTP response headers that help protect web applications from common attacks including:

- **Cross-Site Scripting (XSS)** - Malicious script injection
- **Clickjacking** - Trick users into clicking hidden elements
- **MIME sniffing** - Browser interpreting files as wrong types
- **Information leakage** - Unintended data exposure
- **Spectre attacks** - Cross-origin data leakage

The platform implements **12 security headers** with environment-specific configurations to balance security with functionality.

---

## Implemented Headers

### 1. Strict-Transport-Security (HSTS)
**Purpose:** Forces browsers to use HTTPS for all requests

**Behavior:**
- Development: 5 minutes max-age (allows quick iteration)
- Staging: 1 day max-age (testing flexibility)
- Production: 1 year max-age with preload (maximum security)

```http
Strict-Transport-Security: max-age=31536000; includeSubDomains; preload
```

### 2. Content-Security-Policy (CSP)
**Purpose:** Controls which resources (scripts, styles, images) the browser can load

**Behavior:**
- **Development:** Allows external resources, `unsafe-eval` for debugging
- **Staging:** Balanced - allows CDN resources, blocks inline scripts without nonce
- **Production:** Strict - self-hosted resources only

```http
Content-Security-Policy: default-src 'self'; script-src 'self' 'nonce-{nonce}'; ...
```

### 3. X-Content-Type-Options
**Purpose:** Prevents browser MIME type sniffing

```http
X-Content-Type-Options: nosniff
```

### 4. X-Frame-Options
**Purpose:** Prevents clickjacking by controlling iframe embedding

```http
X-Frame-Options: DENY
```

### 5. X-XSS-Protection
**Purpose:** Legacy XSS protection (for older browsers)

```http
X-XSS-Protection: 1; mode=block
```

### 6. Referrer-Policy
**Purpose:** Controls how much referrer information is sent

```http
Referrer-Policy: strict-origin-when-cross-origin
```

### 7. Permissions-Policy
**Purpose:** Restricts browser features (camera, microphone, etc.)

```http
Permissions-Policy: camera=(), microphone=(), geolocation=(), ...
```

### 8. Cross-Origin-Resource-Policy (CORP)
**Purpose:** Controls cross-origin resource loading

**Behavior:**
- Development: `cross-origin` (allows external resources)
- Staging/Production: `same-origin` (restrictive)

```http
Cross-Origin-Resource-Policy: same-origin
```

### 9. Cross-Origin-Opener-Policy (COOP)
**Purpose:** Isolates browsing context to prevent cross-window attacks

**Behavior:**
- Development: `unsafe-none` (allows popups)
- Staging: `same-origin-allow-popups` (allows popups, isolates otherwise)
- Production: `same-origin` (full isolation)

```http
Cross-Origin-Opener-Policy: same-origin
```

### 10. Cross-Origin-Embedder-Policy (COEP)
**Purpose:** Controls cross-origin resource embedding

**Behavior:**
- Development: `unsafe-none` (relaxed)
- Staging/Production: `require-corp` (requires CORP headers on resources)

```http
Cross-Origin-Embedder-Policy: require-corp
```

### 11. X-Permitted-Cross-Domain-Policies
**Purpose:** Controls Adobe Flash/Flex cross-domain access

```http
X-Permitted-Cross-Domain-Policies: none
```

### 12. Document-Policy
**Purpose:** Controls document-level features

```http
Document-Policy: force-load-at-top
```

---

## Environment-Specific Behavior

| Environment | HSTS max-age | Preload | CSP Strictness | CORP | COOP | COEP |
|-------------|--------------|---------|----------------|------|------|------|
| Development | 5 minutes (300s) | No | Relaxed - allows external resources, `unsafe-eval` | cross-origin | unsafe-none | unsafe-none |
| Staging | 1 day (86400s) | No | Balanced - allows CDN, nonce required | same-origin | same-origin-allow-popups | require-corp |
| Production | 1 year (31536000s) | Yes | Strict - self-hosted only | same-origin | same-origin | require-corp |

### Development Environment
Best for local development and debugging:
- Short HSTS allows HTTP testing
- Relaxed CSP supports development tools
- Permissive CORB/COOP/COEP allows external resources

### Staging Environment
Best for pre-production testing:
- Moderate HSTS for testing HTTPS enforcement
- Balanced CSP tests production-like policies
- Allows debugging while maintaining security

### Production Environment
Maximum security configuration:
- Long HSTS with preload submission ready
- Strict CSP prevents XSS attacks
- Full cross-origin isolation

---

## Configuration

### Using Environment Presets

```python
from app.core.security_headers import SecurityHeadersConfig, SecurityHeadersMiddleware

# Use environment preset
config = SecurityHeadersConfig.production()
middleware = SecurityHeadersMiddleware(app, config=config)
```

### Available Preset Methods

```python
# Environment-specific presets
config = SecurityHeadersConfig.development()  # Quick iteration
config = SecurityHeadersConfig.staging()      # Testing flexibility  
config = SecurityHeadersConfig.production()   # Maximum security

# Legacy security level presets (backward compatible)
config = SecurityHeadersConfig.strict()      # Most restrictive
config = SecurityHeadersConfig.balanced()      # Default
config = SecurityHeadersConfig.relaxed()      # Development only
```

### Custom Configuration

```python
from app.core.security_headers import SecurityHeadersConfig, SecurityHeadersMiddleware

# Create custom configuration
config = SecurityHeadersConfig(
    hsts_max_age=86400,
    hsts_include_subdomains=True,
    hsts_preload=False,
    permissions_policy="camera=(), microphone=()",
    corp_policy="same-origin",
    coop_policy="same-origin-allow-popups",
    coep_policy="require-corp",
    csp_directives={
        "default-src": "'self'",
        "script-src": "'self' 'nonce-{nonce}'",
        "style-src": "'self' 'unsafe-inline'",
    }
)

middleware = SecurityHeadersMiddleware(app, config=config)
```

### Skipping Paths

Some paths like `/metrics` skip security headers for compatibility:

```python
config = SecurityHeadersConfig(
    skip_paths=("/metrics", "/health", "/ready")
)
```

---

## Testing Headers Locally

### Using curl

```bash
# Check all security headers
curl -s -I http://localhost:8000/ | grep -i "strict\|csp\|x-"

# Full header inspection
curl -s -I http://localhost:8000/ | head -30
```

### Using Browser DevTools

1. Open browser DevTools (F12)
2. Go to Network tab
3. Refresh page
4. Click request → Headers tab → Response Headers

### Automated Testing

```python
# Test specific headers exist
def test_security_headers(client):
    response = client.get("/")
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert "Content-Security-Policy" in response.headers
    assert "Strict-Transport-Security" in response.headers
```

---

## Troubleshooting

### Common Issues

#### Issue: External resources blocked (images, fonts, scripts)
**Symptoms:** 404 or CSP errors in console

**Solutions:**
1. Check CSP directives in browser console
2. Add resource domains to CSP:
```python
config.csp_directives["img-src"] = "'self' data: https://cdn.example.com"
```
3. For development, use `SecurityHeadersConfig.development()`

#### Issue: "unsafe-inline" script errors
**Symptoms:** Scripts not executing, CSP violations

**Solutions:**
1. Use nonce-based script loading (automatic with middleware)
2. Access nonce in templates: `request.state.csp_nonce`
3. Add nonce to script tags: `<script nonce="{{ nonce }}">`

#### Issue: Popups blocked unexpectedly
**Symptoms:** OAuth flows, external links fail

**Solutions:**
1. Adjust COOP policy: `coop_policy="same-origin-allow-popups"`
2. For OAuth, use `noopener,noreferrer` on links

#### Issue: HSTS causing HTTPS errors locally
**Symptoms:** Browser redirects HTTP to HTTPS

**Solutions:**
1. Clear browser HSTS cache (chrome://net-internals/#hsts)
2. Use `SecurityHeadersConfig.development()` (5-minute max-age)
3. Test with incognito/private browsing mode

#### Issue: COEP blocking embedded resources
**Symptoms:** Cross-origin iframes, images not loading

**Solutions:**
1. Set `coep_policy="unsafe-none"` for development
2. Ensure embedded resources send CORP headers
3. Use `credentialless` COEP mode if supported

#### Issue: Permissions-Policy blocking features
**Symptoms:** Camera, microphone, geolocation denied

**Solutions:**
1. Update permissions policy to allow features:
```python
config.permissions_policy = "camera=(self), microphone=(self)"
```

### Debug Mode

Enable detailed logging:

```python
import logging
logging.getLogger("app.core.security_headers").setLevel(logging.DEBUG)
```

### Security Headers Checklist

Before production deployment, verify:

- [ ] All 12 headers present in responses
- [ ] HSTS max-age >= 31536000 for production
- [ ] CSP blocks inline scripts (nonce-based only)
- [ ] X-Frame-Options: DENY on all pages
- [ ] No sensitive data in Server header (minimized)
- [ ] Skip paths don't include sensitive endpoints
- [ ] Preload considered for HSTS (irreversible decision)

---

## References

- [OWASP Security Headers](https://owasp.org/www-project-secure-headers/)
- [MDN CSP Documentation](https://developer.mozilla.org/en-US/docs/Web/HTTP/CSP)
- [MDN HSTS Documentation](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Strict-Transport-Security)
- [web.dev Security Headers](https://web.dev/security-headers/)
- [HSTS Preload Submission](https://hstspreload.org/)
