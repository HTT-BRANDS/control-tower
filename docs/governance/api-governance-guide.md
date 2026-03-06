# API Governance Guide

## Overview

This guide explains how to use Spectral for API design governance on the Azure Governance Platform. Spectral is an open-source API linting tool that validates OpenAPI specifications against customizable rulesets.

**Version:** Spectral CLI 6.15.0  
**Spec Format:** OpenAPI 3.1.0 (FastAPI native)

## Table of Contents

1. [Installation](#installation)
2. [Usage](#usage)
3. [Pre-commit Integration](#pre-commit-integration)
4. [CI Integration](#ci-integration)
5. [Generating OpenAPI Specs](#generating-openapi-specs)
6. [Understanding the Ruleset](#understanding-the-ruleset)
7. [Adding Custom Rules](#adding-custom-rules)
8. [Troubleshooting](#troubleshooting)

---

## Installation

### Local Development

Install Spectral globally using npm:

```bash
npm install -g @stoplight/spectral-cli@6.15.0
```

Verify installation:

```bash
spectral --version
# Should output: 6.15.0 (or later)
```

### IDE Integration

#### VS Code

1. Install the **Spectral** extension:
   - Search for "Spectral" in VS Code Extensions
   - Install the official Stoplight extension

2. Configure workspace settings (`.vscode/settings.json`):
   ```json
   {
     "spectral.enable": true,
     "spectral.rulesetFile": ".spectral.yaml",
     "spectral.validateFiles": ["**/*.yaml", "**/*.json"],
     "spectral.run": "onSave"
   }
   ```

#### JetBrains IDEs (PyCharm, IntelliJ)

1. Install the **Spectral** plugin from the marketplace
2. Configure in Settings → Tools → Spectral
3. Point to `.spectral.yaml` in the project root

---

## Usage

### Basic Linting

Lint a single OpenAPI specification:

```bash
spectral lint openapi.yaml
```

Lint with output format options:

```bash
# Pretty output (default)
spectral lint openapi.yaml

# JSON output (for CI/scripts)
spectral lint openapi.yaml --format json

# JUnit format (for test reporters)
spectral lint openapi.yaml --format junit

# HTML report
spectral lint openapi.yaml --format html > api-lint-report.html
```

### Lint Multiple Files

```bash
# Lint all YAML files
spectral lint '**/*.yaml'

# Lint all OpenAPI specs
spectral lint 'specs/**/*.openapi.yaml'
```

### Severity Filtering

```bash
# Fail only on errors (ignore warnings)
spectral lint openapi.yaml --fail-severity error

# Show all issues including hints
spectral lint openapi.yaml --fail-severity hint
```

### Verbose Output

```bash
# Show detailed rule information
spectral lint openapi.yaml --verbose

# Show rule documentation
spectral lint openapi.yaml --display-only-failures false
```

---

## Pre-commit Integration

### Setup

Add Spectral to your pre-commit hooks to catch API issues before committing.

#### Method 1: Using pre-commit framework

Add to `.pre-commit-config.yaml`:

```yaml
repos:
  # Spectral API Linting
  - repo: local
    hooks:
      - id: spectral-lint
        name: Spectral API Lint
        entry: spectral lint
        language: system
        files: '\.(yaml|json)$'
        pass_filenames: true
        args: ["--fail-severity", "error"]
```

Install hooks:

```bash
pre-commit install
```

#### Method 2: Manual Git Hook

Create `.git/hooks/pre-commit`:

```bash
#!/bin/bash
# Pre-commit hook for Spectral API linting

set -e

# Find OpenAPI spec files
OPENAPI_FILES=$(git diff --cached --name-only --diff-filter=ACM | grep -E '\.(yaml|json)$' || true)

if [ -n "$OPENAPI_FILES" ]; then
  echo "🔍 Running Spectral API lint..."
  
  for file in $OPENAPI_FILES; do
    echo "  Checking $file"
    spectral lint "$file" --fail-severity error
  done
  
  echo "✅ All API specs passed linting!"
fi

exit 0
```

Make executable:

```bash
chmod +x .git/hooks/pre-commit
```

### Testing Pre-commit Hook

```bash
# Test without committing
pre-commit run spectral-lint --all-files

# Or test manually
spectral lint openapi.yaml --fail-severity error
```

---

## CI Integration

### GitHub Actions

Create `.github/workflows/api-lint.yml`:

```yaml
name: API Governance

on:
  pull_request:
    paths:
      - '**.yaml'
      - '**.json'
      - '.spectral.yaml'
  push:
    branches:
      - main
      - develop

jobs:
  spectral-lint:
    name: Spectral API Lint
    runs-on: ubuntu-latest
    
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
      
      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'
      
      - name: Install Spectral
        run: npm install -g @stoplight/spectral-cli@6.15.0
      
      - name: Generate OpenAPI spec from FastAPI
        run: |
          python -m venv .venv
          source .venv/bin/activate
          pip install -r requirements.txt
          python -c "from app.main import app; import json; print(json.dumps(app.openapi()))" > openapi.json
      
      - name: Lint OpenAPI specification
        run: spectral lint openapi.json --fail-severity error
      
      - name: Generate HTML report
        if: failure()
        run: spectral lint openapi.json --format html > api-lint-report.html
      
      - name: Upload lint report
        if: failure()
        uses: actions/upload-artifact@v3
        with:
          name: api-lint-report
          path: api-lint-report.html
```

### Azure Pipelines

Add to `azure-pipelines.yml`:

```yaml
stages:
  - stage: APIGovernance
    displayName: 'API Governance'
    jobs:
      - job: SpectralLint
        displayName: 'Spectral API Lint'
        pool:
          vmImage: 'ubuntu-latest'
        steps:
          - task: NodeTool@0
            inputs:
              versionSpec: '20.x'
            displayName: 'Install Node.js'
          
          - script: |
              npm install -g @stoplight/spectral-cli@6.15.0
            displayName: 'Install Spectral'
          
          - script: |
              python -c "from app.main import app; import json; print(json.dumps(app.openapi()))" > openapi.json
            displayName: 'Generate OpenAPI spec'
          
          - script: |
              spectral lint openapi.json --fail-severity error
            displayName: 'Lint OpenAPI spec'
```

### GitLab CI

Add to `.gitlab-ci.yml`:

```yaml
api-governance:
  stage: test
  image: node:20-alpine
  before_script:
    - npm install -g @stoplight/spectral-cli@6.15.0
  script:
    - python -c "from app.main import app; import json; print(json.dumps(app.openapi()))" > openapi.json
    - spectral lint openapi.json --fail-severity error
  artifacts:
    when: on_failure
    paths:
      - api-lint-report.html
```

---

## Generating OpenAPI Specs

### From FastAPI Application

FastAPI automatically generates OpenAPI 3.1.0 specifications. Here's how to extract them:

#### Method 1: Runtime Generation (Recommended)

```bash
# Start the application and fetch the spec
uvicorn app.main:app &
PID=$!
sleep 3
curl http://localhost:8000/openapi.json > openapi.json
kill $PID

# Or using Python directly
python -c "from app.main import app; import json; print(json.dumps(app.openapi()))" > openapi.json
```

#### Method 2: API Endpoint

The FastAPI app exposes OpenAPI at `/openapi.json`:

```bash
curl https://your-app.azurewebsites.net/openapi.json > openapi.json
```

#### Method 3: Export Script

Create `scripts/export-openapi.py`:

```python
#!/usr/bin/env python3
"""Export OpenAPI specification from FastAPI app."""

import json
import sys
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.main import app

def export_openapi(output_file: str = "openapi.json"):
    """Export OpenAPI spec to file."""
    spec = app.openapi()
    
    with open(output_file, 'w') as f:
        json.dump(spec, f, indent=2)
    
    print(f"✅ OpenAPI spec exported to {output_file}")
    print(f"📊 Endpoints: {len(spec.get('paths', {}))}")
    print(f"📦 Schemas: {len(spec.get('components', {}).get('schemas', {}))}")

if __name__ == "__main__":
    output = sys.argv[1] if len(sys.argv) > 1 else "openapi.json"
    export_openapi(output)
```

Usage:

```bash
python scripts/export-openapi.py openapi.json
spectral lint openapi.json
```

### YAML Format

Convert JSON to YAML for better readability:

```bash
# Using yq
yq eval -P openapi.json > openapi.yaml

# Using Python
python -c "import json, yaml; yaml.dump(json.load(open('openapi.json')), open('openapi.yaml', 'w'))"
```

---

## Understanding the Ruleset

The `.spectral.yaml` ruleset includes the following rule categories:

### 1. Documentation Rules (Warnings)

- **operation-description**: Every endpoint must document what it does
- **operation-tag**: Endpoints must be categorized with tags
- **info-contact**: API must include contact information
- **info-description**: API must have a description

### 2. Schema Validation Rules (Errors)

- **oas3-valid-schema-example**: Examples must match their schemas
- **no-$ref-siblings**: `$ref` cannot have sibling properties
- **typed-enum**: Enums must specify their type

### 3. Security Rules (Errors)

- **security-must-be-defined**: API must define security schemes
- **operation-security**: Operations should specify security requirements

### 4. Custom Platform Rules

- **response-must-have-error-schema**: All 4xx/5xx responses must have error schemas
- **path-must-include-version**: Paths should follow `/api/v{n}/` pattern
- **tenant-scoped-operations**: Multi-tenant endpoints should include tenant context

### 5. Response Standards

- **success-response-required**: Operations must define 2xx responses
- **response-examples-recommended**: Responses should include examples

### 6. Naming Conventions

- **operationId-naming-convention**: Use camelCase for operation IDs
- **path-no-trailing-slash**: Paths must not end with `/`

### 7. Pagination Standards

- **list-operations-pagination**: List endpoints should support pagination

---

## Adding Custom Rules

### Basic Rule Structure

Add rules to `.spectral.yaml`:

```yaml
rules:
  my-custom-rule:
    description: Human-readable description
    severity: error  # error, warn, info, hint
    message: "Error message with {{property}} placeholder"
    given: "$.paths.*.*"  # JSONPath expression
    then:
      field: summary
      function: truthy
```

### Example: Enforce Response Headers

```yaml
rules:
  response-headers-required:
    description: Success responses must define headers
    severity: warn
    given: "$.paths.*.*.responses[?(@property.match(/^2/))]"
    then:
      field: headers
      function: truthy
```

### Example: Enforce Error Model

```yaml
rules:
  error-response-model:
    description: Error responses must use ErrorResponse schema
    severity: error
    given: "$.paths.*.*.responses[?(@property.match(/^[45]/))].content.application/json.schema"
    then:
      field: $ref
      function: pattern
      functionOptions:
        match: "#/components/schemas/ErrorResponse$"
```

### Example: Azure-Specific Rules

```yaml
rules:
  azure-subscription-id-param:
    description: Azure operations should include subscriptionId parameter
    severity: warn
    given: "$.paths[?(@property.match(/\/subscriptions\//))].*"
    then:
      - field: parameters
        function: schema
        functionOptions:
          schema:
            contains:
              properties:
                name:
                  const: "subscription_id"
```

### Custom Functions

For complex validation, write custom JavaScript functions:

1. Create `.spectral/functions/checkTenantIsolation.js`:

```javascript
module.exports = (input, options, context) => {
  // Check if tenant-scoped endpoint includes tenant parameter
  const path = context.path.join('.');
  
  if (path.includes('/costs') || path.includes('/resources')) {
    const parameters = input.parameters || [];
    const hasTenantParam = parameters.some(p => 
      p.name && p.name.toLowerCase().includes('tenant')
    );
    
    if (!hasTenantParam) {
      return [
        {
          message: 'Multi-tenant endpoints must include tenant parameter for isolation',
        },
      ];
    }
  }
  
  return [];
};
```

2. Reference in `.spectral.yaml`:

```yaml
functions:
  - checkTenantIsolation

rules:
  tenant-isolation:
    description: Enforce tenant isolation pattern
    severity: error
    given: "$.paths.*.*"
    then:
      function: checkTenantIsolation
```

---

## Troubleshooting

### Common Issues

#### Issue: "No valid OpenAPI document found"

**Solution:** Ensure your spec has the required `openapi` field:

```yaml
openapi: 3.1.0
info:
  title: My API
  version: 1.0.0
paths: {}
```

#### Issue: "Rule not found: my-custom-rule"

**Solution:** Check rule name spelling and ensure it's defined in `rules:` section.

#### Issue: "Function X is not defined"

**Solution:** Ensure custom functions are in `.spectral/functions/` and referenced in `functions:` array.

#### Issue: Too many warnings cluttering output

**Solution:** Use `--fail-severity error` to only fail on errors:

```bash
spectral lint openapi.json --fail-severity error
```

### Debugging Tips

1. **Validate JSONPath expressions:**
   ```bash
   # Use online JSONPath evaluator: https://jsonpath.com/
   ```

2. **Test rules individually:**
   ```bash
   spectral lint openapi.json --ruleset .spectral.yaml --only-rule my-custom-rule
   ```

3. **Verbose output:**
   ```bash
   spectral lint openapi.json --verbose
   ```

4. **Check rule documentation:**
   ```bash
   spectral lint --help
   ```

### Performance

For large specs:

```bash
# Disable specific expensive rules
spectral lint openapi.json --ignore-rule oas3-valid-schema-example

# Limit to specific paths
spectral lint openapi.json --only-paths "$.paths['/api/v1/*']"
```

---

## Best Practices

### 1. Start with Standard Rules

Begin with `extends: ["spectral:oas"]` and add custom rules incrementally.

### 2. Use Severity Appropriately

- **Error**: Breaking changes, security issues, spec violations
- **Warn**: Style guidelines, best practices
- **Info**: Suggestions, nice-to-haves
- **Hint**: Very minor suggestions

### 3. Document Custom Rules

Add clear descriptions and messages to help developers understand violations.

### 4. Test Rules Before Enforcing

Run new rules in `info` mode first, then upgrade to `warn` or `error`.

### 5. Keep Rules Focused

Each rule should check one specific thing. Split complex validations into multiple rules.

### 6. Version Your Ruleset

Track `.spectral.yaml` changes in git and document breaking changes.

---

## Resources

- **Spectral Documentation**: https://meta.stoplight.io/docs/spectral
- **OpenAPI Specification**: https://spec.openapis.org/oas/v3.1.0
- **JSONPath Syntax**: https://goessner.net/articles/JsonPath/
- **Azure API Guidelines**: https://github.com/Azure/azure-api-style-guide
- **FastAPI OpenAPI**: https://fastapi.tiangolo.com/advanced/extending-openapi/

---

## Quick Reference

### Common Commands

```bash
# Install
npm install -g @stoplight/spectral-cli@6.15.0

# Generate spec from FastAPI
python -c "from app.main import app; import json; print(json.dumps(app.openapi()))" > openapi.json

# Lint spec
spectral lint openapi.json

# Lint with error-only failure
spectral lint openapi.json --fail-severity error

# Generate HTML report
spectral lint openapi.json --format html > report.html

# Test specific rule
spectral lint openapi.json --only-rule my-rule
```

### JSONPath Quick Reference

```yaml
# Root
$

# All paths
$.paths

# All operations
$.paths.*.*

# GET operations only
$.paths.*.get

# All responses
$.paths.*.*.responses

# 4xx/5xx responses
$.paths.*.*.responses[?(@property.match(/^[45]/))]

# All schemas
$.components.schemas.*

# Nested properties
$.components.schemas.*.properties
```

---

**Last Updated:** 2025-01-27  
**Spectral Version:** 6.15.0  
**Maintained By:** Azure Governance Platform Team
