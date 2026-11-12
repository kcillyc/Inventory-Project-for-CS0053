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

