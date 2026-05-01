from __future__ import annotations

import pytest

from scripts.resolve_sql_server_name import SqlServerNameError, resolve_sql_server_name


def test_resolves_sqlalchemy_url() -> None:
    database_url = (
        "mssql+pyodbc://sql-governance-staging.database.windows.net:1433/"
        "governance?driver=ODBC+Driver+18+for+SQL+Server"
    )

    assert resolve_sql_server_name(database_url) == "sql-governance-staging"


def test_resolves_odbc_connection_string() -> None:
    database_url = (
        "Driver={ODBC Driver 18 for SQL Server};"
        "Server=tcp:sql-governance-production.database.windows.net,1433;"
        "Database=governance;Uid=sqladmin;Pwd=secret"
    )

    assert resolve_sql_server_name(database_url) == "sql-governance-production"


def test_prefers_azure_fqdn_over_misleading_url_hostname() -> None:
    database_url = (
        "mssql+pyodbc://sqladmin@sqladmin/ignored"
        "?odbc_connect=Server%3Dtcp%3Asql-real.database.windows.net%2C1433"
    )

    assert resolve_sql_server_name(database_url) == "sql-real"


def test_rejects_sqladmin_username_as_server_name() -> None:
    with pytest.raises(SqlServerNameError, match="invalid Azure SQL server name"):
        resolve_sql_server_name("mssql+pyodbc://sqladmin/governance")


def test_rejects_empty_database_url() -> None:
    with pytest.raises(SqlServerNameError, match="DATABASE_URL is empty"):
        resolve_sql_server_name("")
