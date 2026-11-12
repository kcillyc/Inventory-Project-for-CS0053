import re
"""
This module provides validation for data inputs before they are processed or stored in the inventory management system.
"""

# SKU pattern: must start with an uppercase letter or digit, followed by any combination of uppercase letters, digits, underscores, or hyphens.
SKU_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9_-]*$")

def normalize_sku(sku : str) -> str:
    '''
    Validates and normalizes a SKU string.
    Raises ValueError if the SKU is invalid.
    '''

    normalized_sku = sku.strip().upper()

    if not normalized_sku:
        raise ValueError("SKU cannot be empty.")

    if len(normalized_sku) > 30:
        raise ValueError("SKU cannot exceed 30 characters.")

    if not SKU_PATTERN.match(normalized_sku):
        raise ValueError(
            "SKU must start with an uppercase letter or digit," \
            "followed by uppercase letters, digits, underscores, or hyphens."
        )

    return normalized_sku

def validate_text(value: str, field_name: str, max_length: int) -> str:
    '''
    Validates a text field for emptiness and length constraints.
    Raises ValueError if the field is invalid.
    '''
    
    cleaned_value = value.strip()

    if not cleaned_value:
        raise ValueError(f"{field_name} cannot be empty.")

    if len(cleaned_value) > max_length:
        raise ValueError(f"{field_name} cannot exceed {max_length} characters.")

    return cleaned_value

def validate_positive_integer(value: int, field_name: str) -> int:
    '''
    Validates that a given value is a non-negative integer.
    '''

    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{field_name} must be a whole number.")

    if value < 0:
        raise ValueError(f"{field_name} must not be a negative integer.")

    return value

def validate_adjustment(delta: int) -> int:
    if not isinstance(delta, int) or isinstance(delta, bool):
        raise ValueError("Adjustment delta must be a whole number.")

    if delta == 0:
        raise ValueError("Stock adjustment cannot be zero.")

    return delta