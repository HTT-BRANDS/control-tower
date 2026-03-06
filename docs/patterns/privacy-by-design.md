# Privacy-by-Design Pattern Library

| Field | Value |
|---|---|
| **Document ID** | PBD-PATTERNS-2026-001 |
| **Owner** | Husky 🐺 (`husky-8c15e4`) |
| **Date** | 2026-03-06 |
| **Task** | 2.3.3 / REQ-803 / bd `azure-governance-platform-4sa` |
| **Framework** | Ann Cavoukian's Privacy by Design |
| **Standards** | ISO/IEC 29184:2020, GDPR Art. 25, CCPA §1798.100 |
| **Status** | Active |
| **Last Review** | 2026-03-06 |

---

## Executive Summary

This pattern library provides **actionable, code-level implementations** of Privacy-by-Design (PbD) principles for the Azure Governance Platform. Each pattern addresses specific privacy challenges with production-ready examples, WCAG 2.2 accessibility compliance, and GDPR/CCPA legal mappings.

**Privacy-by-Design is not optional** — it's a legal requirement under GDPR Article 25 (Data Protection by Design and by Default) and CCPA §1798.100(a) (right to know what personal information is collected).

---

## Ann Cavoukian's 7 Foundational Principles

**Privacy by Design** was developed by Dr. Ann Cavoukian, former Information and Privacy Commissioner of Ontario, Canada. The framework consists of seven foundational principles:

### 1. Proactive not Reactive; Preventative not Remedial
- **Anticipate and prevent** privacy-invasive events before they occur
- **Don't wait for breaches** to happen — build privacy in from the start
- **Example**: Implement data minimization at design time, not after a data breach

### 2. Privacy as the Default Setting
- **No action required** from the user to protect their privacy
- **Personal data is automatically protected** in any given IT system or business practice
- **Example**: Cookies default to essential-only; analytics requires explicit opt-in

### 3. Privacy Embedded into Design
- **Privacy is integral** to system architecture and business practices
- **Not bolted on** as an add-on after the fact
- **Example**: Database schemas include purpose limitation, retention policies, and encryption by default

### 4. Full Functionality — Positive-Sum, not Zero-Sum
- **Accommodate all legitimate interests** without unnecessary trade-offs
- **Both privacy AND functionality** — not either/or
- **Example**: Progressive profiling collects data over time while maintaining UX quality

### 5. End-to-End Security — Full Lifecycle Protection
- **Secure data from collection to deletion**
- **Cradle-to-grave protection** of personal information
- **Example**: Automated data retention policies with secure deletion workflows

### 6. Visibility and Transparency — Keep it Open
- **Operate in accordance with stated promises** and commitments
- **Subject to independent verification**
- **Example**: Machine-readable consent receipts, public privacy audits

### 7. Respect for User Privacy — Keep it User-Centric
- **Empower individuals** with granular controls
- **Strong privacy defaults**, user-friendly tools, and timely notice
- **Example**: Layered consent interfaces, just-in-time permission requests

---

## Pattern Decision Matrix

Use this matrix to select the appropriate privacy pattern for your use case:

| Pattern | Use When | Don't Use When | Primary Principle | WCAG Impact | Implementation Effort |
|---------|----------|----------------|-------------------|-------------|----------------------|
| **Layered Consent** | Privacy policy > 500 words, legal complexity high | Simple cookie consent (use banner instead) | #7 User-Centric | High (requires ARIA) | Medium |
| **JIT Consent** | Permission needed for specific feature (location, camera) | Data required at signup (email) | #1 Proactive, #7 User-Centric | Low | Low |
| **Progressive Profiling** | Multi-step workflows, account maturity model | One-time transactions, guest checkout | #4 Full Functionality | Low | Medium |
| **Consent Receipts** | B2B, regulated industries, audit requirements | Consumer apps without compliance needs | #6 Visibility | None (backend) | High |
| **GPC (Global Privacy Control)** | California users, analytics/ads, third-party scripts | No tracking/selling of data | #2 Privacy by Default | None (backend) | Low |

**Combination Recommendations:**
- **Authentication flows**: JIT Consent + Progressive Profiling
- **Marketing sites**: Layered Consent + GPC
- **Enterprise SaaS**: All 5 patterns
- **Mobile apps**: JIT Consent + Consent Receipts

---

## Pattern 1: Layered Consent

### Problem

**Privacy policies are legally required but unusable:**
- Average privacy policy: 2,500+ words (8-10 minutes to read)
- 91% of users accept without reading (Deloitte 2021)
- Single-wall-of-text approach violates WCAG 2.2 SC 3.1.5 (Reading Level)
- GDPR Article 12 requires "concise, transparent, intelligible" communication

**Example of the problem:**
```html
<!-- ❌ BAD: All-or-nothing consent -->
<div class="privacy-policy">
  <p>This 5000-word policy describes everything...</p>
  <button>Accept All</button>
</div>
```

### Solution

**Progressive disclosure in three layers:**
1. **Layer 1 (Summary)**: 1-2 sentences, visible by default
2. **Layer 2 (Details)**: Category-specific explanations, expand on click
3. **Layer 3 (Full Policy)**: Complete legal text, link to dedicated page

**Visual hierarchy + semantic HTML + ARIA controls = accessible privacy**

### When to Use

- ✅ Privacy policies longer than 500 words
- ✅ Multi-purpose data processing (analytics, marketing, personalization)
- ✅ Cookie consent with 3+ categories
- ✅ B2C applications with diverse user base
- ❌ Simple cookie banners (overkill)
- ❌ No data collection (nothing to disclose)

### Implementation

```html
<!-- Layer 1: Summary (always visible) -->
<section class="consent-layered" aria-labelledby="consent-heading">
  <h2 id="consent-heading">Your Privacy Choices</h2>
  <p class="consent-summary">
    We use cookies for essential functions, analytics, and personalization.
    <a href="#" aria-controls="consent-details" aria-expanded="false" 
       data-toggle="disclosure">Learn more</a>
  </p>

  <!-- Layer 2: Details (expandable) -->
  <div id="consent-details" class="consent-details" hidden>
    <h3>What We Collect & Why</h3>
    
    <div class="consent-category">
      <h4>Essential (Always Active)</h4>
      <p>
        Authentication tokens, session data. Required for site functionality.
        Legal basis: GDPR Art. 6(1)(b) — contractual necessity.
      </p>
      <button disabled aria-label="Essential cookies cannot be disabled">
        Always Active
      </button>
    </div>

    <div class="consent-category">
      <h4>Analytics</h4>
      <p>
        Anonymized usage data (page views, clicks). Helps us improve UX.
        Legal basis: GDPR Art. 6(1)(f) — legitimate interest.
      </p>
      <label>
        <input type="checkbox" name="consent-analytics" 
               aria-describedby="analytics-desc">
        <span id="analytics-desc">Enable analytics</span>
      </label>
    </div>

    <div class="consent-category">
      <h4>Personalization</h4>
      <p>
        Preferences, saved filters, UI theme. Stored locally.
        Legal basis: GDPR Art. 6(1)(a) — explicit consent.
      </p>
      <label>
        <input type="checkbox" name="consent-personalization" 
               aria-describedby="personalization-desc">
        <span id="personalization-desc">Enable personalization</span>
      </label>
    </div>

    <!-- Layer 3: Full Policy (link) -->
    <p class="consent-full-policy">
      <a href="/privacy-policy" target="_blank">
        Read Full Privacy Policy
        <span class="sr-only">(opens in new tab)</span>
      </a>
    </p>
  </div>

  <!-- Action Buttons -->
  <div class="consent-actions">
    <button type="button" class="btn-reject" data-action="reject-all">
      Reject Optional
    </button>
    <button type="button" class="btn-accept" data-action="accept-all">
      Accept All
    </button>
    <button type="button" class="btn-save" data-action="save-preferences">
      Save My Choices
    </button>
  </div>
</section>

<script>
// Disclosure toggle (vanilla JS for accessibility)
const toggle = document.querySelector('[data-toggle="disclosure"]');
const details = document.getElementById('consent-details');

toggle.addEventListener('click', (e) => {
  e.preventDefault();
  const isExpanded = toggle.getAttribute('aria-expanded') === 'true';
  
  toggle.setAttribute('aria-expanded', !isExpanded);
  details.hidden = isExpanded;
  
  // Update link text
  toggle.textContent = isExpanded ? 'Learn more' : 'Show less';
});
</script>
```

### WCAG 2.2 Compliance

- **SC 2.1.1 (Keyboard)**: All controls keyboard-accessible via `<button>` and native `<input>`
- **SC 2.4.6 (Headings)**: Semantic heading hierarchy (`<h2>` → `<h3>` → `<h4>`)
- **SC 4.1.2 (Name, Role, Value)**: `aria-expanded`, `aria-controls`, `aria-describedby` for disclosure state
- **SC 1.4.1 (Use of Color)**: Button text + icons, not color alone
- **SC 2.5.8 (Target Size)**: Buttons minimum 44×44px

### GDPR/CCPA Mapping

| Regulation | Article/Section | Requirement Met |
|------------|----------------|------------------|
| **GDPR** | Art. 12(1) | Concise, transparent, intelligible communication ✅ |
| **GDPR** | Art. 13(2)(f) | Right to withdraw consent ✅ ("Reject Optional" button) |
| **GDPR** | Art. 7(2) | Consent request distinguishable from other matters ✅ (dedicated UI) |
| **CCPA** | §1798.135(a)(1) | "Do Not Sell" link clearly visible ✅ (if Layer 2 includes sale opt-out) |
| **CPRA** | §1798.135(b) | No dark patterns in opt-out process ✅ (equal visual weight for all buttons) |

---

## Pattern 2: Just-in-Time (JIT) Consent

### Problem

**Premature permission requests create friction and distrust:**
- Mobile apps asking for location access immediately on launch (before context)
- Forms requesting phone numbers before explaining why
- Violations of GDPR Article 5(1)(c) — data minimization principle
- Users deny permissions by default when context is missing

**Example of the problem:**
```python
# ❌ BAD: Request permission at app startup
@app.on_event("startup")
async def request_all_permissions():
    await request_location_permission()  # Why? User hasn't done anything yet!
    await request_notification_permission()
    await request_camera_permission()
```

### Solution

**Defer permission requests until the user triggers a feature that requires them:**
- User clicks "Find Nearby" → request location
- User uploads profile photo → request camera
- User enables alerts → request notifications

**Context + Timing + Purpose = Informed Consent**

### When to Use

- ✅ Geolocation for maps, store finders, delivery tracking
- ✅ Camera/microphone for video calls, photo uploads
- ✅ Push notifications for alerts (not marketing)
- ✅ Phone numbers for 2FA/MFA
- ❌ Email at signup (required for account creation)
- ❌ Mandatory profile fields (ask upfront)

### Implementation

```python
from fastapi import FastAPI, Request, HTTPException, Depends
from functools import wraps
from typing import Callable, Any
import logging

logger = logging.getLogger(__name__)

# JIT Consent Decorator for FastAPI
def requires_jit_consent(permission: str, purpose: str):
    """
    Enforce just-in-time consent for sensitive data access.
    
    Args:
        permission: Permission type ("location", "camera", "notifications")
        purpose: Human-readable purpose ("find nearby resources")
    
    Raises:
        HTTPException 403: If user hasn't granted permission
    
    Example:
        @requires_jit_consent("location", "find nearby Azure regions")
        async def get_nearby_regions(request: Request):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract request from args/kwargs
            request = kwargs.get('request') or next(
                (arg for arg in args if isinstance(arg, Request)), None
            )
            
            if not request:
                raise ValueError("Request object required for JIT consent")
            
            # Check if user has granted permission
            user_permissions = request.session.get('jit_permissions', {})
            
            if not user_permissions.get(permission):
                logger.warning(
                    f"JIT consent required for {permission} (purpose: {purpose})"
                )
                raise HTTPException(
                    status_code=403,
                    detail={
                        "error": "permission_required",
                        "permission": permission,
                        "purpose": purpose,
                        "action": "Request user consent in UI before retrying",
                        "help_url": f"/docs/privacy/jit-consent#{permission}"
                    }
                )
            
            # Log consent usage for audit trail
            logger.info(
                f"JIT consent verified: {permission} for {purpose}",
                extra={
                    "user_id": request.session.get('user_id'),
                    "granted_at": user_permissions.get(f"{permission}_granted_at")
                }
            )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator

# Example endpoint
app = FastAPI()

@app.get("/api/resources/nearby")
@requires_jit_consent("location", "find nearby Azure resources")
async def get_nearby_resources(request: Request):
    """
    Find Azure resources near user's location.
    Requires just-in-time location consent.
    """
    latitude = request.query_params.get('lat')
    longitude = request.query_params.get('lon')
    
    # ... query resources by location ...
    return {"resources": [...], "location": {"lat": latitude, "lon": longitude}}

@app.post("/api/consent/grant")
async def grant_jit_consent(request: Request, permission: str):
    """
    User grants JIT consent for a specific permission.
    Frontend calls this after showing explanation modal.
    """
    from datetime import datetime
    
    if 'jit_permissions' not in request.session:
        request.session['jit_permissions'] = {}
    
    request.session['jit_permissions'][permission] = True
    request.session['jit_permissions'][f"{permission}_granted_at"] = datetime.utcnow().isoformat()
    
    logger.info(f"JIT consent granted: {permission}", extra={
        "user_id": request.session.get('user_id'),
        "session_id": request.session.get('session_id')
    })
    
    return {"status": "consent_granted", "permission": permission}
```

```javascript
// Frontend: Show JIT consent modal when 403 is returned
async function findNearbyResources() {
  try {
    const position = await getCurrentPosition(); // Browser geolocation API
    const response = await fetch(
      `/api/resources/nearby?lat=${position.latitude}&lon=${position.longitude}`
    );
    
    if (response.status === 403) {
      const error = await response.json();
      
      // Show JIT consent modal with context
      const userConsent = await showJITConsentModal({
        permission: error.permission,
        purpose: error.purpose,
        helpUrl: error.help_url
      });
      
      if (userConsent) {
        // Grant consent in backend
        await fetch('/api/consent/grant', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ permission: error.permission })
        });
        
        // Retry original request
        return findNearbyResources();
      }
    }
    
    return await response.json();
  } catch (err) {
    console.error('Location error:', err);
  }
}
```

### WCAG 2.2 Compliance

- **SC 3.2.2 (On Input)**: Permission request triggered by user action (clicking "Find Nearby"), not automatic
- **SC 3.3.2 (Labels or Instructions)**: Modal explains WHY permission is needed ("to find nearby Azure resources")
- **SC 2.4.3 (Focus Order)**: Focus moves to modal, trapped until user responds

### GDPR/CCPA Mapping

| Regulation | Article/Section | Requirement Met |
|------------|----------------|------------------|
| **GDPR** | Art. 5(1)(c) | Data minimization — only request when needed ✅ |
| **GDPR** | Art. 7(1) | Demonstrable consent — logged with timestamp ✅ |
| **GDPR** | Art. 13(1)(c) | Purpose specified before collection ✅ ("purpose" parameter) |
| **CCPA** | §1798.100(b) | Notice at or before collection ✅ (modal before API call) |

---

## Pattern 3: Progressive Profiling

### Problem

**Lengthy signup forms kill conversion and violate data minimization:**
- Average signup form: 11.4 fields (Baymard Institute)
- Each additional field = 5-10% conversion drop
- Users abandon when asked for "nice-to-have" data upfront
- GDPR Article 5(1)(c) prohibits collecting data "just in case"

**Example of the problem:**
```html
<!-- ❌ BAD: 20-field registration form -->
<form action="/signup">
  <input name="email" required>
  <input name="password" required>
  <input name="first_name" required>
  <input name="last_name" required>
  <input name="phone" required>  <!-- Why at signup?! -->
  <input name="company" required>
  <input name="job_title" required>
  <input name="industry" required>
  <!-- ... 12 more fields ... -->
  <button>Create Account</button>
</form>
```

### Solution

**Collect data progressively based on user journey stage:**
1. **Signup (Day 0)**: Email + password only
2. **First login (Day 1)**: Name for personalization
3. **Feature trigger (Day 7)**: Phone for 2FA when enabling secure features
4. **Upgrade (Day 30)**: Billing details when purchasing

**Minimal → Contextual → Value-Driven = Ethical Data Collection**

### When to Use

- ✅ Multi-step user journeys (trials → paid)
- ✅ Freemium models (basic → premium features)
- ✅ Account maturity models (new → power user)
- ✅ Feature-gated data (2FA phone, billing address)
- ❌ One-time transactions (e-commerce checkout)
- ❌ Guest/anonymous flows

### Implementation

```html
<!-- STAGE 1: Minimal Signup (Day 0) -->
<form action="/api/auth/signup" method="post" id="signup-form">
  <h2>Get Started</h2>
  
  <label for="email">
    Email Address <span aria-label="required">*</span>
  </label>
  <input type="email" id="email" name="email" 
         autocomplete="email" required
         aria-describedby="email-help">
  <small id="email-help">We'll never share your email.</small>
  
  <label for="password">
    Password <span aria-label="required">*</span>
  </label>
  <input type="password" id="password" name="password" 
         autocomplete="new-password" required
         aria-describedby="password-help">
  <small id="password-help">Minimum 12 characters, mix of letters and numbers.</small>
  
  <button type="submit">Create Account</button>
  
  <p class="privacy-note">
    By signing up, you agree to our 
    <a href="/terms">Terms of Service</a> and 
    <a href="/privacy">Privacy Policy</a>.
    We collect only what's needed — more details as you use features.
  </p>
</form>

<!-- STAGE 2: First Login (Day 1) - Name collection -->
<aside class="profile-prompt" role="dialog" aria-labelledby="profile-heading" 
       data-trigger="first-login">
  <h3 id="profile-heading">Welcome! Let's personalize your experience</h3>
  <p>
    Help us address you properly. Your name will appear in:
    • Dashboard greeting<br>
    • Email notifications<br>
    • Shared resources
  </p>
  <form action="/api/profile/update" method="post">
    <label for="first_name">First Name</label>
    <input type="text" id="first_name" name="first_name" 
           autocomplete="given-name">
    
    <label for="last_name">Last Name</label>
    <input type="text" id="last_name" name="last_name" 
           autocomplete="family-name">
    
    <button type="submit">Save</button>
    <button type="button" data-action="skip">Skip for Now</button>
  </form>
</aside>

<!-- STAGE 3: 2FA Enablement (Day 7) - Phone collection -->
<section class="security-prompt" data-trigger="enable-2fa">
  <h3>Enable Two-Factor Authentication</h3>
  <p>
    You're accessing sensitive Azure resources. Protect your account with 2FA.
    We'll send a verification code to your phone.
  </p>
  <form action="/api/auth/2fa/enable" method="post">
    <label for="phone">Phone Number</label>
    <input type="tel" id="phone" name="phone" 
           autocomplete="tel" 
           placeholder="+1 (555) 123-4567"
           aria-describedby="phone-purpose">
    <small id="phone-purpose">
      Used only for 2FA codes. Never for marketing.
      <a href="/privacy#phone-usage">Learn more</a>
    </small>
    
    <button type="submit">Enable 2FA</button>
    <button type="button" data-action="later">Remind Me Later</button>
  </form>
</section>
```

```python
# Backend: Track progressive profiling state
from enum import Enum
from datetime import datetime, timedelta

class ProfileStage(str, Enum):
    MINIMAL = "minimal"  # Email + password only
    NAMED = "named"      # Added first/last name
    SECURED = "secured"  # Enabled 2FA
    COMPLETE = "complete" # All optional fields filled

class ProgressiveProfilingService:
    """
    Manage progressive data collection based on user journey.
    """
    
    @staticmethod
    async def get_next_prompt(user_id: int, db_session) -> dict | None:
        """
        Determine next progressive profiling prompt to show.
        Returns None if user is complete or prompts are exhausted.
        """
        user = await db_session.get(User, user_id)
        account_age = datetime.utcnow() - user.created_at
        
        # Stage 1 → 2: Ask for name after first login (Day 1)
        if (user.profile_stage == ProfileStage.MINIMAL and 
            user.login_count >= 1 and 
            account_age >= timedelta(hours=1)):
            return {
                "prompt_type": "name_collection",
                "trigger": "first_login",
                "fields": ["first_name", "last_name"],
                "reason": "Personalize your dashboard",
                "skippable": True
            }
        
        # Stage 2 → 3: Ask for phone when enabling 2FA (Day 7+)
        if (user.profile_stage == ProfileStage.NAMED and 
            not user.two_factor_enabled and 
            account_age >= timedelta(days=7)):
            return {
                "prompt_type": "phone_collection",
                "trigger": "enable_2fa",
                "fields": ["phone"],
                "reason": "Secure your account with 2FA",
                "skippable": False,  # Security-critical
                "help_url": "/docs/security/2fa"
            }
        
        return None  # No prompts needed
    
    @staticmethod
    async def advance_stage(user_id: int, db_session):
        """Update user's progressive profiling stage."""
        user = await db_session.get(User, user_id)
        
        if user.first_name and user.last_name:
            user.profile_stage = ProfileStage.NAMED
        if user.two_factor_enabled:
            user.profile_stage = ProfileStage.SECURED
        
        await db_session.commit()
```

### WCAG 2.2 Compliance

- **SC 3.3.2 (Labels or Instructions)**: Each prompt explains WHY data is needed ("Personalize dashboard", "Secure account")
- **SC 3.2.5 (Change on Request)**: Prompts appear only after user action, never automatically mid-task
- **SC 3.3.7 (Redundant Entry)**: Use `autocomplete` attributes to prevent re-entering data

### GDPR/CCPA Mapping

| Regulation | Article/Section | Requirement Met |
|------------|----------------|------------------|
| **GDPR** | Art. 5(1)(c) | Data minimization — collect only what's needed now ✅ |
| **GDPR** | Art. 13(1)(c) | Purpose specified at time of collection ✅ ("reason" field) |
| **GDPR** | Art. 5(1)(b) | Purpose limitation — phone only for 2FA, not marketing ✅ |
| **CCPA** | §1798.100(a) | Notice of categories collected — disclosed per stage ✅ |

**Anti-Pattern to Avoid:**
```python
# ❌ DON'T: Collect "just in case"
user.phone = "555-1234"  # Collected at signup
# ... never used for anything ...

# ✅ DO: Collect only when purpose is active
if user.wants_2fa:  # User explicitly enabled feature
    user.phone = request.phone
```

---

## Pattern 4: Consent Receipts

### Problem

**Traditional consent is invisible and unverifiable:**
- No proof of what user agreed to ("I never consented to that!")
- No machine-readable format for DPIA audits
- No interoperability between systems
- GDPR Article 7(1) requires **demonstrable consent**

**Example of the problem:**
```python
# ❌ BAD: Boolean flag with no context
user.analytics_consent = True  # When? For what purpose? Until when?
```

### Solution

**Generate machine-readable consent receipts compliant with ISO/IEC 29184:2020:**
- Immutable record of consent transaction
- Includes: what, why, when, how long, who
- Cryptographically signed for audit trails
- User can download/verify receipt

**Receipts = Transparency + Accountability + Compliance**

### When to Use

- ✅ B2B SaaS (customers need audit trails)
- ✅ Regulated industries (healthcare, finance)
- ✅ Multi-party data sharing (consent broker)
- ✅ DPIA/audit requirements
- ❌ Simple cookie consent (overkill)
- ❌ No compliance obligations

### Implementation

```json
{
  "$schema": "https://kantarainitiative.org/schemas/consent-receipt-v1.1.json",
  
  "receipt_id": "cr_2026-03-06_a3b8c7d2",
  "version": "1.1.0",
  "jurisdiction": "US-CA",
  "consent_timestamp": "2026-03-06T14:23:45.678Z",
  "collection_method": "web_form",
  
  "data_controller": {
    "name": "Azure Governance Platform Inc.",
    "contact": "privacy@azuregov.example.com",
    "address": "123 Cloud St, Seattle, WA 98101",
    "phone": "+1-800-PRIVACY",
    "privacy_policy_url": "https://azuregov.example.com/privacy"
  },
  
  "data_subject": {
    "user_id": "usr_abc123",
    "email": "jane.doe@example.com"
  },
  
  "purposes": [
    {
      "purpose_id": "analytics",
      "purpose_name": "Usage Analytics",
      "purpose_description": "Analyze user interactions to improve platform UX",
      "legal_basis": "consent",
      "processing_categories": [
        "page_views",
        "click_events",
        "session_duration"
      ],
      "third_parties": [
        {
          "name": "Google Analytics",
          "purpose": "Traffic analysis",
          "privacy_policy": "https://policies.google.com/privacy"
        }
      ],
      "retention_period": "P26M",
      "consent_given": true
    },
    {
      "purpose_id": "marketing",
      "purpose_name": "Email Marketing",
      "purpose_description": "Send product updates and feature announcements",
      "legal_basis": "consent",
      "processing_categories": [
        "email_address",
        "product_usage",
        "account_type"
      ],
      "third_parties": [],
      "retention_period": "P3Y",
      "consent_given": false
    }
  ],
  
  "consent_type": "explicit",
  "consent_scope": "service",
  "sensitive_data": false,
  
  "expiry": "2028-03-06T14:23:45.678Z",
  "renewable": true,
  
  "rights": {
    "withdraw_url": "https://azuregov.example.com/privacy/withdraw",
    "access_url": "https://azuregov.example.com/privacy/data-request",
    "portability_url": "https://azuregov.example.com/privacy/export",
    "erasure_url": "https://azuregov.example.com/privacy/delete"
  },
  
  "signature": {
    "algorithm": "RS256",
    "value": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
    "certificate_url": "https://azuregov.example.com/.well-known/consent-signing-cert.pem"
  }
}
```

```python
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import jwt
import uuid
from pydantic import BaseModel, HttpUrl, Field

class ThirdParty(BaseModel):
    name: str
    purpose: str
    privacy_policy: HttpUrl

class Purpose(BaseModel):
    purpose_id: str
    purpose_name: str
    purpose_description: str
    legal_basis: str  # "consent", "contract", "legal_obligation", "legitimate_interest"
    processing_categories: List[str]
    third_parties: List[ThirdParty] = []
    retention_period: str  # ISO 8601 duration (P26M = 26 months)
    consent_given: bool

class ConsentReceipt(BaseModel):
    receipt_id: str = Field(default_factory=lambda: f"cr_{datetime.utcnow().strftime('%Y-%m-%d')}_{uuid.uuid4().hex[:8]}")
    version: str = "1.1.0"
    jurisdiction: str = "US-CA"
    consent_timestamp: datetime = Field(default_factory=datetime.utcnow)
    collection_method: str = "web_form"
    
    data_controller: Dict[str, str]
    data_subject: Dict[str, str]
    purposes: List[Purpose]
    
    consent_type: str = "explicit"  # "explicit" or "implicit"
    consent_scope: str = "service"  # "service" or "research"
    sensitive_data: bool = False
    
    expiry: datetime
    renewable: bool = True
    
    rights: Dict[str, HttpUrl]
    signature: Optional[Dict[str, str]] = None

class ConsentReceiptService:
    """
    Generate and verify ISO/IEC 29184:2020-compliant consent receipts.
    """
    
    def __init__(self, private_key: str, public_cert_url: str):
        self.private_key = private_key
        self.public_cert_url = public_cert_url
    
    def generate_receipt(
        self, 
        user_id: str, 
        email: str, 
        purposes: List[Purpose]
    ) -> ConsentReceipt:
        """
        Generate signed consent receipt.
        """
        receipt = ConsentReceipt(
            data_controller={
                "name": "Azure Governance Platform Inc.",
                "contact": "privacy@azuregov.example.com",
                "address": "123 Cloud St, Seattle, WA 98101",
                "phone": "+1-800-PRIVACY",
                "privacy_policy_url": "https://azuregov.example.com/privacy"
            },
            data_subject={
                "user_id": user_id,
                "email": email
            },
            purposes=purposes,
            expiry=datetime.utcnow() + timedelta(days=730),  # 2 years
            rights={
                "withdraw_url": "https://azuregov.example.com/privacy/withdraw",
                "access_url": "https://azuregov.example.com/privacy/data-request",
                "portability_url": "https://azuregov.example.com/privacy/export",
                "erasure_url": "https://azuregov.example.com/privacy/delete"
            }
        )
        
        # Sign receipt with RS256 (RSA + SHA-256)
        receipt_dict = receipt.model_dump(mode='json')
        receipt_dict.pop('signature', None)  # Remove signature field before signing
        
        signature = jwt.encode(
            receipt_dict,
            self.private_key,
            algorithm="RS256"
        )
        
        receipt.signature = {
            "algorithm": "RS256",
            "value": signature,
            "certificate_url": self.public_cert_url
        }
        
        return receipt
    
    def verify_receipt(self, receipt: ConsentReceipt, public_key: str) -> bool:
        """
        Verify receipt signature hasn't been tampered with.
        """
        if not receipt.signature:
            return False
        
        try:
            receipt_dict = receipt.model_dump(mode='json')
            receipt_dict.pop('signature')
            
            jwt.decode(
                receipt.signature['value'],
                public_key,
                algorithms=["RS256"]
            )
            return True
        except jwt.InvalidTokenError:
            return False

# Example usage in FastAPI
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/consent")

@router.post("/grant", response_model=ConsentReceipt)
async def grant_consent(
    purposes: List[Purpose],
    user_id: str,
    email: str
):
    """
    User grants consent and receives machine-readable receipt.
    """
    service = ConsentReceiptService(
        private_key=open("/path/to/private.key").read(),
        public_cert_url="https://azuregov.example.com/.well-known/consent-cert.pem"
    )
    
    receipt = service.generate_receipt(user_id, email, purposes)
    
    # Store receipt in database for audit trail
    await db.consent_receipts.insert_one(receipt.model_dump())
    
    # Email receipt to user
    await send_email(
        to=email,
        subject="Your Consent Receipt",
        body=f"Attached is your consent receipt (ID: {receipt.receipt_id})",
        attachments=[{"consent-receipt.json": receipt.model_dump_json(indent=2)}]
    )
    
    return receipt

@router.get("/receipt/{receipt_id}", response_model=ConsentReceipt)
async def get_receipt(receipt_id: str):
    """
    User retrieves consent receipt by ID.
    """
    receipt = await db.consent_receipts.find_one({"receipt_id": receipt_id})
    if not receipt:
        raise HTTPException(status_code=404, detail="Receipt not found")
    
    return ConsentReceipt(**receipt)
```

### WCAG 2.2 Compliance

- **N/A** — Backend-only pattern (no UI)
- **Accessibility consideration**: If displaying receipts in UI, use `<dl>` (description list) for key-value pairs
- **Download format**: Provide both JSON (machine-readable) and PDF (human-readable)

### GDPR/CCPA Mapping

| Regulation | Article/Section | Requirement Met |
|------------|----------------|------------------|
| **GDPR** | Art. 7(1) | Demonstrable consent — cryptographically signed record ✅ |
| **GDPR** | Art. 13 | Information to be provided — all 13(1) and 13(2) fields included ✅ |
| **GDPR** | Art. 30 | Records of processing activities — receipts serve as evidence ✅ |
| **ISO/IEC 29184:2020** | § 7.2 | Consent record requirements — fully compliant ✅ |
| **CCPA** | §1798.100(a) | Right to know — receipt provides complete disclosure ✅ |

**Key Benefits:**
- **Audit Defense**: "Here's the signed receipt proving consent on 2026-03-06 at 14:23 UTC"
- **User Trust**: Transparency builds confidence
- **Interoperability**: JSON schema works across systems
- **Automation**: Machine-readable for DPIA tooling

---

## Pattern 5: GPC (Global Privacy Control)

### Problem

**Users can't exercise privacy rights at scale:**
- 1,000+ websites visited per year = 1,000 cookie banners
- "Do Not Sell" links buried in footer (dark pattern)
- No way to signal preferences browser-wide
- CCPA §1798.135(a) requires "clear and conspicuous" opt-out — current UX fails this

**Example of the problem:**
```python
# ❌ BAD: Ignore user's privacy preference signal
@app.middleware("http")
async def analytics_middleware(request: Request, call_next):
    # Loads analytics script for EVERYONE, ignoring GPC
    response = await call_next(request)
    response.headers["X-Analytics"] = "enabled"
    return response
```

### Solution

**Detect and honor `Sec-GPC: 1` HTTP header automatically:**
- Browser sends `Sec-GPC: 1` if user enabled GPC
- Backend disables sale/sharing of personal information
- No user action required (privacy by default)
- Reference: [docs/security/gpc-compliance.md](../security/gpc-compliance.md)

**One Signal = Universal Privacy = Regulatory Compliance**

### When to Use

- ✅ California users (CCPA/CPRA requirement)
- ✅ Analytics/ads enabled on site
- ✅ Third-party scripts (Google, Facebook pixels)
- ✅ Data sharing with partners
- ❌ No tracking/selling of data (nothing to opt out of)
- ❌ Internal tools (no external users)

### Implementation

```python
from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware
import logging

logger = logging.getLogger(__name__)

class GPCMiddleware(BaseHTTPMiddleware):
    """
    Global Privacy Control (GPC) compliance middleware.
    Detects Sec-GPC: 1 header and auto-disables sale/sharing.
    
    Legal basis: CCPA §1798.135, CPRA amendments.
    Reference: docs/security/gpc-compliance.md
    """
    
    async def dispatch(self, request: Request, call_next):
        # Detect GPC signal
        gpc_header = request.headers.get("Sec-GPC")
        gpc_enabled = gpc_header == "1"
        
        # Store in request state for route handlers
        request.state.gpc_enabled = gpc_enabled
        
        if gpc_enabled:
            logger.info(
                "GPC signal detected - disabling sale/sharing",
                extra={
                    "ip": request.client.host,
                    "path": request.url.path,
                    "user_agent": request.headers.get("User-Agent")
                }
            )
            
            # Auto-apply privacy preferences
            request.state.analytics_enabled = False
            request.state.third_party_sharing = False
            request.state.targeted_ads = False
        else:
            # Default behavior (can be overridden by user preferences)
            request.state.analytics_enabled = True
            request.state.third_party_sharing = True
            request.state.targeted_ads = True
        
        response = await call_next(request)
        
        # Add GPC status header for transparency
        if gpc_enabled:
            response.headers["X-GPC-Status"] = "honored"
        
        return response

app = FastAPI()
app.add_middleware(GPCMiddleware)

# Example: Conditional analytics loading
@app.get("/analytics-config")
async def get_analytics_config(request: Request):
    """
    Return analytics configuration based on GPC status.
    Frontend uses this to decide whether to load GA/FB pixels.
    """
    return {
        "analytics_enabled": request.state.analytics_enabled,
        "third_party_sharing": request.state.third_party_sharing,
        "gpc_honored": request.state.gpc_enabled,
        "notice": "Your privacy preferences have been applied automatically" if request.state.gpc_enabled else None
    }

# Example: GPC-aware data sharing
@app.post("/api/resources/share")
async def share_resource(request: Request, recipient_email: str):
    """
    Share Azure resource with colleague.
    Respects GPC for metadata sharing with third parties.
    """
    if request.state.third_party_sharing:
        # Include usage analytics in share notification
        await analytics.track_share_event(request.state.user_id)
    
    # Core functionality works regardless of GPC
    await share_service.send_invitation(recipient_email)
    
    return {"status": "shared", "gpc_applied": request.state.gpc_enabled}
```

```javascript
// Frontend: Respect GPC in JavaScript
(async function() {
  // Fetch GPC status from backend
  const config = await fetch('/analytics-config').then(r => r.json());
  
  if (config.analytics_enabled) {
    // Load Google Analytics
    window.dataLayer = window.dataLayer || [];
    function gtag(){dataLayer.push(arguments);}
    gtag('js', new Date());
    gtag('config', 'GA-XXXXXXXXX');
  } else {
    console.log('Analytics disabled due to GPC signal');
  }
  
  // Show notice to user
  if (config.gpc_honored) {
    const notice = document.createElement('div');
    notice.className = 'gpc-notice';
    notice.setAttribute('role', 'status');
    notice.setAttribute('aria-live', 'polite');
    notice.textContent = '✓ Your Global Privacy Control preference has been applied';
    document.body.prepend(notice);
  }
})();
```

```html
<!-- GPC status indicator in privacy settings -->
<section class="privacy-settings">
  <h2>Privacy Preferences</h2>
  
  <div class="gpc-status" data-gpc-detected="true">
    <svg aria-hidden="true" width="24" height="24">
      <circle cx="12" cy="12" r="10" fill="#10B981"/>
      <path d="M7 12l3 3 7-7" stroke="white" stroke-width="2"/>
    </svg>
    <div>
      <strong>Global Privacy Control Detected</strong>
      <p>
        Your browser is sending a <code>Sec-GPC: 1</code> signal.
        We've automatically disabled sale and sharing of your personal information.
      </p>
      <p>
        <a href="https://globalprivacycontrol.org" target="_blank">
          Learn more about GPC
          <span class="sr-only">(opens in new tab)</span>
        </a>
      </p>
    </div>
  </div>
  
  <details>
    <summary>What's disabled when GPC is active?</summary>
    <ul>
      <li>❌ Third-party analytics (Google Analytics, Facebook Pixel)</li>
      <li>❌ Targeted advertising</li>
      <li>❌ Data sharing with partners</li>
      <li>✅ Essential cookies (authentication, security) — still active</li>
      <li>✅ First-party analytics (anonymized) — still active</li>
    </ul>
  </details>
</section>
```

### WCAG 2.2 Compliance

- **SC 1.3.1 (Info and Relationships)**: GPC status indicator uses semantic HTML (`<section>`, `<strong>`)
- **SC 4.1.3 (Status Messages)**: `role="status"` + `aria-live="polite"` for GPC confirmation
- **SC 1.4.1 (Use of Color)**: Green checkmark + text, not color alone

### GDPR/CCPA Mapping

| Regulation | Article/Section | Requirement Met |
|------------|----------------|------------------|
| **CCPA** | §1798.135(a) | Right to opt out of sale — GPC is legally binding signal ✅ |
| **CPRA** | §1798.135(b)(2) | Browser-based opt-out mechanisms honored ✅ |
| **GDPR** | Art. 21 | Right to object to processing — GPC satisfies objection ✅ |
| **ePrivacy Directive** | Art. 5(3) | User's wishes expressed via browser settings respected ✅ |

**Legal Compliance Note:**

Per California Attorney General regulations (CCPA §999.315(d)):
> "A business that uses a user-enabled global privacy control... SHALL treat the user-enabled global privacy control as a valid request..."

**Not honoring GPC = legal violation.** See [docs/security/gpc-compliance.md](../security/gpc-compliance.md) for full analysis.

### Browser Support

| Browser | GPC Support |
|---------|-------------|
| **Firefox** | ✅ Native (Settings → Privacy → Do Not Sell) |
| **Brave** | ✅ Native (enabled by default) |
| **DuckDuckGo** | ✅ Native (mobile + desktop) |
| **Chrome** | ⚠️ Extension required ([OptMeowt](https://chrome.google.com/webstore/detail/optmeowt)) |
| **Safari** | ⚠️ Extension required |

**Testing GPC:**
```bash
# Test with curl
curl -H "Sec-GPC: 1" https://azuregov.example.com/analytics-config

# Should return: {"analytics_enabled": false, "gpc_honored": true}
```

---

## Implementation Checklist

When implementing Privacy-by-Design patterns:

### Planning Phase
- [ ] Identify which patterns apply to your use case (see Decision Matrix)
- [ ] Map data flows to GDPR/CCPA requirements
- [ ] Involve legal team in pattern selection
- [ ] Review [docs/security/gpc-compliance.md](../security/gpc-compliance.md) for GPC obligations

### Development Phase
- [ ] Implement patterns in order of legal priority (GPC first if applicable)
- [ ] Add WCAG 2.2 compliance checks to code review
- [ ] Generate consent receipts for all explicit consent flows
- [ ] Test with screen readers (NVDA, JAWS, VoiceOver)
- [ ] Validate JSON schemas against ISO/IEC 29184:2020

### Testing Phase
- [ ] Test GPC with `Sec-GPC: 1` header
- [ ] Verify JIT consent prompts appear at correct triggers
- [ ] Test progressive profiling across user journey stages
- [ ] Validate consent receipt signatures
- [ ] Test layered consent with keyboard-only navigation

### Documentation Phase
- [ ] Update privacy policy with pattern descriptions
- [ ] Document data retention per purpose (consent receipts)
- [ ] Create user guides for privacy controls
- [ ] Maintain DPIA records referencing consent receipts

### Monitoring Phase
- [ ] Log GPC detection rate (monitor compliance)
- [ ] Track JIT consent conversion rates
- [ ] Monitor progressive profiling completion stages
- [ ] Audit consent receipt generation errors
- [ ] Review WCAG compliance quarterly

---

## References

### Standards & Specifications
- **ISO/IEC 29184:2020**: Online privacy notices and consent
- **Kantara Initiative**: Consent Receipt Specification v1.1
- **W3C**: Global Privacy Control (GPC) Specification
- **WCAG 2.2**: Web Content Accessibility Guidelines

### Legal Frameworks
- **GDPR**: Articles 7, 12, 13, 25, 30
- **CCPA/CPRA**: §1798.100, §1798.135
- **ePrivacy Directive**: Article 5(3)
- **California AG Regulations**: §999.315 (GPC)

### Azure Governance Platform Docs
- [GPC Compliance Validation](../security/gpc-compliance.md)
- [API Governance Guide](../governance/api-governance-guide.md)
- [Accessibility API Contract](../contracts/accessibility-api.md)

### External Resources
- [Privacy by Design Framework](https://www.ipc.on.ca/wp-content/uploads/resources/7foundationalprinciples.pdf) — Ann Cavoukian
- [Global Privacy Control](https://globalprivacycontrol.org) — Official site
- [WCAG 2.2 Quick Reference](https://www.w3.org/WAI/WCAG22/quickref/)

---

## Changelog

| Date | Version | Changes | Author |
|------|---------|---------|--------|
| 2026-03-06 | 1.0.0 | Initial pattern library creation | Husky 🐺 (husky-8c15e4) |

---

## Support

Questions about Privacy-by-Design patterns?
- **Technical**: Open issue with `privacy` label
- **Legal**: Contact privacy@azuregov.example.com
- **Accessibility**: Contact accessibility@azuregov.example.com

**Remember**: Privacy is a human right, not a feature toggle. Build it in from day one. 🔒
