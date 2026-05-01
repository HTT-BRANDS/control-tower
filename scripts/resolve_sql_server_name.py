#!/usr/bin/env python3
"""Resolve an Azure SQL Server resource name from a database connection string."""

from __future__ import annotations

import argparse
import os
import re
from urllib.parse import unquote, urlparse

_AZURE_SQL_FQDN_RE = re.compile(
    r"(?P<server>[A-Za-z0-9-]+)\.database\.windows\.net",
    re.IGNORECASE,
)
_INVALID_SERVER_NAMES = {"", "localhost", "127", "sqladmin", "admin", "administrator"}


class SqlServerNameError(ValueError):
    """Raised when a SQL Server resource name cannot be safely resolved."""


def _strip_host_noise(host: str) -> str:
    host = unquote(host.strip().strip("'\""))
    if host.lower().startswith("tcp:"):
        host = host[4:]
    if "," in host:
        host = host.split(",", 1)[0]
    elif ":" in host and not host.startswith("["):
        host = host.split(":", 1)[0]
    return host.strip().strip(".")


def _server_name_from_host(host: str | None) -> str | None:
    if not host:
        return None
    clean_host = _strip_host_noise(host)
    if not clean_host:
        return None
    match = _AZURE_SQL_FQDN_RE.search(clean_host)
    if match:
        return match.group("server")
    if "." in clean_host:
        return clean_host.split(".", 1)[0]
    return clean_host


def resolve_sql_server_name(database_url: str) -> str:
    """Return the Azure SQL Server resource name for a connection string.

    The backup workflow receives environment-scoped ``DATABASE_URL`` secrets.
    Those secrets may be SQLAlchemy URLs or ODBC-style semicolon-delimited
    strings. Prefer extracting ``*.database.windows.net`` anywhere in the full
    string because URL parsing can misidentify usernames as hosts for malformed
    or partially encoded secrets.
    """
    if not database_url or not database_url.strip():
        raise SqlServerNameError("DATABASE_URL is empty")

    decoded_database_url = unquote(database_url)
    fqdn_match = _AZURE_SQL_FQDN_RE.search(decoded_database_url)
    if fqdn_match:
        candidate = fqdn_match.group("server")
    else:
        parsed = urlparse(database_url)
        candidate = _server_name_from_host(parsed.hostname)

        if candidate is None:
            odbc_parts = decoded_database_url.split(";")
            server_part = next(
                (
                    part.split("=", 1)[1]
                    for part in odbc_parts
                    if "=" in part
                    and part.split("=", 1)[0].strip().lower() in {"server", "addr", "address"}
                ),
                None,
            )
            candidate = _server_name_from_host(server_part)

    server_name = (candidate or "").strip().lower()
    if server_name in _INVALID_SERVER_NAMES:
        raise SqlServerNameError(
            f"Resolved invalid Azure SQL server name {server_name!r}; check DATABASE_URL formatting"
        )
    if not re.fullmatch(r"[a-z0-9-]{1,63}", server_name):
        raise SqlServerNameError("Resolved Azure SQL server name contains unsupported characters")
    return server_name


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--env-var",
        default="DATABASE_URL",
        help="Environment variable containing the database connection string.",
    )
    args = parser.parse_args()
    print(resolve_sql_server_name(os.environ.get(args.env_var, "")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
