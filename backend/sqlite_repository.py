"""Adapt the team's original SQLite schema to InventoryRepository.

The legacy database column is named unit_costs_cents (plural). This adapter maps
it to Product.unit_cost_cents without renaming columns or replacing stored data.
"""

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from inventory import create_database

from .models import Movement, Product

MAX_INTEGER = 2**63 - 1


class SQLiteInventoryRepository:
    """Provide the persistence methods expected by the team's InventoryService."""

    def __init__(self, path="inventory.db"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        create_database(self.path, announce=False)
        with self.connection() as db:
            db.execute("PRAGMA journal_mode=WAL")

    @contextmanager
    def connection(self):
        """Use short-lived connections and roll back any failed multi-write action."""
        db = sqlite3.connect(self.path, timeout=5)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def _integer(value, label):
        if type(value) is not int or not 0 <= value <= MAX_INTEGER:
            raise ValueError(
                f"{label} must be a nonnegative whole number within SQLite's integer range."
            )

    @staticmethod
    def _product(row):
        if row is None:
            return None
        return Product(
            id=row["id"],
            sku=row["sku"],
            name=row["name"],
            category=row["category"],
            quantity=row["quantity"],
            unit_cost_cents=row["unit_costs_cents"],
            reorder_level=row["reorder_level"],
            version=row["version"],
            archived=bool(row["archived"]),
        )

    def _require_active(self, db, product_id):
        product = self._product(
            db.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone()
        )
        if product is None:
            raise ValueError(f"Product with ID '{product_id}' does not exist.")
        if product.archived:
            raise ValueError("Archived products cannot be changed.")
        return product

    @staticmethod
    def _check_sku(db, sku, product_id=None):
        existing = db.execute(
            "SELECT id FROM products WHERE sku=? COLLATE NOCASE", (sku,)
        ).fetchone()
        if existing is not None and existing["id"] != product_id:
            raise ValueError("SKU already exists, including archived products.")

    @staticmethod
    def _record(db, product, delta, balance, reason):
        db.execute(
            "INSERT INTO movements(product_id,sku,name,delta,balance,reason,created_at) VALUES(?,?,?,?,?,?,?)",
            (
                product.id,
                product.sku,
                product.name,
                delta,
                balance,
                reason,
                datetime.now(timezone.utc).isoformat(timespec="microseconds"),
            ),
        )

    def get_product_by_sku(self, sku):
        with self.connection() as db:
            return self._product(
                db.execute(
                    "SELECT * FROM products WHERE sku=? COLLATE NOCASE", (sku,)
                ).fetchone()
            )

    def get_product_by_id(self, product_id):
        with self.connection() as db:
            return self._product(
                db.execute(
                    "SELECT * FROM products WHERE id=?", (product_id,)
                ).fetchone()
            )

    def list_products(self):
        """Include archived rows so existing service methods can apply their filters."""
        with self.connection() as db:
            return [
                self._product(row)
                for row in db.execute("SELECT * FROM products ORDER BY id")
            ]

    def create_product(self, product):
        for label, value in (
            ("Quantity", product.quantity),
            ("Unit cost", product.unit_cost_cents),
            ("Reorder level", product.reorder_level),
        ):
            self._integer(value, label)
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            self._check_sku(db, product.sku)
            cursor = db.execute(
                "INSERT INTO products(sku,name,category,quantity,unit_costs_cents,reorder_level) VALUES(?,?,?,?,?,?)",
                (
                    product.sku,
                    product.name,
                    product.category,
                    product.quantity,
                    product.unit_cost_cents,
                    product.reorder_level,
                ),
            )
            saved = self._require_active(db, cursor.lastrowid)
            if saved.quantity:
                self._record(db, saved, saved.quantity, saved.quantity, "Opening stock")
            return saved

    def update_product(self, product_id, fields, expected_version):
        allowed = {"sku", "name", "category", "unit_cost_cents", "reorder_level"}
        if set(fields) != allowed:
            raise ValueError(
                "Update requires metadata fields only. Use adjust_stock for quantity."
            )
        self._integer(fields["unit_cost_cents"], "Unit cost")
        self._integer(fields["reorder_level"], "Reorder level")
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            product = self._require_active(db, product_id)
            if type(expected_version) is not int or product.version != expected_version:
                raise ValueError(
                    "Product changed since opening. Refresh before editing again."
                )
            self._check_sku(db, fields["sku"], product_id)
            db.execute(
                "UPDATE products SET sku=:sku,name=:name,category=:category,"
                "unit_costs_cents=:unit_cost_cents,reorder_level=:reorder_level,version=version+1 WHERE id=:id",
                {**fields, "id": product_id},
            )
            return self._require_active(db, product_id)

    def adjust_stock(self, product_id, delta, reason):
        """Lock before reading balance; stock and movement must succeed together."""
        if type(delta) is not int or delta == 0:
            raise ValueError("Stock adjustment must be a nonzero whole number.")
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            product = self._require_active(db, product_id)
            balance = product.quantity + delta
            if balance < 0:
                raise ValueError("Stock out exceeds available quantity.")
            self._integer(balance, "Resulting quantity")
            db.execute(
                "UPDATE products SET quantity=?,version=version+1 WHERE id=?",
                (balance, product_id),
            )
            self._record(db, product, delta, balance, reason)
            return self._require_active(db, product_id)

    def archive_product(self, product_id):
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            product = self._require_active(db, product_id)
            if product.quantity != 0:
                raise ValueError("Only zero-stock products can be archived.")
            db.execute(
                "UPDATE products SET archived=1,version=version+1 WHERE id=?",
                (product_id,),
            )
            self._record(db, product, 0, 0, "Product archived")
            return self._product(
                db.execute(
                    "SELECT * FROM products WHERE id=?", (product_id,)
                ).fetchone()
            )

    def list_movements(self, limit=200):
        if type(limit) is not int or not 1 <= limit <= MAX_INTEGER:
            raise ValueError("Movement limit must be a positive whole number.")
        with self.connection() as db:
            rows = db.execute(
                "SELECT * FROM movements ORDER BY id DESC LIMIT ?", (limit,)
            )
            return [
                Movement(
                    id=row["id"],
                    product_id=row["product_id"],
                    sku=row["sku"],
                    name=row["name"],
                    delta=row["delta"],
                    balance=row["balance"],
                    reason=row["reason"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                )
                for row in rows
            ]
