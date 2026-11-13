"""Verify documented schemas and safe upgrades of populated legacy databases."""

import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from backend import sqlite_repository
from backend.inventory_service import InventoryService
from backend.sqlite_repository import SQLiteInventoryRepository
from test_sqlite_integration import LEGACY_SCHEMA


class SchemaMigrationTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.path = Path(self.temporary_directory.name) / "inventory.db"

    def create_fixture(self, *, canonical=False):
        cost_column = "unit_cost_cents" if canonical else "unit_costs_cents"
        schema = LEGACY_SCHEMA.replace("unit_costs_cents", cost_column)
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.executescript(schema)
            connection.executemany(
                "INSERT INTO products VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (7, "old-001", "Legacy Notebook", "School", 8, 4999, 3, 4, 0),
                    (8, "old-002", "Archived Pen", "School", 0, 250, 2, 9, 1),
                ],
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
            connection.execute(
                "CREATE TABLE cost_change_audit "
                "(product_id INTEGER, previous_cost INTEGER, new_cost INTEGER)"
            )
            connection.execute(
                f"CREATE INDEX product_cost_lookup ON products({cost_column})"
            )
            connection.execute(
                f"CREATE TRIGGER track_unit_cost_change "
                f"AFTER UPDATE OF {cost_column} ON products "
                "BEGIN INSERT INTO cost_change_audit VALUES "
                f"(OLD.id, OLD.{cost_column}, NEW.{cost_column}); END"
            )

    @staticmethod
    def columns(path, table="products"):
        with closing(sqlite3.connect(path)) as connection:
            return [row[1] for row in connection.execute(f"PRAGMA table_info({table})")]

    @staticmethod
    def database_dump(path):
        with closing(
            sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
        ) as connection:
            return tuple(connection.iterdump())

    def test_new_database_matches_documented_columns_and_relationship(self):
        repository = SQLiteInventoryRepository(self.path)
        self.assertIsNone(repository.migration_backup)
        self.assertEqual(
            self.columns(self.path),
            [
                "id",
                "sku",
                "name",
                "category",
                "quantity",
                "unit_cost_cents",
                "reorder_level",
                "version",
                "archived",
            ],
        )
        self.assertEqual(
            self.columns(self.path, "movements"),
            [
                "id",
                "product_id",
                "sku",
                "name",
                "delta",
                "balance",
                "reason",
                "created_at",
            ],
        )
        with repository.connection() as connection:
            self.assertEqual(connection.execute("PRAGMA foreign_keys").fetchone()[0], 1)
            foreign_keys = connection.execute(
                "PRAGMA foreign_key_list(movements)"
            ).fetchall()
            self.assertEqual(
                [(row[2], row[3], row[4]) for row in foreign_keys],
                [("products", "product_id", "id")],
            )

    def test_canonical_existing_database_is_usable_without_migration(self):
        self.create_fixture(canonical=True)
        original = self.database_dump(self.path)
        repository = SQLiteInventoryRepository(self.path)
        self.assertIsNone(repository.migration_backup)
        self.assertEqual(repository.get_product_by_id(7).unit_cost_cents, 4999)
        self.assertEqual(repository.get_product_by_id(8).archived, True)
        self.assertEqual(self.database_dump(self.path), original)
        self.assertEqual(list(self.path.parent.glob("*.db")), [self.path])

    def test_legacy_upgrade_preserves_records_indexes_triggers_and_backup(self):
        self.create_fixture()
        original = self.database_dump(self.path)
        with closing(sqlite3.connect(self.path)) as connection:
            original_products = connection.execute(
                "SELECT * FROM products ORDER BY id"
            ).fetchall()
            original_movements = connection.execute(
                "SELECT * FROM movements ORDER BY id"
            ).fetchall()

        repository = SQLiteInventoryRepository(self.path)
        backup = Path(repository.migration_backup)
        self.assertNotEqual(backup, self.path)
        self.assertEqual(backup.parent, self.path.parent)
        self.assertEqual(backup.suffix, ".db")
        self.assertEqual(self.database_dump(backup), original)
        self.assertIn("unit_costs_cents", self.columns(backup))
        self.assertIn("unit_cost_cents", self.columns(self.path))
        self.assertNotIn("unit_costs_cents", self.columns(self.path))
        self.assertEqual(repository.get_product_by_id(7).version, 4)
        self.assertTrue(repository.get_product_by_id(8).archived)
        with repository.connection() as connection:
            self.assertEqual(
                [
                    tuple(row)
                    for row in connection.execute("SELECT * FROM products ORDER BY id")
                ],
                original_products,
            )
            self.assertEqual(
                [
                    tuple(row)
                    for row in connection.execute("SELECT * FROM movements ORDER BY id")
                ],
                original_movements,
            )
            self.assertEqual(
                connection.execute("PRAGMA foreign_key_check").fetchall(), []
            )
            index_sql = connection.execute(
                "SELECT sql FROM sqlite_schema WHERE name='product_cost_lookup'"
            ).fetchone()[0]
            self.assertIn("unit_cost_cents", index_sql)
            self.assertNotIn("unit_costs_cents", index_sql)

        service = InventoryService(repository)
        service.update_product(7, "OLD-001", "Updated Notebook", "School", 5500, 3, 4)
        with repository.connection() as connection:
            self.assertEqual(
                tuple(connection.execute("SELECT * FROM cost_change_audit").fetchone()),
                (7, 4999, 5500),
            )
            self.assertEqual(
                [
                    tuple(row)
                    for row in connection.execute("SELECT * FROM movements ORDER BY id")
                ],
                original_movements,
            )
        new_product = service.create_product("NEW-001", "New Pen", "School", 0, 100, 2)
        self.assertGreater(new_product.id, 8)
        self.assertEqual(self.database_dump(backup), original)

    def test_reopening_migrated_database_does_not_repeat_backup_or_migration(self):
        self.create_fixture()
        first = SQLiteInventoryRepository(self.path)
        first_backup = first.migration_backup
        backups_after_migration = set(self.path.parent.glob("*.db"))
        saved = self.database_dump(self.path)
        reopened = SQLiteInventoryRepository(self.path)
        self.assertIsNone(reopened.migration_backup)
        self.assertEqual(self.database_dump(self.path), saved)
        self.assertEqual(set(self.path.parent.glob("*.db")), backups_after_migration)
        self.assertTrue(Path(first_backup).is_file())

    def test_backup_contains_committed_rows_still_in_write_ahead_log(self):
        self.create_fixture()
        with closing(sqlite3.connect(self.path)) as writer:
            self.assertEqual(
                writer.execute("PRAGMA journal_mode=WAL").fetchone()[0], "wal"
            )
            writer.execute("PRAGMA wal_autocheckpoint=0")
            writer.execute("UPDATE products SET quantity=11, version=5 WHERE id=7")
            writer.commit()
            self.assertTrue(Path(str(self.path) + "-wal").is_file())
            repository = SQLiteInventoryRepository(self.path)
            with closing(sqlite3.connect(repository.migration_backup)) as backup:
                self.assertEqual(
                    backup.execute(
                        "SELECT quantity, version FROM products WHERE id=7"
                    ).fetchone(),
                    (11, 5),
                )
                self.assertEqual(
                    backup.execute("PRAGMA integrity_check").fetchone()[0], "ok"
                )
                self.assertIn(
                    "unit_costs_cents",
                    [row[1] for row in backup.execute("PRAGMA table_info(products)")],
                )
            self.assertEqual(repository.get_product_by_id(7).quantity, 11)

    def test_backup_failure_leaves_legacy_schema_and_records_unchanged(self):
        self.create_fixture()
        original = self.database_dump(self.path)
        with patch.object(
            sqlite_repository,
            "_backup_database",
            side_effect=OSError("Controlled backup failure"),
        ), self.assertRaisesRegex(OSError, "backup failure"):
            SQLiteInventoryRepository(self.path)
        self.assertEqual(self.database_dump(self.path), original)
        self.assertEqual(list(self.path.parent.glob("*.db")), [self.path])

    def test_failed_rename_rolls_back_schema_and_keeps_recovery_backup(self):
        self.create_fixture()
        with closing(sqlite3.connect(self.path)) as connection, connection:
            # A pre-existing invalid view prevents SQLite from rewriting schema.
            connection.execute(
                "CREATE VIEW broken_cost_report AS "
                "SELECT missing_cost FROM products"
            )
        original = self.database_dump(self.path)
        with self.assertRaises(sqlite3.OperationalError):
            sqlite_repository.initialize_database(self.path)
        self.assertEqual(self.database_dump(self.path), original)
        backups = [path for path in self.path.parent.glob("*.db") if path != self.path]
        self.assertEqual(len(backups), 1)
        self.assertEqual(self.database_dump(backups[0]), original)

    def test_ambiguous_or_missing_cost_column_fails_without_modifying_database(self):
        definitions = (
            "unit_cost_cents INTEGER, unit_costs_cents INTEGER",
            "unexpected_cost INTEGER",
        )
        for index, definition in enumerate(definitions):
            with self.subTest(definition=definition):
                path = self.path.parent / f"malformed-{index}.db"
                with closing(sqlite3.connect(path)) as connection, connection:
                    connection.execute(
                        f"CREATE TABLE products (id INTEGER PRIMARY KEY, {definition})"
                    )
                    connection.execute("INSERT INTO products (id) VALUES (7)")
                original = self.database_dump(path)
                with self.assertRaisesRegex(ValueError, "cost"):
                    sqlite_repository.initialize_database(path)
                self.assertEqual(self.database_dump(path), original)

    def test_documented_notebook_example_records_each_balance_and_final_quantity(self):
        service = InventoryService(SQLiteInventoryRepository(self.path))
        product = service.create_product(
            "NB001", "Notebook", "School Supplies", 20, 5000, 5
        )
        adjustments = (
            (10, "Supplier delivery"),
            (-5, "Issued to classroom"),
            (-2, "Damaged items"),
        )
        for delta, reason in adjustments:
            product = service.adjust_stock(product.id, delta, reason)
        self.assertEqual(product.quantity, 23)
        history = sorted(service.list_movements(), key=lambda movement: movement.id)
        self.assertEqual(
            [(movement.delta, movement.balance) for movement in history],
            [(20, 20), (10, 30), (-5, 25), (-2, 23)],
        )
        self.assertTrue(all(movement.product_id == product.id for movement in history))
        reopened = InventoryService(SQLiteInventoryRepository(self.path))
        self.assertEqual(reopened.get_summary()["total_quantity"], 23)


if __name__ == "__main__":
    unittest.main()
