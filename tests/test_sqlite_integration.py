"""Inventory workflows against temporary SQLite files and controlled HTTP quotes."""

import io
import json
import sqlite3
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch
from urllib.error import URLError

from backend.inventory_service import InventoryService
from backend.models import Product
from backend.sqlite_repository import SQLiteInventoryRepository

LEGACY_SCHEMA = """
CREATE TABLE products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sku TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    quantity INTEGER NOT NULL CHECK (quantity >= 0),
    unit_costs_cents INTEGER NOT NULL CHECK (unit_costs_cents >= 0),
    reorder_level INTEGER NOT NULL CHECK (reorder_level >= 0),
    version INTEGER NOT NULL DEFAULT 1,
    archived INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE movements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL,
    sku TEXT NOT NULL,
    name TEXT NOT NULL,
    delta INTEGER NOT NULL,
    balance INTEGER NOT NULL,
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (product_id) REFERENCES products(id)
);
"""


def quote_response(**changes):
    data = {
        "base": "PHP",
        "quote": "USD",
        "rate": 0.02,
        "date": "2026-11-12",
        **changes,
    }
    result = io.BytesIO(json.dumps(data).encode())
    result.status = 200
    return result


class SQLiteInventoryIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.path = Path(self.temporary_directory.name) / "inventory.db"
        self.repository = SQLiteInventoryRepository(self.path)
        self.service = InventoryService(self.repository)

    def create_product(self, **changes):
        values = {
            "sku": "PEN-001",
            "name": "Blue Pen",
            "category": "Supplies",
            "quantity": 5,
            "unit_cost_cents": 125,
            "reorder_level": 2,
            **changes,
        }
        return self.service.create_product(**values)

    def fail_movement_inserts(self):
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute("""
                CREATE TRIGGER reject_movement BEFORE INSERT ON movements
                BEGIN
                    SELECT RAISE(ABORT, 'injected movement failure');
                END
            """)

    def test_reuses_legacy_schema_and_preserves_existing_rows(self):
        legacy_path = Path(self.temporary_directory.name) / "legacy.db"
        with closing(sqlite3.connect(legacy_path)) as connection, connection:
            connection.executescript(LEGACY_SCHEMA)
            connection.execute(
                "INSERT INTO products VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (7, "old-001", "Legacy Notebook", "School", 8, 4999, 3, 4, 0),
            )
            connection.execute(
                "INSERT INTO movements VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    9,
                    7,
                    "old-001",
                    "Original Notebook",
                    -2,
                    8,
                    "Legacy issue",
                    "2026-01-02T03:04:05",
                ),
            )
            original_product = connection.execute("SELECT * FROM products").fetchone()
            original_movement = connection.execute("SELECT * FROM movements").fetchone()

        repository = SQLiteInventoryRepository(legacy_path)
        product = repository.get_product_by_sku("OLD-001")
        self.assertEqual(product.id, 7)
        self.assertEqual(product.quantity, 8)
        self.assertEqual(product.unit_cost_cents, 4999)
        self.assertEqual(product.version, 4)
        movement = repository.list_movements()[0]
        self.assertEqual(
            (movement.id, movement.name, movement.balance), (9, "Original Notebook", 8)
        )
        self.assertEqual(movement.created_at.isoformat(), "2026-01-02T03:04:05")

        InventoryService(repository).create_product(
            "NEW-001", "New Notebook", "School", 0, 2500, 1
        )
        with closing(sqlite3.connect(legacy_path)) as connection, connection:
            self.assertEqual(
                connection.execute("SELECT * FROM products WHERE id = 7").fetchone(),
                original_product,
            )
            self.assertEqual(
                connection.execute("SELECT * FROM movements WHERE id = 9").fetchone(),
                original_movement,
            )

    def test_products_and_movements_survive_reopening_database(self):
        product = self.create_product()
        updated = self.service.adjust_stock(product.id, 3, "Supplier delivery")

        reopened = SQLiteInventoryRepository(self.path)
        self.assertEqual(reopened.get_product_by_id(product.id), updated)
        movements = sorted(reopened.list_movements(), key=lambda movement: movement.id)
        self.assertEqual(
            [(movement.delta, movement.balance) for movement in movements],
            [(5, 5), (3, 8)],
        )
        self.assertTrue(
            all(movement.product_id == product.id for movement in movements)
        )
        self.assertEqual(reopened.get_product_by_sku("pen-001").id, product.id)

    def test_zero_opening_stock_has_no_fictitious_stock_movement(self):
        self.create_product(quantity=0)
        self.assertEqual(self.service.list_movements(), [])

    def test_opening_movement_failure_rolls_back_product_insert(self):
        self.fail_movement_inserts()
        with self.assertRaises((sqlite3.IntegrityError, ValueError)):
            self.create_product()
        self.assertEqual(self.repository.list_products(), [])
        self.assertEqual(self.repository.list_movements(), [])

    def test_stock_failure_rolls_back_quantity_version_and_history(self):
        product = self.create_product()
        original_movements = self.service.list_movements()
        self.fail_movement_inserts()

        with self.assertRaises((sqlite3.IntegrityError, ValueError)):
            self.service.adjust_stock(product.id, 2, "Supplier delivery")

        self.assertEqual(self.repository.get_product_by_id(product.id), product)
        self.assertEqual(self.service.list_movements(), original_movements)

    def test_overdraw_is_rejected_without_changing_product_or_history(self):
        product = self.create_product()
        original_movements = self.service.list_movements()

        with self.assertRaises(ValueError):
            self.service.adjust_stock(product.id, -6, "Issue to classroom")
        # The repository also enforces the invariant when called directly.
        with self.assertRaises(ValueError):
            self.repository.adjust_stock(product.id, -6, "Issue to classroom")

        self.assertEqual(self.repository.get_product_by_id(product.id), product)
        self.assertEqual(self.service.list_movements(), original_movements)

    def test_competing_stock_outs_cannot_oversell_a_stale_service_read(self):
        product = self.create_product()
        barrier = threading.Barrier(2)
        repositories = [SQLiteInventoryRepository(self.path) for _ in range(2)]

        def stock_out(repository):
            service = InventoryService(repository)
            original_read = repository.get_product_by_id
            waited = False

            def synchronized_read(product_id):
                nonlocal waited
                result = original_read(product_id)
                if not waited:
                    waited = True
                    barrier.wait(timeout=5)
                return result

            # Force both service preflight checks to observe the same stock.
            with patch.object(repository, "get_product_by_id", synchronized_read):
                try:
                    service.adjust_stock(product.id, -4, "Concurrent stock issue")
                    return "issued"
                except ValueError:
                    return "rejected"

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(stock_out, repository) for repository in repositories
            ]
            outcomes = [future.result(timeout=15) for future in futures]

        self.assertCountEqual(outcomes, ["issued", "rejected"])
        current = self.repository.get_product_by_id(product.id)
        self.assertEqual((current.quantity, current.version), (1, product.version + 1))
        issues = [
            movement for movement in self.service.list_movements() if movement.delta < 0
        ]
        self.assertEqual(
            [(movement.delta, movement.balance) for movement in issues], [(-4, 1)]
        )

    def test_metadata_edit_rejects_stale_version_and_keeps_movement_snapshots(self):
        product = self.create_product()
        first_movements = self.service.list_movements()
        changes = {
            "product_id": product.id,
            "sku": "PEN-RENAMED",
            "name": "Renamed Pen",
            "category": "Stationery",
            "unit_cost_cents": 200,
            "reorder_level": 3,
            "expected_version": product.version,
        }
        updated = self.service.update_product(**changes)
        self.assertEqual(updated.version, product.version + 1)
        self.assertEqual((updated.quantity, updated.unit_cost_cents), (5, 200))
        self.assertEqual(self.service.list_movements(), first_movements)

        with self.assertRaises(ValueError):
            self.service.update_product(**{**changes, "name": "Stale edit"})
        self.assertEqual(self.repository.get_product_by_id(product.id), updated)

        self.service.adjust_stock(product.id, -1, "Issue after rename")
        movements = sorted(
            self.service.list_movements(), key=lambda movement: movement.id
        )
        self.assertEqual(
            [(movement.sku, movement.name) for movement in movements],
            [("PEN-001", "Blue Pen"), ("PEN-RENAMED", "Renamed Pen")],
        )

    def test_archive_requires_zero_stock_retains_history_and_reserves_sku(self):
        product = self.create_product(quantity=1)
        with self.assertRaises(ValueError):
            self.service.archive_product(product.id)
        self.service.adjust_stock(product.id, -1, "Final stock issue")
        before = self.service.list_movements()
        archived = self.service.archive_product(product.id)

        self.assertTrue(archived.archived)
        self.assertEqual(self.repository.get_product_by_sku("pen-001").id, product.id)
        movements = self.service.list_movements()
        self.assertEqual(len(movements), len(before) + 1)
        archive_events = [
            movement
            for movement in movements
            if movement.id not in {previous.id for previous in before}
        ]
        self.assertEqual(
            [(movement.delta, movement.balance) for movement in archive_events],
            [(0, 0)],
        )
        self.assertTrue(all(previous in movements for previous in before))

        with self.assertRaises(ValueError):
            self.create_product(sku="pen-001")
        # A direct repository call must not bypass case-insensitive reservation.
        with self.assertRaises(ValueError):
            self.repository.create_product(
                Product(None, "pen-001", "Duplicate", "Supplies", 0, 1, 0)
            )
        with self.assertRaises(ValueError):
            self.service.adjust_stock(product.id, 1, "Attempt to reopen")

    def test_archive_movement_failure_rolls_back_archive(self):
        product = self.create_product(quantity=0)
        self.fail_movement_inserts()
        with self.assertRaises((sqlite3.IntegrityError, ValueError)):
            self.service.archive_product(product.id)
        self.assertEqual(self.repository.get_product_by_id(product.id), product)
        self.assertEqual(self.service.list_movements(), [])

    def test_summary_and_search_exclude_archived_rows(self):
        archived = self.create_product(sku="OLD-001", quantity=0)
        self.service.archive_product(archived.id)
        low = self.create_product(quantity=2, unit_cost_cents=125, reorder_level=2)
        self.create_product(
            sku="BOOK-001",
            name="Book",
            quantity=3,
            unit_cost_cents=250,
            reorder_level=1,
        )

        self.assertEqual(
            self.service.get_summary(),
            {
                "total_products": 2,
                "low_stock_products": 1,
                "total_quantity": 5,
                "total_value_cents": 1000,
            },
        )
        self.assertEqual(len(self.repository.list_products()), 3)
        self.assertEqual(
            {product.sku for product in self.service.search_products("")},
            {"PEN-001", "BOOK-001"},
        )
        self.assertEqual(self.service.list_low_stock_products(), [low])

    @patch("backend.exchange_service.urlopen")
    def test_currency_report_uses_persisted_inventory_total_and_real_adapter(
        self, transport
    ):
        self.create_product(quantity=3, unit_cost_cents=12345)
        self.create_product(sku="BOOK-001", quantity=2, unit_cost_cents=678)
        # Reopen so the report cannot depend on service memory.
        service = InventoryService(SQLiteInventoryRepository(self.path))
        transport.return_value = quote_response()
        report = service.get_currency_report(" usd ")

        self.assertEqual(Decimal(str(report["total_php"])), Decimal("383.91"))
        self.assertEqual(Decimal(str(report["converted_total"])), Decimal("7.68"))
        self.assertEqual(Decimal(str(report["rate"])), Decimal("0.02"))
        self.assertEqual(report["currency"], "USD")
        self.assertEqual(report["rate_date"], "2026-11-12")
        self.assertEqual(report["provider"], "Frankfurter")
        self.assertFalse(report["cached"])
        self.assertEqual(
            transport.call_args.args[0].full_url,
            "https://api.frankfurter.dev/v2/rate/php/usd",
        )

    @patch("backend.exchange_service.urlopen")
    def test_currency_failures_do_not_disable_core_inventory(self, transport):
        product = self.create_product()
        original = self.service.get_summary()
        transport.side_effect = URLError("Controlled offline response")
        with self.assertRaises(RuntimeError):
            self.service.get_currency_report("USD")
        self.assertEqual(self.service.get_summary(), original)

        transport.side_effect = None
        transport.return_value = quote_response(rate=-1)
        with self.assertRaises(RuntimeError):
            self.service.get_currency_report("USD")
        with self.assertRaises(ValueError):
            self.service.get_currency_report("unsupported")

        updated = self.service.adjust_stock(product.id, 1, "Delivery while offline")
        self.assertEqual(updated.quantity, 6)
        self.create_product(sku="BOOK-001", quantity=0)
        self.assertEqual(self.service.get_summary()["total_products"], 2)
        self.assertEqual(self.service.search_products("PEN")[0].quantity, 6)


if __name__ == "__main__":
    unittest.main()
