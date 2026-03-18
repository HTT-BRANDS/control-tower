# =============================================================================
# Azure Governance Platform - Production Dockerfile
# Multi-stage build for optimized container size and security
# =============================================================================

# -----------------------------------------------------------------------------
# Stage 1: Build dependencies
# -----------------------------------------------------------------------------
FROM acrgovstaging19859.azurecr.io/python:3.11-slim-bookworm as builder

# Build arguments
ARG PYTHON_VERSION=3.11

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast Python package management
RUN pip install --no-cache-dir uv

# Set work directory
WORKDIR /build

# Copy dependency files
COPY pyproject.toml uv.lock ./
COPY README.md ./

# Install dependencies using uv
# --system flag installs to system Python (needed for multi-stage)
RUN uv pip install --system -e . \
    && uv pip install --system gunicorn uvicorn

# Clean up
RUN rm -rf /root/.cache

# -----------------------------------------------------------------------------
# Stage 2: Production image
# -----------------------------------------------------------------------------
FROM acrgovstaging19859.azurecr.io/python:3.11-slim-bookworm as production

LABEL maintainer="Cloud Governance Team" \
      application="Azure Governance Platform" \
      version="1.0.0"

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    PYTHONHASHSEED=random \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    APP_HOME=/app \
    APP_USER=appuser \
    APP_GROUP=appgroup \
    PORT=8000 \
    # App Service specific settings
    WEBSITE_HEALTHCHECK_MAXPINGFAILURES=3 \
    WEBSITES_PORT=8000

# Install ODBC runtime + Microsoft ODBC Driver 18 for SQL Server
# NOTE: libodbc2 (libodbc.so.2) must be installed from the standard Debian repo
#       first; the Microsoft repo provides msodbcsql18 (the actual MSSQL driver).
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl gnupg2 apt-transport-https ca-certificates \
    # ODBC runtime — provides libodbc.so.2 required by pyodbc at startup
    libodbc2 libodbccr2 unixodbc \
    && curl -sSL https://packages.microsoft.com/keys/microsoft.asc \
       | gpg --dearmor > /usr/share/keyrings/microsoft.gpg \
    && echo "deb [signed-by=/usr/share/keyrings/microsoft.gpg] https://packages.microsoft.com/debian/12/prod bookworm main" \
       > /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql18 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/* \
    # Refresh dynamic linker cache after installing ODBC libraries
    && ldconfig

# Create non-root user for security
RUN groupadd --gid 1000 ${APP_GROUP} && \
    useradd --uid 1000 --gid ${APP_GROUP} \
    --shell /bin/bash --create-home ${APP_USER}

# Set work directory
WORKDIR ${APP_HOME}

# Copy installed packages from builder stage
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Smoke-test: verify pyodbc can import against the system libodbc.so.2.
# This fails the BUILD (not just runtime) if the ODBC runtime is missing.
RUN python3 -c "import pyodbc; print('pyodbc import OK — libodbc.so.2 found')"

# Copy application code
COPY --chown=${APP_USER}:${APP_GROUP} app/ ./app/
COPY --chown=${APP_USER}:${APP_GROUP} scripts/ ./scripts/
COPY --chown=${APP_USER}:${APP_GROUP} README.md ./
COPY --chown=${APP_USER}:${APP_GROUP} config/ ./config/
COPY --chown=${APP_USER}:${APP_GROUP} alembic/ ./alembic/
COPY --chown=${APP_USER}:${APP_GROUP} alembic.ini ./

# Create necessary directories
RUN mkdir -p /home/data /home/logs /tmp && \
    chown -R ${APP_USER}:${APP_GROUP} /home/data /home/logs /tmp && \
    chmod 755 /home/data /home/logs

# Copy entrypoint script
COPY --chown=${APP_USER}:${APP_GROUP} scripts/entrypoint.sh ./scripts/entrypoint.sh
RUN chmod +x ./scripts/entrypoint.sh

# Switch to non-root user
USER ${APP_USER}

# Health check — longer start period to allow migrations + cold DB start
HEALTHCHECK --interval=30s --timeout=10s --start-period=90s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

# Expose port
EXPOSE ${PORT}

# Run migrations then start — entrypoint handles both
ENTRYPOINT ["./scripts/entrypoint.sh"]

# -----------------------------------------------------------------------------
# Stage 3: Development image (optional - includes dev dependencies)
# -----------------------------------------------------------------------------
FROM builder as development

LABEL maintainer="Cloud Governance Team" \
      application="Azure Governance Platform" \
      version="1.0.0-dev"

# Install development dependencies
RUN uv pip install --system -e ".[dev]"

WORKDIR /app

# Copy full application
COPY . .

# Create data directory
RUN mkdir -p /app/data && chmod 755 /app/data

# Run in development mode
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
