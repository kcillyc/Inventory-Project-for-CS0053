from dataclasses import dataclass
from datetime import datetime

"""
Contains data models for the inventory management system.
"""

@dataclass
class Product:
    id: int | None
    sku: str # Stock Keeping Unit
    name: str
    category: str
    quantity: int
    unit_cost_cents: int
    reorder_level: int
    version: int = 1
    archived: bool = False

@dataclass
class Movement: # Change in stock level for a product
    id: int | None
    product_id: int
    sku: str
    name: str
    delta: int # signed stock change (positive for incoming, negative for outgoing)
    balance: int
    reason: str
    created_at: datetime = datetime.now()