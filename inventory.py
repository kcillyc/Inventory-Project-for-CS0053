"""Keep the original demo entry points while repositories own all SQL.

The short helper names remain available for existing team code. New callers
should use the descriptive functions or InventoryService directly.
"""

from sqlite3 import Error as SQLiteError

from backend.inventory_service import InventoryService
from backend.sqlite_repository import SQLiteInventoryRepository, initialize_database

DB = "inventory.db"


def _inventory_service():
    """Create persistence only when a compatibility function is called."""
    return InventoryService(SQLiteInventoryRepository(DB))


def create_database(db_path=None, *, announce=True):
    """Initialize or migrate the database through the repository module."""
    backup = initialize_database(DB if db_path is None else db_path)
    if announce:
        print("Database is ready")
    return backup


def add_product(sku, name, category, quantity, unit_cost_cents, reorder_level):
    """Validate and save a product, including its opening movement."""
    product = _inventory_service().create_product(
        sku, name, category, quantity, unit_cost_cents, reorder_level
    )
    print("Product added successfully")
    return product


def show_products():
    """Display the original six product fields for active products."""
    products = _inventory_service().search_products("")
    for product in products:
        print(
            (
                product.id,
                product.sku,
                product.name,
                product.category,
                product.quantity,
                product.unit_cost_cents,
            )
        )
    return products


def record_movement(product_id, amount, reason):
    """Record stock changes atomically and keep legacy readable errors."""
    try:
        product = _inventory_service().adjust_stock(product_id, amount, reason)
    except ValueError as error:
        print(f"Error: {error}")
        return None
    print("Stock movement successfully recorded")
    return product


def addprod(sku, name, category, quantity, unit_costs_cents, reorder_level):
    """Support the original name and plural cost keyword without legacy SQL."""
    return add_product(
        sku, name, category, quantity, unit_costs_cents, reorder_level
    )


def showprod():
    """Support the original product-listing entry point."""
    return show_products()


def recmove(product_id, amount, reason):
    """Support the original stock-adjustment entry point."""
    return record_movement(product_id, amount, reason)


def main():
    """Run the original notebook example once without reseeding saved stock."""
    try:
        service = _inventory_service()
        if service.repository.get_product_by_sku("NB001") is None:
            product = service.create_product(
                "NB001", "Notebook", "School Supplies", 20, 5000, 5
            )
            service.adjust_stock(product.id, 10, "Supplier delivery")
            service.adjust_stock(product.id, -5, "Issued to classroom")
        else:
            print("Demonstration product already exists; saved stock is unchanged.")
        show_products()
        return 0
    except (ValueError, RuntimeError, SQLiteError, OSError) as error:
        print(f"Error: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
