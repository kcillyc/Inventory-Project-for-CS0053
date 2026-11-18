import sqlite3
from datetime import datetime

from models import Product, Movement


DB = "inventory.db"

#input validation functions
def normalize_sku(value):
    if not isinstance(value, str):
        raise ValueError("SKU must be a string")

    value = value.strip().upper()

    if not value:
        raise ValueError("SKU cannot be empty")

    return value


def validate_text(value, field_name):
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")

    value = value.strip()

    if not value:
        raise ValueError(f"{field_name} cannot be empty")

    return value


def validate_reason(value):
    if not isinstance(value, str):
        raise ValueError("Reason must be a string")

    value = value.strip()

    if len(value) < 3 or len(value) > 200:
        raise ValueError("Reason must be between 3 and 200 characters")

    return value


def validate_integer(value, field_name, minimum=None):
    # bool is technically an integer in Python, so reject it separately
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field_name} must be an integer")

    if minimum is not None and value < minimum:
        raise ValueError(f"{field_name} must be at least {minimum}")

    return value

#inventory repository
class invRepo:

    # Initializes the database path
    def __init__(self, db_path=DB):
        self.db_path = db_path
        self.create_database()

    # Connects to SQLite
    def connect(self):
        connection = sqlite3.connect(self.db_path)
        connection.execute("PRAGMA foreign_keys = ON")
        connection.row_factory = sqlite3.Row
        return connection

    # Creates the database tables
    def create_database(self):
        with self.connect() as connection:

            connection.execute("""
                CREATE TABLE IF NOT EXISTS products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sku TEXT UNIQUE NOT NULL,
                    name TEXT NOT NULL,
                    category TEXT NOT NULL,
                    quantity INTEGER NOT NULL CHECK(quantity >= 0),
                    unit_cost_cents INTEGER NOT NULL
                        CHECK(unit_cost_cents >= 0),
                    reorder_level INTEGER NOT NULL
                        CHECK(reorder_level >= 0),
                    version INTEGER NOT NULL DEFAULT 1,
                    archived INTEGER NOT NULL DEFAULT 0
                )
            """)

            connection.execute("""
                CREATE TABLE IF NOT EXISTS movements (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_id INTEGER NOT NULL,
                    sku TEXT NOT NULL,
                    name TEXT NOT NULL,
                    delta INTEGER NOT NULL,
                    balance INTEGER NOT NULL,
                    reason TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(product_id) REFERENCES products(id)
                )
            """)

    # Converts a database row into a Product object
    def row_to_product(self, row):
        if row is None:
            return None

        return Product(
            id=row["id"],
            sku=row["sku"],
            name=row["name"],
            category=row["category"],
            quantity=row["quantity"],
            unit_cost_cents=row["unit_cost_cents"],
            reorder_level=row["reorder_level"],
            version=row["version"],
            archived=bool(row["archived"])
        )

    # Converts a database row into a Movement object
    def row_to_movement(self, row):
        return Movement(
            id=row["id"],
            product_id=row["product_id"],
            sku=row["sku"],
            name=row["name"],
            delta=row["delta"],
            balance=row["balance"],
            reason=row["reason"],
            created_at=datetime.fromisoformat(row["created_at"])
        )

    # Creates a new product
    def create_product(self, product):
        sku = normalize_sku(product.sku)
        name = validate_text(product.name, "Product name")
        category = validate_text(product.category, "Category")

        quantity = validate_integer(
            product.quantity,
            "Quantity",
            0
        )

        unit_cost_cents = validate_integer(
            product.unit_cost_cents,
            "Unit cost",
            0
        )

        reorder_level = validate_integer(
            product.reorder_level,
            "Reorder level",
            0
        )

        try:
            with self.connect() as connection:
                cursor = connection.execute("""
                    INSERT INTO products
                    (
                        sku,
                        name,
                        category,
                        quantity,
                        unit_cost_cents,
                        reorder_level
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    sku,
                    name,
                    category,
                    quantity,
                    unit_cost_cents,
                    reorder_level
                ))

                product_id = cursor.lastrowid

            # The transaction is committed after leaving the with-block
            return self.get_product_by_id(product_id)

        except sqlite3.IntegrityError as error:
            raise ValueError(
                "A product with this SKU already exists"
            ) from error

    # Gets a product using its SKU
    def get_product_by_sku(self, sku):
        sku = normalize_sku(sku)

        with self.connect() as connection:
            row = connection.execute("""
                SELECT *
                FROM products
                WHERE sku = ?
            """, (sku,)).fetchone()

            return self.row_to_product(row)

    # Gets a product using its ID
    def get_product_by_id(self, product_id):
        product_id = validate_integer(
            product_id,
            "Product ID",
            1
        )

        with self.connect() as connection:
            row = connection.execute("""
                SELECT *
                FROM products
                WHERE id = ?
            """, (product_id,)).fetchone()

            return self.row_to_product(row)

    # Searches products using SKU, name, or category
    def search_products(self, query):
        if not isinstance(query, str):
            raise ValueError("Search query must be a string")

        query = query.strip().casefold()

        if not query:
            raise ValueError("Search query cannot be empty")

        search_value = f"%{query}%"

        with self.connect() as connection:
            rows = connection.execute("""
                SELECT *
                FROM products
                WHERE lower(sku) LIKE ?
                   OR lower(name) LIKE ?
                   OR lower(category) LIKE ?
                ORDER BY id
            """, (
                search_value,
                search_value,
                search_value
            )).fetchall()

            return [
                self.row_to_product(row)
                for row in rows
            ]

    # Adds or removes stock and records the movement
    def adjust_stock(self, product_id, delta, reason):
        product_id = validate_integer(
            product_id,
            "Product ID",
            1
        )

        delta = validate_integer(
            delta,
            "Stock change"
        )

        reason = validate_reason(reason)

        with self.connect() as connection:
            product_row = connection.execute("""
                SELECT *
                FROM products
                WHERE id = ?
                  AND archived = 0
            """, (product_id,)).fetchone()

            if product_row is None:
                raise ValueError("Product not found")

            new_quantity = product_row["quantity"] + delta

            if new_quantity < 0:
                raise ValueError(
                    "Stock quantity cannot be negative"
                )

            connection.execute("""
                UPDATE products
                SET quantity = quantity + ?,
                    version = version + 1
                WHERE id = ?
            """, (
                delta,
                product_id
            ))

            connection.execute("""
                INSERT INTO movements
                (
                    product_id,
                    sku,
                    name,
                    delta,
                    balance,
                    reason,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                product_id,
                product_row["sku"],
                product_row["name"],
                delta,
                new_quantity,
                reason,
                datetime.now().isoformat(timespec="seconds")
            ))

            updated_row = connection.execute("""
                SELECT *
                FROM products
                WHERE id = ?
            """, (product_id,)).fetchone()

            return self.row_to_product(updated_row)

    # Updates product information
    def update_product(
        self,
        product_id,
        fields,
        expected_version
    ):
        product_id = validate_integer(
            product_id,
            "Product ID",
            1
        )

        expected_version = validate_integer(
            expected_version,
            "Expected version",
            1
        )

        if not isinstance(fields, dict):
            raise ValueError(
                "Fields must be provided as a dictionary"
            )

        allowed_fields = {
            "sku",
            "name",
            "category",
            "quantity",
            "unit_cost_cents",
            "reorder_level"
        }

        update_fields = {
            key: value
            for key, value in fields.items()
            if key in allowed_fields
        }

        if "sku" in update_fields:
            update_fields["sku"] = normalize_sku(
                update_fields["sku"]
            )

        if "name" in update_fields:
            update_fields["name"] = validate_text(
                update_fields["name"],
                "Product name"
            )

        if "category" in update_fields:
            update_fields["category"] = validate_text(
                update_fields["category"],
                "Category"
            )

        if "quantity" in update_fields:
            update_fields["quantity"] = validate_integer(
                update_fields["quantity"],
                "Quantity",
                0
            )

        if "unit_cost_cents" in update_fields:
            update_fields["unit_cost_cents"] = validate_integer(
                update_fields["unit_cost_cents"],
                "Unit cost",
                0
            )

        if "reorder_level" in update_fields:
            update_fields["reorder_level"] = validate_integer(
                update_fields["reorder_level"],
                "Reorder level",
                0
            )

        if not update_fields:
            return self.get_product_by_id(product_id)

        assignments = ", ".join(
            f"{field} = ?"
            for field in update_fields
        )

        values = list(update_fields.values())
        values.extend([
            product_id,
            expected_version
        ])

        try:
            with self.connect() as connection:
                cursor = connection.execute(f"""
                    UPDATE products
                    SET {assignments},
                        version = version + 1
                    WHERE id = ?
                      AND version = ?
                """, values)

                if cursor.rowcount == 0:
                    raise ValueError(
                        "Product was not found or its version is outdated"
                    )

                row = connection.execute("""
                    SELECT *
                    FROM products
                    WHERE id = ?
                """, (product_id,)).fetchone()

                return self.row_to_product(row)

        except sqlite3.IntegrityError as error:
            raise ValueError(
                "A product with this SKU already exists"
            ) from error

    # Archives a product
    def archive_product(self, product_id):
        product_id = validate_integer(
            product_id,
            "Product ID",
            1
        )

        with self.connect() as connection:
            cursor = connection.execute("""
                UPDATE products
                SET archived = 1,
                    version = version + 1
                WHERE id = ?
            """, (product_id,))

            if cursor.rowcount == 0:
                raise ValueError("Product not found")

            row = connection.execute("""
                SELECT *
                FROM products
                WHERE id = ?
            """, (product_id,)).fetchone()

            return self.row_to_product(row)

    # Returns all products
    def list_products(self):
        with self.connect() as connection:
            rows = connection.execute("""
                SELECT *
                FROM products
                ORDER BY id
            """).fetchall()

            return [
                self.row_to_product(row)
                for row in rows
            ]

    # Returns movement history
    def list_movements(self, limit=200):
        limit = validate_integer(
            limit,
            "Limit",
            1
        )

        with self.connect() as connection:
            rows = connection.execute("""
                SELECT *
                FROM movements
                ORDER BY id DESC
                LIMIT ?
            """, (limit,)).fetchall()

            return [
                self.row_to_movement(row)
                for row in rows
            ]