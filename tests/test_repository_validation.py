"""Public repository calls must enforce shared rules even without a service."""

import tempfile
import unittest
from pathlib import Path
from backend.models import Product, Movement
from backend.inventory_service import InventoryService
from backend.sqlite_repository import SQLiteInventoryRepository


class DirectRepositoryValidationTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.repo = SQLiteInventoryRepository(Path(self.folder.name) / "stock.db")
        self.product = self.repo.create_product(
            Product(None, "BASE-1", "Notebook", "School", 5, 125, 2)
        )

    def test_direct_creation_rejects_invalid_text_without_saving(self):
        for changes in (
            {"name": ""},
            {"name": None},
            {"category": None},
            {"sku": None},
            {"sku": "BAD SKU"},
            {"name": "x" * 101},
            {"category": "x" * 61},
        ):
            fields = dict(
                id=None,
                sku="NEW-1",
                name="Item",
                category="School",
                quantity=1,
                unit_cost_cents=100,
                reorder_level=0,
            )
            fields.update(changes)
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.repo.create_product(Product(**fields))
        self.assertEqual(len(self.repo.list_products()), 1)

    def test_direct_creation_normalizes_values(self):
        product = self.repo.create_product(Product(None, " new-1 ", " Pen ", " School ", 0, 100, 0))
        self.assertEqual((product.sku, product.name, product.category), ("NEW-1", "Pen", "School"))

    def test_invalid_ids_are_rejected_at_storage_boundary(self):
        for value in (None, True, False, 0, -1, 1.5, "1", 2**63):
            for operation in (
                lambda: self.repo.get_product_by_id(value),
                lambda: self.repo.adjust_stock(value, 1, "Delivery"),
                lambda: self.repo.archive_product(value),
            ):
                with self.subTest(value=value), self.assertRaises(ValueError):
                    operation()
        self.assertEqual(self.repo.get_product_by_id(self.product.id).quantity, 5)

    def test_invalid_reasons_and_deltas_do_not_change_balance_or_history(self):
        before = self.repo.list_movements()
        for delta, reason in (
            (0, "Delivery"),
            (1, None),
            (1, "x"),
            (True, "Delivery"),
            (1, "x" * 201),
        ):
            with self.subTest(delta=delta, reason=reason), self.assertRaises(ValueError):
                self.repo.adjust_stock(self.product.id, delta, reason)
        self.assertEqual(self.repo.get_product_by_id(self.product.id).quantity, 5)
        self.assertEqual(self.repo.list_movements(), before)

    def test_metadata_cannot_overwrite_quantity_or_accept_bad_types(self):
        fields = dict(
            sku="BASE-1", name="Notebook", category="School", unit_cost_cents=125, reorder_level=2
        )
        for changed in (
            None,
            [],
            {**fields, "quantity": 0},
            {**fields, "name": None},
            {**fields, "sku": "BAD SKU"},
        ):
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                self.repo.update_product(self.product.id, changed, self.product.version)
        for version in (None, True, 0, 1.0, "1"):
            with self.subTest(version=version), self.assertRaises(ValueError):
                self.repo.update_product(self.product.id, fields, version)

    def test_invalid_history_limits_have_useful_errors(self):
        for value in (None, True, 0, -1, 1.5, "1", 2**63):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.repo.list_movements(value)

    def test_service_direct_calls_also_reject_invalid_inputs(self):
        service = InventoryService(self.repo)
        for operation in (
            lambda: service.search_products(None),
            lambda: service.list_movements(None),
            lambda: service.adjust_stock(True, 1, "Delivery"),
            lambda: service.archive_product(True),
            lambda: service.create_product(None, "Item", "School", 1, 100, 0),
        ):
            with self.assertRaises(ValueError):
                operation()

    def test_new_model_and_persisted_timestamps_are_aware(self):
        movement = Movement(None, 1, "A", "Item", 1, 1, "Delivery")
        self.assertIsNotNone(movement.created_at.tzinfo)
        self.assertIsNotNone(self.repo.list_movements()[0].created_at.tzinfo)
