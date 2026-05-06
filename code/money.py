"""
Money handling utilities for payment system.

CRITICAL: All money operations must use integer kopecks (cents) internally
to avoid float arithmetic precision errors.

Float arithmetic errors:
    4.01 * 100 = 401.00000000000006  # Wrong
    int(Decimal("4.01") * 100) = 401  # Correct

This module provides safe money conversion and validation functions.
"""

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation


class MoneyError(ValueError):
    """Raised when money conversion or validation fails."""


def to_kopecks(amount: int | float | str | Decimal) -> int:
    """
    Convert amount to integer kopecks (cents) safely.

    This is the ONLY safe way to convert money amounts for internal storage
    and calculations. Never use float arithmetic directly.

    Args:
        amount: Amount in UAH (major units). Can be:
            - int: 50 → 5000 kopecks
            - float: 50.25 → 5025 kopecks (caution: precision issues)
            - str: "50.25" → 5025 kopecks (recommended)
            - Decimal: Decimal("50.25") → 5025 kopecks (best)

    Returns:
        Amount in kopecks (integer)

    Raises:
        MoneyError: If amount is invalid or cannot be converted
    """
    if amount is None:
        msg = "Amount cannot be None"
        raise MoneyError(msg)

    try:
        if isinstance(amount, Decimal):
            decimal_amount = amount
        elif isinstance(amount, str):
            decimal_amount = Decimal(amount)
        elif isinstance(amount, int | float):
            decimal_amount = Decimal(str(amount))
        else:
            msg = f"Invalid amount type: {type(amount).__name__}"
            raise MoneyError(msg)

        kopecks_decimal = decimal_amount * 100
        return int(
            kopecks_decimal.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        )

    except (InvalidOperation, ValueError, TypeError) as e:
        msg = f"Failed to convert amount to kopecks: {amount!r} ({e})"
        raise MoneyError(msg) from e


def to_uah(kopecks: int) -> Decimal:
    """
    Convert kopecks to UAH (major units) as Decimal.

    Args:
        kopecks: Amount in kopecks (integer)

    Returns:
        Amount in UAH as Decimal (e.g., Decimal("50.25"))
    """
    if not isinstance(kopecks, int):
        msg = f"Kopecks must be integer, got {type(kopecks).__name__}"
        raise MoneyError(msg)

    return Decimal(kopecks) / 100


def to_uah_str(kopecks: int, decimal_places: int = 2) -> str:
    """
    Convert kopecks to UAH string for API/display.

    Args:
        kopecks: Amount in kopecks (integer)
        decimal_places: Number of decimal places (default: 2)

    Returns:
        Amount as string (e.g., "50.25")
    """
    decimal_amount = to_uah(kopecks)
    format_str = f"{{:.{decimal_places}f}}"
    return format_str.format(decimal_amount)


def compare_amounts(
    expected_kopecks: int,
    received_kopecks: int,
    tolerance_kopecks: int = 100,
) -> tuple[bool, int]:
    """
    Compare two amounts with tolerance (for payment verification).

    Args:
        expected_kopecks: Expected amount in kopecks
        received_kopecks: Received amount in kopecks
        tolerance_kopecks: Allowed difference (default: 100 = 1 UAH)

    Returns:
        Tuple of (is_match, difference_kopecks)
    """
    difference = abs(received_kopecks - expected_kopecks)
    is_match = difference <= tolerance_kopecks
    return is_match, difference


def validate_amount(
    amount: int | float | str | Decimal,
    min_kopecks: int = 100,
) -> int:
    """
    Validate and convert amount to kopecks.

    Args:
        amount: Amount in UAH (any supported type)
        min_kopecks: Minimum allowed amount in kopecks (default: 100 = 1 UAH)

    Returns:
        Amount in kopecks (integer)

    Raises:
        MoneyError: If amount is invalid or below minimum
    """
    kopecks = to_kopecks(amount)

    if kopecks < min_kopecks:
        msg = (
            f"Amount {kopecks} kopecks is below minimum {min_kopecks} kopecks "
            f"({to_uah_str(kopecks)} UAH < {to_uah_str(min_kopecks)} UAH)"
        )
        raise MoneyError(msg)

    return kopecks


def format_amount_display(kopecks: int, currency: str = "UAH") -> str:
    """
    Format amount for user display.

    Args:
        kopecks: Amount in kopecks
        currency: Currency code (default: "UAH")

    Returns:
        Formatted string (e.g., "50.25 UAH")
    """
    return f"{to_uah_str(kopecks)} {currency}"


__all__ = [
    "MoneyError",
    "compare_amounts",
    "format_amount_display",
    "to_kopecks",
    "to_uah",
    "to_uah_str",
    "validate_amount",
]
