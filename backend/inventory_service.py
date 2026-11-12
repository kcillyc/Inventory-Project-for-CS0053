from models import Product
from repository_interface import InventoryRepository
from validators import (
    normalize_sku,
    validate_adjustment,
    validate_positive_integer,
    validate_reason,
    validate_text
)

class InventoryService:
    def __init__(self, repository: InventoryRepository):
        self.repository = repository

    def create_product(
            self,
            sku: str,
            name: str,
            category: str,
            quantity: int,
            unit_cost_cents: int,
            reorder_level: int
    ) -> Product:

        # Normalize and validate text/str inputs
        normalized_sku = normalize_sku(sku)
        cleaned_name = validate_text(name, "Name", 100)
        cleaned_category = validate_text(category, "Category", 60)

        # Validate integer inputs
        validate_positive_integer(quantity, "Quantity")
        validate_positive_integer(unit_cost_cents, "Unit cost")
        validate_positive_integer(reorder_level, "Reorder level")

        # Check if a product with the same SKU already exists
        existing_product = self.repository.get_product_by_sku(normalized_sku)

        if existing_product is not None:
            raise ValueError(f"Product with SKU '{normalized_sku}' already exists.")

        # Create new Product with cleaned and validated data
        product = Product(
            id = None,
            sku = normalized_sku,
            name = cleaned_name,
            category = cleaned_category,
            quantity = quantity,
            unit_cost_cents = unit_cost_cents,
            reorder_level = reorder_level
        )

        return self.repository.create_product(product)