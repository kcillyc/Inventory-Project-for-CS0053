"""Shared input rules for services and public repository methods."""

import re

MAX_INTEGER = 2**63 - 1
MIN_INTEGER = -(2**63)
SKU_PATTERN = re.compile(r"[A-Z0-9][A-Z0-9_-]*")


def validate_text(value, field_name, max_length, minimum=1):
    """Check types before trimming so invalid input gives a useful error."""
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be text.")
    cleaned = value.strip()
    if len(cleaned) < minimum:
        if minimum == 1:
            raise ValueError(f"{field_name} cannot be empty.")
        raise ValueError(f"{field_name} must contain at least {minimum} characters.")
    if len(cleaned) > max_length:
        raise ValueError(f"{field_name} cannot exceed {max_length} characters.")
    if any(ord(c) < 32 or ord(c) == 127 for c in cleaned):
        raise ValueError(f"{field_name} must not contain control characters.")
    return cleaned


def normalize_sku(sku):
    """Normalize a bounded product code with an ASCII character allowlist."""
    normalized = validate_text(sku, "SKU", 30).upper()
    if len(normalized) > 30 or not SKU_PATTERN.fullmatch(normalized):
        raise ValueError(
            "SKU must start with a letter or digit and use only letters, digits, hyphens, or underscores."
        )
    return normalized


def validate_integer(value, field_name, minimum=0, maximum=MAX_INTEGER):
    """Reject bools, fractions, and values outside SQLite's integer range."""
    if type(value) is not int:
        raise ValueError(f"{field_name} must be a whole number.")
    if not minimum <= value <= maximum:
        raise ValueError(f"{field_name} must be between {minimum} and {maximum}.")
    return value


def validate_non_negative_integer(value, field_name):
    """Require a bounded zero-or-positive stored value."""
    return validate_integer(value, field_name)


def validate_id(value, field_name="Product ID"):
    """Require a positive identifier, version, or limit."""
    return validate_integer(value, field_name, minimum=1)


def validate_adjustment(delta):
    """Require a nonzero signed whole-number stock change."""
    validate_integer(delta, "Stock adjustment", MIN_INTEGER)
    if delta == 0:
        raise ValueError("Stock adjustment cannot be zero.")
    return delta


def validate_reason(reason):
    """Require a visible explanation for every ordinary stock change."""
    return validate_text(reason, "Reason for stock adjustment", 200, minimum=3)


def validate_search(query):
    """An empty search intentionally lists all active products."""
    return validate_text(query, "Search query", 100, minimum=0)


def validate_product_details(sku, name, category, unit_cost_cents, reorder_level):
    """Canonical metadata shared by service and repository boundaries."""
    return {
        "sku": normalize_sku(sku),
        "name": validate_text(name, "Name", 100),
        "category": validate_text(category, "Category", 60),
        "unit_cost_cents": validate_non_negative_integer(unit_cost_cents, "Unit cost"),
        "reorder_level": validate_non_negative_integer(reorder_level, "Reorder level"),
    }
