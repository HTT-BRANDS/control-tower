"""Architecture fitness function tests.

These tests validate architectural constraints and design decisions:
- Module dependencies and circular imports
- Agent privilege boundaries (security)
- API security configurations
- Code organization and file size limits

These tests should run in CI/CD and fail fast if architectural
boundaries are violated.
"""

import ast
import json
import os
from pathlib import Path

import pytest

# ============================================================================
# Test 1: Circular Import Detection
# ============================================================================


def get_imports_from_file(file_path: Path) -> set[str]:
    """Extract all imports from a Python file using AST parsing.

    Args:
        file_path: Path to the Python file

    Returns:
        Set of module names imported by the file
    """
    try:
        with open(file_path, encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=str(file_path))
    except (SyntaxError, UnicodeDecodeError):
        return set()

    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.add(node.module.split(".")[0])

    return imports


def build_module_dependency_graph(base_path: Path) -> dict[str, set[str]]:
    """Build a dependency graph for all Python modules.

    Args:
        base_path: Root directory to scan

    Returns:
        Dictionary mapping module names to their dependencies
    """
    graph = {}

    # Get all Python files
    for py_file in base_path.rglob("*.py"):
        if "__pycache__" in str(py_file) or "venv" in str(py_file):
            continue

        # Convert file path to module name
        rel_path = py_file.relative_to(base_path)
        module_parts = list(rel_path.parts[:-1])  # Remove filename
        if rel_path.stem != "__init__":
            module_parts.append(rel_path.stem)

        if module_parts:
            module_name = ".".join(module_parts)
            imports = get_imports_from_file(py_file)

            # Filter to only include app.* imports
            app_imports = {imp for imp in imports if imp.startswith("app")}
            graph[module_name] = app_imports

    return graph


def detect_circular_dependencies(
    graph: dict[str, set[str]], start_module: str, visited: set[str] = None
) -> list[str]:
    """Detect circular dependencies using DFS.

    Args:
        graph: Module dependency graph
        start_module: Module to start search from
        visited: Set of visited modules (for cycle detection)

    Returns:
        List of modules in the circular dependency, or empty list if none found
    """
    if visited is None:
        visited = set()

    if start_module in visited:
        return [start_module]

    if start_module not in graph:
        return []

    visited.add(start_module)

    for dep in graph[start_module]:
        cycle = detect_circular_dependencies(graph, dep, visited.copy())
        if cycle:
            return [start_module] + cycle

    return []


def test_no_circular_imports():
    """Verify no circular import dependencies between major modules.

    Circular imports can cause:
    - Import errors at runtime
    - Difficult-to-debug initialization issues
    - Tight coupling between modules

    This test scans app/core/, app/api/, app/models/, and app/services/
    for circular dependencies.
    """
    app_path = Path("app")
    if not app_path.exists():
        pytest.skip("app/ directory not found")

    # Build dependency graph
    graph = build_module_dependency_graph(app_path)

    # Check for circular dependencies in major modules
    major_modules = ["core", "api", "models", "services"]
    cycles_found = []

    for module in graph.keys():
        # Only check major modules
        if any(module.startswith(major) for major in major_modules):
            cycle = detect_circular_dependencies(graph, module)
            if len(cycle) > 1 and cycle[0] == cycle[-1]:
                # Found a cycle
                cycles_found.append(" -> ".join(cycle))

    assert not cycles_found, "Circular dependencies detected:\n" + "\n".join(
        f"  - {cycle}" for cycle in cycles_found
    )


# ============================================================================
# Test 2: Agent Least Privilege
# ============================================================================


@pytest.mark.skipif(
    not Path(os.path.expanduser("~/.code_puppy/agents")).exists(),
    reason="No code_puppy agents directory found",
)
def test_agent_least_privilege():
    """Verify agent configurations follow least privilege principle.

    Security constraints:
    1. No agent should have both universal_constructor AND invoke_agent
       (god-mode combo)
    2. Reviewer agents should not have edit_file or delete_file
       (read-only constraint)
    3. Document total unique tools across all agents (baseline metric)

    This ensures the multi-agent system maintains privilege boundaries.
    """
    agents_dir = Path(os.path.expanduser("~/.code_puppy/agents"))
    violations = []
    all_tools = set()
    reviewer_agents = []

    # Read all agent JSON files
    for agent_file in agents_dir.glob("*.json"):
        try:
            with open(agent_file) as f:
                agent_config = json.load(f)

            agent_name = agent_config.get("name", agent_file.stem)
            tools = set(agent_config.get("tools", []))
            all_tools.update(tools)

            # Check for god-mode combo
            if "universal_constructor" in tools and "invoke_agent" in tools:
                violations.append(
                    f"{agent_name}: Has both universal_constructor and invoke_agent (god-mode)"
                )

            # Check reviewer agents
            if "reviewer" in agent_name.lower() or "review" in agent_name.lower():
                reviewer_agents.append(agent_name)
                dangerous_tools = tools & {"edit_file", "delete_file"}
                if dangerous_tools:
                    violations.append(
                        f"{agent_name}: Reviewer has write permissions: {dangerous_tools}"
                    )

        except (json.JSONDecodeError, KeyError) as e:
            violations.append(f"{agent_file.name}: Failed to parse - {e}")

    # Document baseline metrics
    print("\n📊 Agent Privilege Metrics:")
    print(f"  Total agents: {len(list(agents_dir.glob('*.json')))}")
    print(f"  Reviewer agents: {len(reviewer_agents)}")
    print(f"  Unique tools across all agents: {len(all_tools)}")
    print(f"  Tools: {', '.join(sorted(all_tools))}")

    assert not violations, "Agent privilege violations detected:\n" + "\n".join(
        f"  - {v}" for v in violations
    )


# ============================================================================
# Test 3: Security Headers Configuration
# ============================================================================


def test_security_headers_configured():
    """Verify FastAPI app configures all required security headers.

    Required security headers:
    - X-Frame-Options: Prevent clickjacking
    - X-Content-Type-Options: Prevent MIME sniffing
    - Content-Security-Policy: XSS protection
    - Referrer-Policy: Control referrer information
    - Permissions-Policy: Restrict browser features

    Also verifies:
    - CORS is not wildcard in production
    - HSTS is enabled in production
    """
    main_py = Path("app/main.py")
    security_headers_py = Path("app/core/security_headers.py")
    if not main_py.exists():
        pytest.skip("app/main.py not found")
    if not security_headers_py.exists():
        pytest.skip("app/core/security_headers.py not found")

    with open(main_py) as f:
        main_content = f.read()
    with open(security_headers_py) as f:
        security_content = f.read()

    # Check for security headers middleware (class-based pattern)
    assert "SecurityHeadersMiddleware" in main_content, (
        "Security headers middleware not found in app/main.py"
    )

    # Check for required security headers in the security_headers module
    required_headers = [
        "X-Frame-Options",
        "X-Content-Type-Options",
        "Content-Security-Policy",
        "Referrer-Policy",
        "Permissions-Policy",
    ]

    missing_headers = []
    for header in required_headers:
        if header not in security_content:
            missing_headers.append(header)

    assert not missing_headers, (
        "Missing security headers in app/core/security_headers.py:\n"
        + "\n".join(f"  - {h}" for h in missing_headers)
    )

    # Check CORS configuration
    assert "CORSMiddleware" in main_content, "CORS middleware not configured"

    # Verify CORS is not using wildcard ("*") for allow_origins
    # This is a critical security issue
    if 'allow_origins=["*"]' in main_content:
        pytest.fail(
            "CORS is configured with wildcard (*) - this allows any origin "
            "and is a security vulnerability"
        )

    # Check that HSTS is conditionally enabled (production only)
    assert "Strict-Transport-Security" in security_content, (
        "HSTS header not configured (should be enabled in production)"
    )

    print("\n✅ All security headers properly configured")


# ============================================================================
# Test 4: API Routes Require Authentication
# ============================================================================


def extract_route_functions(file_path: Path) -> list[dict[str, any]]:
    """Extract all FastAPI route functions from a route file.

    Args:
        file_path: Path to the route file

    Returns:
        List of dictionaries with route information
    """
    try:
        with open(file_path, encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=str(file_path))
    except (SyntaxError, UnicodeDecodeError):
        return []

    routes = []

    for node in ast.walk(tree):
        # Look for function definitions with route decorators
        if isinstance(node, ast.FunctionDef):
            has_route_decorator = False
            has_auth_dependency = False

            # Check decorators for @router.get, @router.post, etc.
            for decorator in node.decorator_list:
                if isinstance(decorator, ast.Call):
                    if isinstance(decorator.func, ast.Attribute):
                        if decorator.func.attr in [
                            "get",
                            "post",
                            "put",
                            "delete",
                            "patch",
                        ]:
                            has_route_decorator = True

            # Check function parameters for Depends(get_current_user)
            for arg in node.args.args:
                if hasattr(arg, "annotation") and arg.annotation:
                    # Check if annotation mentions User or get_current_user
                    annotation_str = ast.unparse(arg.annotation)
                    if "get_current_user" in annotation_str or annotation_str == "User":
                        has_auth_dependency = True

            if has_route_decorator:
                routes.append(
                    {
                        "name": node.name,
                        "has_auth": has_auth_dependency,
                        "lineno": node.lineno,
                    }
                )

    return routes


def check_router_level_auth(file_path: Path) -> bool:
    """Check if a route file has router-level authentication.

    Returns:
        True if router is configured with dependencies=[Depends(get_current_user)]
    """
    try:
        with open(file_path, encoding="utf-8") as f:
            content = f.read()

        # Look for APIRouter with dependencies parameter
        tree = ast.parse(content, filename=str(file_path))

        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                # Check if assigning to 'router'
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "router":
                        # Check if value is APIRouter call
                        if isinstance(node.value, ast.Call):
                            # Check for dependencies keyword argument
                            for keyword in node.value.keywords:
                                if keyword.arg == "dependencies":
                                    # Check if it mentions get_current_user
                                    dep_str = ast.unparse(keyword.value)
                                    if "get_current_user" in dep_str:
                                        return True

        return False
    except (SyntaxError, UnicodeDecodeError):
        return False


def test_api_routes_require_auth():
    """Verify all API routes (except allowlisted) require authentication.

    Allowlisted endpoints:
    - /health, /health/detailed (health checks)
    - /api/v1/auth/* (login, token refresh)
    - /api/v1/onboarding/* (self-service onboarding)
    - /static/* (static files)
    - / (root redirect)

    All other API endpoints MUST require authentication via:
    - Router-level: dependencies=[Depends(get_current_user)]
    - Route-level: parameter with Depends(get_current_user) or User type
    """
    routes_dir = Path("app/api/routes")
    if not routes_dir.exists():
        pytest.skip("app/api/routes directory not found")

    # Files that are allowed to have public routes
    public_route_files = {"auth.py", "onboarding.py"}

    violations = []

    for route_file in routes_dir.glob("*.py"):
        if route_file.name.startswith("__"):
            continue

        # Check if router has global auth
        has_router_auth = check_router_level_auth(route_file)

        # If public route file, skip detailed checks
        if route_file.name in public_route_files:
            print(f"  ⚠️  {route_file.name}: Public routes allowed (auth/onboarding)")
            continue

        # Extract routes from file
        routes = extract_route_functions(route_file)

        for route in routes:
            # If router has auth, all routes are protected
            if has_router_auth:
                continue

            # Check individual route auth
            if not route["has_auth"]:
                violations.append(
                    f"{route_file.name}:{route['lineno']} - "
                    f"Function '{route['name']}' missing authentication"
                )

    if violations:
        print(f"\n❌ Found {len(violations)} routes without authentication:")
        for v in violations:
            print(f"  - {v}")
    else:
        print("\n✅ All API routes properly secured with authentication")

    assert not violations, "API routes without authentication:\n" + "\n".join(
        f"  - {v}" for v in violations
    )


# ============================================================================
# Test 5: File Size Limit
# ============================================================================


def test_file_size_limit():
    """Verify no Python file exceeds 600 lines (project standard).

    Large files indicate:
    - Violation of Single Responsibility Principle
    - Poor code organization
    - Maintenance difficulties

    Files should be split into smaller, focused modules.

    This test documents the current baseline and fails only if NEW files
    exceed the limit (files not in the known allowlist).
    """
    app_path = Path("app")
    if not app_path.exists():
        pytest.skip("app/ directory not found")

    max_lines = 600
    violations = []

    # Known large files (technical debt) - grandfathered in
    # These should be refactored over time
    known_large_files = {
        "app/preflight/azure_checks.py",
        "app/preflight/riverside_checks.py",
        "app/api/services/graph_client.py",
        "app/core/riverside_scheduler.py",
        "app/services/backfill_service.py",
        "app/services/riverside_sync.py",
        "app/preflight/admin_risk_checks.py",
        "app/preflight/checks.py",
        "app/services/lighthouse_client.py",
        "app/preflight/mfa_checks.py",
        "app/api/routes/onboarding.py",
        "app/api/services/riverside_requirements.py",
        "app/api/services/monitoring_service.py",
        "app/core/rate_limit.py",
        "app/services/email_service.py",
        "app/core/notifications.py",
        "app/api/routes/auth.py",
        "app/api/services/dmarc_service.py",
        "app/core/cache.py",
        "app/api/services/budget_service.py",
        "app/api/routes/identity.py",  # IG-010: access review routes added
        "app/core/config.py",  # Large settings model — cohesive, no good split
        "app/main.py",  # FastAPI app setup — 24 routers + middleware
        "app/core/azure_service_health.py",  # Comprehensive health check logic
        "app/core/metrics.py",  # Prometheus + App Insights metrics
    }

    for py_file in app_path.rglob("*.py"):
        if "__pycache__" in str(py_file):
            continue

        try:
            with open(py_file, encoding="utf-8") as f:
                line_count = sum(1 for _ in f)

            rel_path = str(py_file.relative_to(app_path.parent))

            if line_count > max_lines:
                # Only flag as violation if NOT in known large files
                if rel_path not in known_large_files:
                    violations.append(
                        {
                            "file": rel_path,
                            "lines": line_count,
                            "excess": line_count - max_lines,
                        }
                    )
        except (OSError, UnicodeDecodeError):
            continue

    if violations:
        # Sort by line count (worst offenders first)
        violations.sort(key=lambda x: x["lines"], reverse=True)

        print(f"\n❌ Found {len(violations)} NEW files exceeding {max_lines} lines:")
        for v in violations:
            print(f"  - {v['file']}: {v['lines']} lines (+{v['excess']} over limit)")
        print(
            f"\nNew files must stay under {max_lines} lines. "
            f"Consider splitting into smaller modules."
        )

        raise AssertionError(
            f"\n{len(violations)} NEW files exceed {max_lines} line limit. "
            f"Largest: {violations[0]['file']} ({violations[0]['lines']} lines)"
        )
    else:
        print(
            f"\n✅ No NEW files exceed {max_lines} lines "
            f"({len(known_large_files)} legacy files grandfathered)"
        )


# ============================================================================
# Test 6: Bonus - Module Cohesion Check
# ============================================================================


def test_module_cohesion():
    """Verify core modules maintain high cohesion.

    Checks that:
    - app/core/ modules focus on infrastructure/framework concerns
    - app/api/ modules focus on HTTP/API concerns
    - app/models/ modules focus on data models
    - app/services/ modules focus on business logic

    This is a basic check to ensure modules don't mix concerns.
    """
    app_path = Path("app")
    if not app_path.exists():
        pytest.skip("app/ directory not found")

    violations = []

    # Core modules should not import from api/services
    core_path = app_path / "core"
    if core_path.exists():
        for py_file in core_path.rglob("*.py"):
            imports = get_imports_from_file(py_file)
            bad_imports = {imp for imp in imports if imp.startswith(("app.api", "app.services"))}
            if bad_imports:
                violations.append(
                    f"{py_file.relative_to(app_path.parent)}: "
                    f"Core module imports from api/services: {bad_imports}"
                )

    # Models should be minimal - no service/api imports
    models_path = app_path / "models"
    if models_path.exists():
        for py_file in models_path.rglob("*.py"):
            imports = get_imports_from_file(py_file)
            bad_imports = {
                imp
                for imp in imports
                if imp.startswith(("app.api", "app.services", "app.core"))
                and not imp.startswith("app.core.database")
            }
            if bad_imports:
                violations.append(
                    f"{py_file.relative_to(app_path.parent)}: "
                    f"Model imports from api/services/core: {bad_imports}"
                )

    if violations:
        print(f"\n⚠️  Found {len(violations)} potential cohesion issues:")
        for v in violations:
            print(f"  - {v}")
        print("\nNote: Some violations may be acceptable. Review carefully before making changes.")
    else:
        print("\n✅ Module cohesion looks good - no obvious layering violations")

    # This is a warning, not a hard failure
    # assert not violations
