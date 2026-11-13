"""Keep inventory SQL and compatible schema migrations in the repository layer."""

import sqlite3
import tempfile
from contextlib import closing, contextmanager
from datetime import datetime, timezone
from pathlib import Path

from .models import Movement, Product

MAX_INTEGER = 2**63 - 1


def _backup_database(path):
    """Save a unique, consistent SQLite snapshot before changing a legacy schema.

    The initializer holds a reserved write lock. A separate read connection can
    still copy committed data, including WAL pages, without backing up from the
    write transaction itself (which would wait on its own pending transaction).
    """
    with tempfile.NamedTemporaryFile(
        prefix=f"{path.stem}.before-unit-cost-migration-",
        suffix=".db",
        dir=path.parent,
        delete=False,
    ) as backup_file:
        backup_path = Path(backup_file.name)
    source_uri = path.resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(source_uri, uri=True, timeout=5)) as source:
        with closing(sqlite3.connect(backup_path, timeout=5)) as destination:
            source.backup(destination)
    return backup_path


def initialize_database(path):
    """Create the documented schema or migrate the legacy cost-column spelling.

    Return the pre-migration backup path, or None when no migration was needed.
    Migration and table creation share one transaction; product and movement
    values, identifiers, indexes and foreign-key relationships are retained.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    backup_path = None
    with closing(sqlite3.connect(path, timeout=5)) as db:
        db.execute("PRAGMA foreign_keys=ON")
        try:
            # Serialize schema inspection and migration against other writers.
            db.execute("BEGIN IMMEDIATE")
            columns = {row[1] for row in db.execute("PRAGMA table_info(products)")}
            if columns:
                canonical = "unit_cost_cents" in columns
                legacy = "unit_costs_cents" in columns
                if canonical and legacy:
                    raise ValueError(
                        "Products has both unit_cost_cents and unit_costs_cents. "
                        "Resolve the ambiguous unit-cost columns before opening it."
                    )
                if not canonical and not legacy:
                    raise ValueError(
                        "Products is missing the required unit_cost_cents column."
                    )
                if legacy:
                    if sqlite3.sqlite_version_info < (3, 25, 0):
                        raise RuntimeError(
                            "Migrating the unit-cost column requires SQLite 3.25 or newer."
                        )
                    backup_path = _backup_database(path)
                    db.execute(
                        "ALTER TABLE products RENAME COLUMN "
                        "unit_costs_cents TO unit_cost_cents"
                    )
            db.execute("""
                CREATE TABLE IF NOT EXISTS products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sku TEXT UNIQUE NOT NULL,
                    name TEXT NOT NULL,
                    category TEXT NOT NULL,
                    quantity INTEGER NOT NULL CHECK (quantity >= 0),
                    unit_cost_cents INTEGER NOT NULL CHECK (unit_cost_cents >= 0),
                    reorder_level INTEGER NOT NULL CHECK (reorder_level >= 0),
                    version INTEGER NOT NULL DEFAULT 1,
                    archived INTEGER NOT NULL DEFAULT 0
                )
            """)
            db.execute("""
                CREATE TABLE IF NOT EXISTS movements (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_id INTEGER NOT NULL,
                    sku TEXT NOT NULL,
                    name TEXT NOT NULL,
                    delta INTEGER NOT NULL,
                    balance INTEGER NOT NULL,
                    reason TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (product_id) REFERENCES products(id)
                )
            """)
            db.commit()
        except Exception:
            db.rollback()
            raise
    return backup_path


class SQLiteInventoryRepository:
    """Provide the persistence methods expected by the team's InventoryService."""

    def __init__(self, path="inventory.db"):
        self.path = Path(path)
        self.migration_backup = initialize_database(self.path)
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
            unit_cost_cents=row["unit_cost_cents"],
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
                "INSERT INTO products(sku,name,category,quantity,unit_cost_cents,reorder_level) VALUES(?,?,?,?,?,?)",
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
                "unit_cost_cents=:unit_cost_cents,reorder_level=:reorder_level,version=version+1 WHERE id=:id",
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
