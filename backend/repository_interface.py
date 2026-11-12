"""
Defines the InventoryRepository interface, 
which outlines the methods for interacting with the inventory data.
"""

from typing import Protocol
from models import Product, Movement

class InventoryRepository(Protocol):
    def create_product(self, product: Product) -> Product:
        '''
        Creates a new product in the inventory.
        '''
        # TODO: Implement the method to create a new product in the inventory.
        ...

    def get_product_by_sku(self, sku: str) -> Product | None:
        '''
        Retrieves a product from the inventory by its SKU.
        '''
        # TODO: Implement the method to retrieve a product by its SKU.
        ...

    def get_product_by_id(self, product_id: int) -> Product | None:
        '''
        Retrieves a product from the inventory by its ID.
        '''
        # TODO: Implement the method to retrieve a product by its ID.
        ...

    def update_product(
            self, 
            product_id: int,
            delta: int,
            reason: str,
        ) -> Product:
        '''
        Updates the stock level of a product and records the movement.
        '''
        # TODO: Implement the method to update a product's stock level and record the movement.
        ...

    def archive_product(self, product_id: int) -> Product:
        '''
        Archives a product in the inventory.
        '''
        # TODO: Implement the method to archive a product.
        ...

    def list_products(self) -> list[Product]:
        '''
        Lists all products in the inventory.
        '''
        # TODO: Implement the method to list all products.
        ...

    def list_movements(self, limit: int = 200) -> list[Movement]:
        '''
        Lists all stock movements in the inventory, limited to a specified number.
        '''
        # TODO: Implement the method to list all stock movements.
        ...