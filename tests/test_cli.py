"""Exercise the real terminal interface against temporary SQLite databases."""

import csv
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from application_connection import create_application
from backend.exchange_service import ExchangeService
from ui.cli import TerminalUI
from ui.formatting import money, table

ROOT = Path(__file__).resolve().parents[1]


class TerminalWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / "stock.db"
        self.connection = create_application(self.path)

    def answers(self, values, connection=None):
        iterator = iter(values)
        output = []
        ui = TerminalUI(
            connection or self.connection,
            input_fn=lambda prompt: next(iterator),
            output_fn=output.append,
        )
        ui.run()
        return "\n".join(output)

    def add(self, quantity=5, name="Notebook"):
        return self.connection.service.create_product("NB001", name, "School", quantity, 125, 3)

    def test_full_operator_workflow_persists_products_movements_and_archive(self):
        output = self.answers(
            [
                "2",
                "NB001",
                "Notebook",
                "School",
                "10",
                "12.50",
                "3",
                "4",
                "1",
                "5",
                "Supplier delivery",
                "5",
                "1",
                "12",
                "Issued to classroom",
                "3",
                "1",
                "",
                "Revised notebook",
                "",
                "20.00",
                "",
                "6",
                "revised",
                "7",
                "8",
                "200",
                "10",
                "5",
                "1",
                "3",
                "Final issue",
                "9",
                "1",
                "YES",
                "1",
                "0",
            ]
        )
        for expected in (
            "Product saved",
            "remaining stock 3",
            "Product updated",
            "Revised notebook",
            "PHP 60.00",
            "Product archived",
            "No matching records",
            "Inventory closed",
        ):
            self.assertIn(expected, output)
        reopened = create_application(self.path)
        self.assertEqual(reopened.execute("view_products").data, [])
        self.assertEqual(len(reopened.execute("movement_history").data), 5)
        self.assertEqual(reopened.service.repository.get_product_by_id(1).quantity, 0)

    def test_invalid_action_and_failed_withdrawal_leave_session_usable(self):
        self.add()
        output = self.answers(["nonsense", "5", "1", "99", "Issued units", "1", "10", "0"])
        self.assertIn("Choose an action from 0 to 12", output)
        self.assertIn("Error:", output)
        self.assertIn("Units in stock: 5", output)
        self.assertEqual(self.connection.service.get_summary()["total_quantity"], 5)
        self.assertEqual(len(self.connection.service.list_movements()), 1)

    def test_cancelled_form_does_not_create_product(self):
        output = self.answers(["2", "NEW-1", ":back", "0"])
        self.assertIn("Action cancelled", output)
        self.assertEqual(self.connection.service.get_summary()["total_products"], 0)

    def test_archive_requires_confirmation_and_zero_stock(self):
        self.add()
        output = self.answers(["9", "1", "NO", "9", "1", "YES", "0"])
        self.assertIn("Archive cancelled", output)
        self.assertIn("zero quantity", output)
        self.assertFalse(self.connection.service.repository.get_product_by_id(1).archived)

    def test_enter_keeps_edit_defaults_and_quantity(self):
        product = self.add()
        output = self.answers(["3", str(product.id), "", "", "", "", "", "0"])
        self.assertIn("Product updated", output)
        current = self.connection.service.repository.get_product_by_id(product.id)
        self.assertEqual(
            (current.sku, current.name, current.quantity, current.unit_cost_cents),
            ("NB001", "Notebook", 5, 125),
        )

    def test_edit_uses_original_version_when_another_action_changes_stock(self):
        product = self.add()
        values = iter(["3", "1", "", "Stale name", "", "", "", "0"])
        output = []
        changed = False

        def respond(prompt):
            nonlocal changed
            if prompt.startswith("SKU") and not changed:
                self.connection.service.adjust_stock(product.id, 1, "Concurrent delivery")
                changed = True
            return next(values)

        TerminalUI(self.connection, input_fn=respond, output_fn=output.append).run()
        self.assertIn("changed since opening", "\n".join(output))
        current = self.connection.service.repository.get_product_by_id(product.id)
        self.assertEqual((current.name, current.quantity), ("Notebook", 6))

    def test_currency_error_does_not_end_menu(self):
        self.add()
        self.connection.service.exchange_service = ExchangeService(
            Mock(side_effect=RuntimeError("Offline test"))
        )
        output = self.answers(["11", "USD", "10", "0"])
        self.assertIn("Error: Offline test", output)
        self.assertIn("Units in stock: 5", output)

    def test_successful_currency_report_labels_cache(self):
        self.add()
        fetch = Mock(
            return_value=dict(
                base="PHP", quote="USD", rate="0.02", date="2026-11-23", provider="Frankfurter"
            )
        )
        self.connection.service.exchange_service = ExchangeService(fetch)
        output = self.answers(["11", "USD", "11", "USD", "0"])
        self.assertIn("Converted value: USD 0.13", output)
        self.assertIn("Live request", output)
        self.assertIn("Cached (under 15 minutes)", output)
        fetch.assert_called_once_with("USD")

    def test_export_writes_a_real_csv_file(self):
        self.add(name="=2+2")
        target = Path(self.folder.name) / "export.csv"
        output = self.answers(["12", str(target), "0"])
        self.assertIn("CSV exported", output)
        with target.open(encoding="utf-8-sig", newline="") as stream:
            rows = list(csv.reader(stream))
        self.assertEqual(rows[1][1], "'=2+2")
        self.assertEqual(rows[1][3], "5")

    def test_export_does_not_overwrite_without_confirmation(self):
        self.add()
        target = Path(self.folder.name) / "keep.csv"
        target.write_text("Keep this file", encoding="utf-8")
        output = self.answers(["12", str(target), "NO", "0"])
        self.assertIn("Export cancelled", output)
        self.assertEqual(target.read_text(), "Keep this file")

    def test_export_permission_error_returns_to_menu(self):
        target = Path(self.folder.name) / "a-directory.csv"
        target.mkdir()
        output = self.answers(["12", str(target), "YES", "10", "0"])
        self.assertIn("Error:", output)
        self.assertIn("Active products: 0", output)

    def test_export_rejects_a_non_csv_destination(self):
        target = Path(self.folder.name) / "keep.py"
        target.write_text("Important source", encoding="utf-8")
        output = self.answers(["12", str(target), "0"])
        self.assertIn("ending in .csv", output)
        self.assertEqual(target.read_text(), "Important source")

    def test_export_cannot_overwrite_database_even_with_csv_extension(self):
        path = Path(self.folder.name) / "inventory.csv"
        self.connection = create_application(path)
        self.add()
        output = self.answers(["12", str(path), "0"])
        self.assertIn("cannot replace the active inventory database", output)
        self.assertEqual(self.connection.service.get_summary()["total_quantity"], 5)

    def test_empty_catalog_and_blank_search_are_usable(self):
        output = self.answers(["1", "6", "", "7", "8", "", "10", "0"])
        self.assertIn("No matching records", output)
        self.assertIn("Current inventory value: PHP 0.00", output)

    def test_menu_starts_from_outside_project_folder(self):
        result = subprocess.run(
            [sys.executable, "-B", str(ROOT / "app.py"), "--menu", "--db", str(self.path)],
            input="0\n",
            capture_output=True,
            text=True,
            cwd=self.folder.name,
            timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("SIMPLE INVENTORY", result.stdout)
        self.assertIn("Inventory closed", result.stdout)

    def test_end_of_input_closes_actual_application_cleanly(self):
        result = subprocess.run(
            [sys.executable, "-B", str(ROOT / "app.py"), "--menu", "--db", str(self.path)],
            input="",
            capture_output=True,
            text=True,
            cwd=self.folder.name,
            timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Menu closed", result.stdout)
        self.assertNotIn("Traceback", result.stderr)

    def test_exact_money_formatting_handles_values_above_float_precision(self):
        self.assertEqual(money(999999999999999999), "PHP 9,999,999,999,999,999.99")

    def test_table_wraps_instead_of_hiding_text(self):
        output = table(["Name"], [["one two three four"]], [7])
        for word in ("one", "two", "three", "four"):
            self.assertIn(word, output)
