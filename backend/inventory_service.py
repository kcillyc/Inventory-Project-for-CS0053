"""
Contains the InventoryService class, 
which provides business logic for managing products in an inventory system. 
It interacts with a repository to perform CRUD operations and includes validation for input data.

"""

from .models import Product
from .repository_interface import InventoryRepository
from .validators import (
    normalize_sku,
    validate_adjustment,
    validate_non_negative_integer,
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
        '''
        Creates a new product in the inventory after validating the input data.
        '''

        # Normalize and validate text/str inputs
        normalized_sku = normalize_sku(sku)
        cleaned_name = validate_text(name, "Name", 100)
        cleaned_category = validate_text(category, "Category", 60)

        # Validate integer inputs
        validate_non_negative_integer(quantity, "Quantity")
        validate_non_negative_integer(unit_cost_cents, "Unit cost")
        validate_non_negative_integer(reorder_level, "Reorder level")

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

    def adjust_stock(
            self,
            product_id: int,
            delta: int,
            reason: str
    ) -> Product:
        '''
        Adjusts the stock quantity of a product by a specified delta (positive or negative).
        Validates the adjustment and ensures that the product exists and is not archived.
        '''

        # Validate inputs
        validate_adjustment(delta)
        cleaned_reason = validate_reason(reason)

        product = self.repository.get_product_by_id(product_id)

        if product is None:
            raise ValueError(f"Product with ID '{product_id}' does not exist.")

        if product.archived:
            raise ValueError(f"Cannot adjust stock for archived product with ID '{product_id}'.")

        if product.quantity + delta < 0:
            raise ValueError(f"Stock adjustment would result in negative quantity for product with ID '{product_id}'.")

        return self.repository.adjust_stock(
            product_id = product_id,
            delta = delta,
            reason = cleaned_reason
        )

    def list_low_stock_products(self) -> list[Product]:
        '''
        Lists all products that are low on stock (quantity is less than or equal to the reorder level).
        '''

        products = self.repository.list_products()

        return [
            product
            for product in products
            if not product.archived and product.quantity <= product.reorder_level
        ]

    def search_products(self, query: str) -> list[Product]:
        '''
        Searches for products based on a query string that can match the SKU, name, or category.
        The search is case-insensitive and ignores archived products.
        '''

        term = query.strip().casefold() # Normalize the search term for case-insensitive matching

        return [
            product
            for product in self.repository.list_products()
            if not product.archived and (
                term in product.sku.casefold() or
                term in product.name.casefold() or
                term in product.category.casefold()
            )
        ]

    # def update_product 

    