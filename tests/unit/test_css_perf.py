"""Performance validation for design system theme pipeline.

Task 5.5.2 — validates:
  1. CSS generation speed: < 10 ms per brand for generate_brand_css_variables()
  2. Inline style generation speed: < 10 ms per brand
  3. Scoped CSS generation speed: < 10 ms per brand
  4. All-brands CSS generation: < 50 ms total (5 brands)
  5. ThemeContext construction speed: < 15 ms per brand
"""

import time
import statistics
import pytest

from app.core.css_generator import (
    generate_brand_css_variables,
    generate_inline_style,
    generate_scoped_brand_css,
    generate_all_brands_css,
)
from app.core.design_tokens import load_brands, get_google_fonts_url
from app.core.theme_middleware import ThemeContext, ThemeMiddleware

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
ITERATIONS = 50  # run each operation N times for stable percentiles
MAX_MS_PER_BRAND = 10.0  # requirement: < 10 ms per brand
MAX_MS_ALL_BRANDS = 50.0  # generous budget for all 5 brands at once
MAX_MS_THEME_CTX = 15.0  # ThemeContext construction (includes CSS + inline)

ALL_BRAND_KEYS = ["httbrands", "frenchies", "bishops", "lashlounge", "deltacrown"]


@pytest.fixture(scope="module")
def registry():
    """Load brand registry once for the module."""
    return load_brands()


# ---------------------------------------------------------------------------
# 1. CSS variable generation speed (per brand)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("brand_key", ALL_BRAND_KEYS)
def test_css_variable_generation_speed(registry, brand_key: str):
    """generate_brand_css_variables() must complete in < 10 ms per brand."""
    brand = registry[brand_key]

    timings: list[float] = []
    for _ in range(ITERATIONS):
        start = time.perf_counter()
        variables = generate_brand_css_variables(brand)
        elapsed_ms = (time.perf_counter() - start) * 1000
        timings.append(elapsed_ms)

    p95 = sorted(timings)[int(len(timings) * 0.95)]
    median = statistics.median(timings)

    # Sanity: must produce at least 40 CSS variables
    assert len(variables) >= 40, (
        f"{brand_key}: expected ≥40 CSS variables, got {len(variables)}"
    )
    assert p95 < MAX_MS_PER_BRAND, (
        f"{brand_key}: CSS generation p95={p95:.2f}ms exceeds {MAX_MS_PER_BRAND}ms "
        f"(median={median:.2f}ms)"
    )


# ---------------------------------------------------------------------------
# 2. Inline style generation speed (per brand)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("brand_key", ALL_BRAND_KEYS)
def test_inline_style_generation_speed(registry, brand_key: str):
    """generate_inline_style() must complete in < 10 ms per brand."""
    brand = registry[brand_key]

    timings: list[float] = []
    for _ in range(ITERATIONS):
        start = time.perf_counter()
        style = generate_inline_style(brand)
        elapsed_ms = (time.perf_counter() - start) * 1000
        timings.append(elapsed_ms)

    p95 = sorted(timings)[int(len(timings) * 0.95)]

    assert "--brand-primary:" in style
    assert p95 < MAX_MS_PER_BRAND, (
        f"{brand_key}: inline style p95={p95:.2f}ms exceeds {MAX_MS_PER_BRAND}ms"
    )


# ---------------------------------------------------------------------------
# 3. Scoped CSS generation speed (per brand)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("brand_key", ALL_BRAND_KEYS)
def test_scoped_css_generation_speed(registry, brand_key: str):
    """generate_scoped_brand_css() must complete in < 10 ms per brand."""
    brand = registry[brand_key]

    timings: list[float] = []
    for _ in range(ITERATIONS):
        start = time.perf_counter()
        css = generate_scoped_brand_css(brand_key, brand)
        elapsed_ms = (time.perf_counter() - start) * 1000
        timings.append(elapsed_ms)

    p95 = sorted(timings)[int(len(timings) * 0.95)]

    assert f'[data-brand="{brand_key}"]' in css
    assert p95 < MAX_MS_PER_BRAND, (
        f"{brand_key}: scoped CSS p95={p95:.2f}ms exceeds {MAX_MS_PER_BRAND}ms"
    )


# ---------------------------------------------------------------------------
# 4. All-brands CSS generation (batch)
# ---------------------------------------------------------------------------
def test_all_brands_css_generation_speed(registry):
    """generate_all_brands_css() for 5 brands must complete in < 50 ms."""
    brands = {k: registry[k] for k in ALL_BRAND_KEYS}

    timings: list[float] = []
    for _ in range(ITERATIONS):
        start = time.perf_counter()
        css = generate_all_brands_css(brands)
        elapsed_ms = (time.perf_counter() - start) * 1000
        timings.append(elapsed_ms)

    p95 = sorted(timings)[int(len(timings) * 0.95)]
    median = statistics.median(timings)

    # Must contain all 5 brand selectors
    for key in ALL_BRAND_KEYS:
        assert f'[data-brand="{key}"]' in css

    assert p95 < MAX_MS_ALL_BRANDS, (
        f"All-brands CSS p95={p95:.2f}ms exceeds {MAX_MS_ALL_BRANDS}ms "
        f"(median={median:.2f}ms)"
    )


# ---------------------------------------------------------------------------
# 5. ThemeContext construction speed (per brand)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("brand_key", ALL_BRAND_KEYS)
def test_theme_context_construction_speed(registry, brand_key: str):
    """ThemeContext construction must complete in < 15 ms per brand."""
    brand = registry[brand_key]

    timings: list[float] = []
    for _ in range(ITERATIONS):
        start = time.perf_counter()
        ctx = ThemeContext(
            brand_key=brand_key,
            brand_config=brand,
            css_variables=generate_brand_css_variables(brand),
            inline_style=generate_inline_style(brand),
            google_fonts_url=get_google_fonts_url(brand),
        )
        elapsed_ms = (time.perf_counter() - start) * 1000
        timings.append(elapsed_ms)

    p95 = sorted(timings)[int(len(timings) * 0.95)]

    # Validate the context is correct
    assert ctx.brand_key == brand_key
    assert len(ctx.css_variables) >= 40

    assert p95 < MAX_MS_THEME_CTX, (
        f"{brand_key}: ThemeContext construction p95={p95:.2f}ms exceeds "
        f"{MAX_MS_THEME_CTX}ms"
    )


# ---------------------------------------------------------------------------
# 6. ThemeMiddleware cache effectiveness
# ---------------------------------------------------------------------------
def test_middleware_cache_returns_identical_object():
    """Cached ThemeContext must be the *same* object (identity check)."""
    from unittest.mock import MagicMock

    mw = ThemeMiddleware(MagicMock())

    first = mw._build_theme_context("httbrands")
    second = mw._build_theme_context("httbrands")

    assert first is second, "Cache miss: middleware returned a new object"


def test_middleware_cache_speed():
    """Second call to _build_theme_context (cached) must be < 0.1 ms."""
    from unittest.mock import MagicMock

    mw = ThemeMiddleware(MagicMock())

    # Warm the cache
    mw._build_theme_context("frenchies")

    timings: list[float] = []
    for _ in range(ITERATIONS):
        start = time.perf_counter()
        mw._build_theme_context("frenchies")
        elapsed_ms = (time.perf_counter() - start) * 1000
        timings.append(elapsed_ms)

    p95 = sorted(timings)[int(len(timings) * 0.95)]
    assert p95 < 0.1, (
        f"Cached theme context lookup p95={p95:.4f}ms — should be < 0.1 ms"
    )
