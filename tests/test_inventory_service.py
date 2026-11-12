"""
Testing inventory service with fake InventoryRepository
"""

import unittest

from backend.inventory_service import InventoryService
from backend.models import Product

class FakeInventoryRepository:
    def __init__(self):
        self.products = {}
        self.next_id = 1

    def create_product(self, product: Product) -> Product:
        '''
        Simulates creating a product in the repository.
        '''
        
        product.id = self.next_id
        self.products[product.id] = product
        self.next_id += 1
        return product

    def get_product_by_sku(self, sku: str) -> Product:
        '''
        Simulates retrieving a product by SKU from the repository.
        '''
        return next(
            (
                product 
                for product in self.products.values() 
                if product.sku == sku
            ), 
            None
        )

    def get_product_by_id(self, product_id: int) -> Product:
        '''
        Simulates retrieving a product by ID from the repository.
        '''
        return self.products.get(product_id, None)

    def list_products(self) -> list[Product]:
        '''
        Simulates listing all products in the repository.
        '''
        return list(self.products.values())

    def adjust_stock(self, product_id: int, delta: int, reason: str) -> Product:
        '''
        Simulates adjusting the stock of a product in the repository.
        '''
        product = self.get_product_by_id(product_id)
        
        if product is None:
            raise ValueError(f"Product with ID '{product_id}' does not exist.")
        
        product.quantity += delta
        product.version += 1  # Increment version for optimistic locking
        
        return product

class InventoryServiceTests(unittest.TestCase):
    def setUp(self):
        self.repository = FakeInventoryRepository()
        self.inventory_service = InventoryService(self.repository)

    def test_create_product_normalize_sku(self):
        '''
        Test that creating a product normalizes the SKU to uppercase and rejects duplicates.
        '''
        product = self.inventory_service.create_product(
            sku = "pen-001",
            name = "Blue Pen",
            category = "Supplies",
            quantity = 10,
            unit_cost_cents = 2500,
            reorder_level = 3
        )
        self.assertEqual(product.sku, "PEN-001") # Check that SKU is normalized to uppercase

    def test_duplicate_sku_is_rejected(self):
        '''
        Test that creating a product with a duplicate SKU raises a ValueError.
        '''
        product_data = {
            "sku": "PEN-001",
            "name": "Blue Pen",
            "category": "Supplies",
            "quantity": 10,
            "unit_cost_cents": 2500,
            "reorder_level": 3
        }

        self.inventory_service.create_product(**product_data) # Create the first product

        with self.assertRaises(ValueError):
            self.inventory_service.create_product(**product_data) # Attempt to create a duplicate product

    def test_stock_out_cannot_exceed_quantity(self):
        '''
        Test that adjusting stock to a negative quantity raises a ValueError.
        '''
        
        product = self.inventory_service.create_product(
            sku = "PEN-001",
            name = "Blue Pen",
            category = "Supplies",
            quantity = 5,
            unit_cost_cents = 2500,
            reorder_level = 3
        )

        with self.assertRaises(ValueError):
            self.inventory_service.adjust_stock(product.id, -6, "Stock issued")  # This would result in negative quantity

        self.assertEqual(product.quantity, 5)  # Quantity should remain unchanged

if __name__ == "__main__":
    unittest.main()