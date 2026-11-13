"""
Contains data models for the inventory management system.
"""

from dataclasses import dataclass, field
from datetime import datetime

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
    created_at: datetime = field(default_factory = datetime.now)