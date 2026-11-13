"""Check that original entry points use the connected inventory implementation."""

import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import inventory
from backend.inventory_service import InventoryService
from backend.sqlite_repository import SQLiteInventoryRepository


class LegacyEntryPointTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.path = Path(self.temporary_directory.name) / "inventory.db"
        self.database_patch = patch.object(inventory, "DB", str(self.path))
        self.database_patch.start()
        self.addCleanup(self.database_patch.stop)

    def test_legacy_keyword_and_helpers_preserve_validated_stock_history(self):
        with redirect_stdout(io.StringIO()) as output:
            inventory.create_database(announce=False)
            product = inventory.addprod(
                "NB001", "Notebook", "School", 20,
                unit_costs_cents=5000, reorder_level=5,
            )
            adjusted = inventory.recmove(product.id, -2, "Damaged items")
            rejected = inventory.recmove(product.id, -99, "Excessive withdrawal")
            shown = inventory.showprod()

        self.assertEqual(adjusted.quantity, 18)
        self.assertIsNone(rejected)
        self.assertEqual(shown[0].quantity, 18)
        self.assertEqual(shown[0].unit_cost_cents, 5000)
        self.assertIn("Error:", output.getvalue())
        service = InventoryService(SQLiteInventoryRepository(self.path))
        self.assertEqual(service.get_summary()["total_quantity"], 18)
        self.assertEqual(
            [(row.delta, row.balance) for row in reversed(service.list_movements())],
            [(20, 20), (-2, 18)],
        )

    def test_repeating_legacy_demo_does_not_reseed_or_repeat_movements(self):
        with redirect_stdout(io.StringIO()):
            self.assertEqual(inventory.main(), 0)
        service = InventoryService(SQLiteInventoryRepository(self.path))
        original_summary = service.get_summary()
        original_history = service.list_movements()

        with redirect_stdout(io.StringIO()) as output:
            self.assertEqual(inventory.main(), 0)

        self.assertEqual(original_summary["total_quantity"], 25)
        self.assertEqual(service.get_summary(), original_summary)
        self.assertEqual(service.list_movements(), original_history)
        self.assertIn("saved stock is unchanged", output.getvalue())


if __name__ == "__main__":
    unittest.main()
