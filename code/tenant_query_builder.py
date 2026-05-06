"""
SQLAlchemy Core utilities for tenant-aware queries.

This module provides safe, type-checked query building using SQLAlchemy Core
to ensure tenant isolation in multi-tenant operations.

Usage:
    from core.repositories.sqlalchemy_helpers import TenantQueryBuilder
    from db.models import Anketa

    # SELECT with tenant filter
    builder = TenantQueryBuilder(tenant_id="tenant_123")
    stmt = builder.select(Anketa).where(Anketa.status == "opened")
    query, params = builder.compile(stmt)

    # INSERT with tenant_id
    stmt = builder.insert(Anketa).values(
        anketa_id="123",
        desc="Description",
        status="opened"
    )
    query, params = builder.compile(stmt)
"""

from typing import Any

from sqlalchemy import (
    Delete,
    Insert,
    Select,
    Update,
    delete,
    insert,
    select,
    update,
)
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.sql import ClauseElement


class TenantQueryBuilder:
    """
    Safe query builder for tenant-aware operations using SQLAlchemy Core.

    Automatically adds tenant_id filters to SELECT/UPDATE/DELETE queries
    and tenant_id values to INSERT queries for tenant-scoped tables.

    Attributes:
        tenant_id: Current tenant ID for filtering
        tenant_scoped_tables: Set of table names that require tenant filtering
    """

    TENANT_SCOPED_TABLES = frozenset(
        {
            "vacancies",
            "business_config",
            "outbox_messages",
            "user_context_messages",
            "user_anketa_messages",
            "user_anketa_state",
            "payments",
            "subscriptions",
            "admin_actions",
            "ankety",
        }
    )

    def __init__(self, tenant_id: str | None = None):
        """
        Initialize query builder with tenant context.

        Args:
            tenant_id: Tenant ID for filtering
                (None = use current tenant context)
        """
        if tenant_id is None:
            try:
                from core.tenant_context import get_tenant_id
                tenant_id = get_tenant_id()
            except (LookupError, RuntimeError):
                tenant_id = "default"

        self.tenant_id = tenant_id

    def _is_tenant_scoped(self, table_name: str) -> bool:
        """Check if table requires tenant filtering."""
        return table_name in self.TENANT_SCOPED_TABLES

    def select(self, *entities: Any) -> Select[Any]:
        """
        Create SELECT statement with automatic tenant filtering.

        Args:
            *entities: SQLAlchemy model classes or columns to select

        Returns:
            Select statement (use .where() to add conditions, then compile())
        """
        stmt = select(*entities)

        for entity in entities:
            table_name = None
            if hasattr(entity, "__tablename__"):
                table_name = entity.__tablename__
            elif hasattr(entity, "table") and hasattr(entity.table, "name"):
                table_name = entity.table.name

            if table_name and self._is_tenant_scoped(table_name):
                if hasattr(entity, "tenant_id"):
                    stmt = stmt.where(entity.tenant_id == self.tenant_id)
                break

        return stmt

    def insert(self, table: Any) -> Insert:
        """
        Create INSERT statement with automatic tenant_id value.

        Args:
            table: SQLAlchemy model class

        Returns:
            Insert statement (use .values() to add data, then compile())
        """
        stmt = insert(table)
        return stmt

    def update(self, table: Any) -> Update:
        """
        Create UPDATE statement with automatic tenant filtering.

        Args:
            table: SQLAlchemy model class

        Returns:
            Update statement (use .where() and .values(), then compile())
        """
        stmt = update(table)

        table_name = getattr(table, "__tablename__", None)
        is_scoped = self._is_tenant_scoped(table_name) if table_name else False
        if is_scoped and hasattr(table, "tenant_id"):
            stmt = stmt.where(table.tenant_id == self.tenant_id)

        return stmt

    def delete(self, table: Any) -> Delete:
        """
        Create DELETE statement with automatic tenant filtering.

        Args:
            table: SQLAlchemy model class

        Returns:
            Delete statement (use .where() to add conditions, then compile())
        """
        stmt = delete(table)

        table_name = getattr(table, "__tablename__", None)
        is_scoped = self._is_tenant_scoped(table_name) if table_name else False
        if is_scoped and hasattr(table, "tenant_id"):
            stmt = stmt.where(table.tenant_id == self.tenant_id)

        return stmt

    def compile(self, stmt: ClauseElement) -> tuple[str, tuple[Any, ...]]:
        """
        Compile SQLAlchemy statement to PostgreSQL query string and params.

        Args:
            stmt: SQLAlchemy statement (Select, Insert, Update, Delete)

        Returns:
            Tuple of (query_string, params_tuple) ready for asyncpg
        """
        # Handle INSERT with tenant_id injection
        if isinstance(stmt, Insert):
            table_name = stmt.table.name if hasattr(stmt, "table") else None
            if (
                table_name
                and self._is_tenant_scoped(table_name)
                and hasattr(stmt, "parameters")
                and stmt.parameters
            ):
                params_dict = stmt.parameters[0]
                if "tenant_id" not in params_dict:
                    stmt = stmt.values(tenant_id=self.tenant_id)

        # Compile to PostgreSQL dialect
        compiled = stmt.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": False},
        )

        query = str(compiled)
        params = tuple(compiled.params.values()) if compiled.params else ()

        return query, params


def build_select_with_tenant(
    model_class: type[DeclarativeBase],
    tenant_id: str | None = None,
    **filters: Any,
) -> tuple[str, tuple[Any, ...]]:
    """
    Convenience function to build SELECT query with tenant filtering.

    Args:
        model_class: SQLAlchemy model class
        tenant_id: Tenant ID (None = use current context)
        **filters: Column filters (e.g., status="opened", anketa_id="123")

    Returns:
        Tuple of (query, params) ready for asyncpg
    """
    builder = TenantQueryBuilder(tenant_id)
    stmt = builder.select(model_class)

    for column_name, value in filters.items():
        if hasattr(model_class, column_name):
            column = getattr(model_class, column_name)
            stmt = stmt.where(column == value)

    return builder.compile(stmt)


def build_insert_with_tenant(
    model_class: type[DeclarativeBase],
    tenant_id: str | None = None,
    **values: Any,
) -> tuple[str, tuple[Any, ...]]:
    """
    Convenience function to build INSERT query with tenant_id.

    Args:
        model_class: SQLAlchemy model class
        tenant_id: Tenant ID (None = use current context)
        **values: Column values to insert

    Returns:
        Tuple of (query, params) ready for asyncpg
    """
    builder = TenantQueryBuilder(tenant_id)
    stmt = builder.insert(model_class).values(**values)
    return builder.compile(stmt)


__all__ = [
    "TenantQueryBuilder",
    "build_select_with_tenant",
    "build_insert_with_tenant",
]
