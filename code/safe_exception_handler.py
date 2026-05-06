"""
Safe exception handling with PII masking for logging.

This module provides utilities to safely log exceptions without exposing
personal identifiable information (PII) like phone numbers, emails.
"""

import logging
import re
from typing import Any
from urllib.parse import urlparse, urlunparse

logger = logging.getLogger(__name__)


def mask_pii(text: str) -> str:
    """Mask phones and emails in string for safe logging.

    Phones: UA +380/380/0XX (with and without plus)
    Emails: user@domain.com -> u***@domain.com
    """
    if not text:
        return text

    # UA phone numbers
    text = re.sub(
        r"(\+?380|0)[\s\-]*\d{2}[\s\-]*(\d{3})[\s\-]*(\d{4})",
        lambda m: f"{m.group(1)}***{m.group(3)}",
        text,
    )
    # International phones: mask tail
    text = re.sub(
        r"(\+\d{1,4})[\s\-]*\d[\s\-]*\d[\s\-]*\d[\s\-]*\d[\s\-]*\d[\s\-]*\d"
        r"(?:\d[\s\-]*)*",
        lambda m: m.group(1) + "***",
        text,
    )
    # Email: user@domain.com -> u***@domain.com
    return re.sub(
        r"([a-zA-Z0-9._%+-]{1})[a-zA-Z0-9._%+-]+(@[a-zA-Z0-9.-]+)",
        r"\1***\2",
        text,
    )


def mask_database_url(url: str | None) -> str | None:
    """Mask password in database URL.

    Example: postgresql://user:password@host:5432/db
             -> postgresql://user:***@host:5432/db
    """
    if not url:
        return url

    try:
        parsed = urlparse(url)
        if parsed.password:
            masked_netloc = f"{parsed.username}:***@{parsed.hostname}"
            if parsed.port:
                masked_netloc += f":{parsed.port}"
            return urlunparse(
                (
                    parsed.scheme,
                    masked_netloc,
                    parsed.path,
                    parsed.params,
                    parsed.query,
                    parsed.fragment,
                )
            )
    except (ValueError, TypeError):
        return "***DATABASE_URL***"

    return url


def mask_sql_query(query: str | None) -> str | None:
    """Mask potential PII in SQL queries.

    Masks string values in WHERE conditions, INSERT VALUES, etc.
    """
    if not query:
        return query

    try:
        # Mask strings in quotes
        masked = re.sub(r"'([^']{3,})'", r"'***'", query)
        # Mask numeric values (potential phone IDs)
        masked = re.sub(r"\b(\d{6,})\b", "***", masked)
        # Mask emails in queries
        return re.sub(
            r"([a-zA-Z0-9._%+-]{1})[a-zA-Z0-9._%+-]+(@[a-zA-Z0-9.-]+)",
            r"\1***\2",
            masked,
        )
    except (ValueError, TypeError):
        return query[:100] + "..." if len(query) > 100 else query


def mask_exception_data(exc_str: str) -> str:
    """Mask PII in exception strings.

    Applies all masking types to protect data in tracebacks.
    """
    if not exc_str:
        return exc_str

    # Apply all masking
    masked = mask_pii(exc_str) or ""
    masked = mask_database_url(masked) or masked
    masked = mask_sql_query(masked) or masked

    # Truncate long strings (may contain PII)
    if len(masked) > 500:
        masked = masked[:250] + "..." + masked[-250:]

    return masked


_MASK_SENSITIVE_KEYS = frozenset(
    {
        "password",
        "token",
        "secret",
        "key",
        "auth",
        "credential",
        "phone",
        "email",
        "address",
        "url",
        "path",
    }
)
_MASK_MAX_DEPTH = 20


def mask_sensitive_dict(
    data: Any, _depth: int = 0, _seen: set[Any] | None = None
) -> Any:
    """Recursively mask sensitive data in dictionary.

    Used for safe logging of structured data.

    Features:
    - Cycle detection to handle circular references
    - Max depth hard-cap to prevent OOM on deep structures
    """
    if _depth > _MASK_MAX_DEPTH:
        return "***DEPTH_LIMIT***"

    if not isinstance(data, dict | list):
        return data

    if _seen is None:
        _seen = set()

    obj_id = id(data)
    if obj_id in _seen:
        return "***CIRCULAR_REF***"
    _seen.add(obj_id)

    try:
        if isinstance(data, list):
            return [
                (
                    mask_sensitive_dict(item, _depth + 1, _seen)
                    if isinstance(item, dict | list)
                    else mask_pii(str(item))
                )
                for item in data
            ]

        masked_data = {}
        for key, value in data.items():
            key_lower = str(key).lower()
            is_sensitive = any(
                sensitive in key_lower for sensitive in _MASK_SENSITIVE_KEYS
            )

            if is_sensitive:
                masked_data[key] = "***"
            elif isinstance(value, dict | list):
                masked_data[key] = mask_sensitive_dict(value, _depth + 1, _seen)
            else:
                masked_data[key] = value

        return masked_data
    finally:
        _seen.discard(obj_id)


class SafeExceptionHandler:
    """Exception handler that safely logs errors without PII."""

    def __init__(self, logger: logging.Logger | None = None) -> None:
        self.logger = logger or logging.getLogger(__name__)

    def log_exception(
        self, exc: Exception, context: dict[str, Any] | None = None
    ) -> None:
        """Log exception with masked PII.

        Args:
            exc: The exception to log
            context: Additional context (will be masked for sensitive keys)
        """
        # Mask exception string
        exc_str = mask_exception_data(str(exc))
        exc_type = type(exc).__name__

        # Mask context if provided
        safe_context = None
        if context:
            safe_context = mask_sensitive_dict(context)

        if safe_context:
            self.logger.error(
                "%s: %s | Context: %s",
                exc_type,
                exc_str,
                safe_context,
                exc_info=True,
            )
        else:
            self.logger.error(
                "%s: %s",
                exc_type,
                exc_str,
                exc_info=True,
            )

    def format_error_response(self, exc: Exception) -> dict[str, str]:
        """Format error for API response (never expose internals).

        Args:
            exc: The exception

        Returns:
            Safe error dict for API response
        """
        return {
            "error": "Internal server error",
            "code": type(exc).__name__,
        }


__all__ = [
    "mask_pii",
    "mask_database_url",
    "mask_sql_query",
    "mask_exception_data",
    "mask_sensitive_dict",
    "SafeExceptionHandler",
]
