"""Exercise John Rich Bernaldez's wiring independently of the pending menu UI."""

import io
import tempfile
import unittest
from contextlib import redirect_stdout
from decimal import Decimal, localcontext
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import app
from application_connection import (
    ApplicationConnection, create_application, php_to_centavos,
)
from backend.exchange_service import ExchangeService

QUOTE = {
    "base": "PHP", "quote": "USD", "rate": "0.02",
    "date": "2026-11-19", "provider": "Frankfurter",
}


class ApplicationConnectionTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / "application.db"
        self.connection = create_application(self.path)

    def add_product(self, **changes):
        fields = dict(
            sku="NB001", name="Notebook", category="School Supplies",
            quantity="20", price_php="50.25", reorder_level="5",
        )
        result = self.connection.execute("add_product", **{**fields, **changes})
        self.assertTrue(result.ok, result.error)
        return result.data

    def test_all_document_actions_share_real_sqlite_service_without_implicit_api(self):
        with patch("backend.exchange_service.fetch_exchange_rate") as fetch:
            product = self.add_product()
            self.assertEqual(product.unit_cost_cents, 5025)
            self.assertEqual(self.connection.execute("view_products").data, [product])
            self.assertEqual(
                self.connection.execute("search", query="notebook").data, [product]
            )
            self.assertEqual(self.connection.execute("low_stock").data, [])
            incoming = self.connection.execute(
                "stock_in", product_id=str(product.id), quantity="10",
                reason="Supplier delivery",
            )
            self.assertEqual(incoming.data.quantity, 30)
            outgoing = self.connection.execute(
                "stock_out", product_id=product.id, quantity="5",
                reason="Issued to classroom",
            )
            self.assertEqual(outgoing.data.quantity, 25)
            current = self.connection.execute("prepare_edit", product_id=product.id)
            edited = self.connection.execute(
                "edit_product", product_id=product.id, sku="NB001",
                name="Updated Notebook", category="Stationery", price_php="60.29",
                reorder_level="30", expected_version=current.data.version,
            )
            self.assertTrue(edited.ok, edited.error)
            self.assertEqual(edited.data.unit_cost_cents, 6029)
            self.assertEqual(self.connection.execute("low_stock").data, [edited.data])
            movements = self.connection.execute("movement_history", limit="10")
            self.assertEqual(
                [(row.delta, row.balance) for row in reversed(movements.data)],
                [(20, 20), (10, 30), (-5, 25)],
            )
            summary = self.connection.execute("summary")
            self.assertEqual(summary.data["total_value_cents"], 150725)
            self.assertFalse(self.connection.execute(
                "archive", product_id=product.id, confirmed=True
            ).ok)
            self.connection.execute(
                "stock_out", product_id=product.id, quantity=25,
                reason="Final stock issue",
            )
            self.assertFalse(self.connection.execute(
                "archive", product_id=product.id, confirmed=False
            ).ok)
            archived = self.connection.execute(
                "archive", product_id=product.id, confirmed=True
            )
            self.assertTrue(archived.ok, archived.error)
            self.assertTrue(archived.data.archived)
            self.assertEqual(self.connection.execute("view_products").data, [])
            fetch.assert_not_called()
        reopened = create_application(self.path)
        self.assertEqual(reopened.execute("summary").data["total_products"], 0)
        self.assertEqual(len(reopened.execute("movement_history").data), 5)

    def test_edit_keeps_version_loaded_before_other_stock_changes(self):
        product = self.add_product()
        snapshot = self.connection.execute("prepare_edit", product_id=product.id).data
        self.connection.execute(
            "stock_in", product_id=product.id, quantity=1, reason="New delivery"
        )
        stale = self.connection.execute(
            "edit_product", product_id=product.id, sku="NB001", name="Stale name",
            category="School", price_php="1.00", reorder_level=5,
            expected_version=snapshot.version,
        )
        self.assertFalse(stale.ok)
        self.assertIn("changed", stale.error)
        saved = self.connection.execute("prepare_edit", product_id=product.id).data
        self.assertEqual((saved.name, saved.quantity), ("Notebook", 21))

    def test_api_failure_returns_error_then_inventory_actions_continue(self):
        self.add_product()
        with patch("backend.exchange_service.fetch_exchange_rate") as fetch:
            fetch.side_effect = RuntimeError("Cannot connect to the exchange service.")
            self.connection.service.exchange_service = ExchangeService()
            connection = ApplicationConnection(self.connection.service)
            failed = connection.execute("currency_report", currency="USD")
            self.assertFalse(failed.ok)
            self.assertIn("Cannot connect", failed.error)
            self.assertTrue(connection.execute("summary").ok)
            self.assertEqual(connection.execute("view_products").data[0].quantity, 20)
            self.assertEqual(fetch.call_count, 1)

    def test_only_explicit_currency_action_requests_rate_and_reuses_cache(self):
        self.add_product()
        with patch("backend.exchange_service.fetch_exchange_rate", return_value=QUOTE) as fetch:
            self.connection.service.exchange_service = ExchangeService()
            first = self.connection.execute("currency_report", currency="USD")
            second = self.connection.execute("currency_report", currency="USD")
            self.assertTrue(first.ok, first.error)
            self.assertEqual(first.data["converted_total"], "20.10")
            self.assertFalse(first.data["cached"])
            self.assertTrue(second.data["cached"])
            fetch.assert_called_once_with("USD")

    def test_input_errors_do_not_change_saved_records_or_end_session(self):
        product = self.add_product()
        before = self.connection.execute("movement_history").data
        attempts = [
            ("stock_in", dict(product_id=product.id, quantity="-5", reason="Delivery")),
            ("stock_out", dict(product_id=product.id, quantity="0", reason="Issue")),
            ("stock_out", dict(product_id=product.id, quantity="99", reason="Issue")),
            ("stock_out", dict(product_id=product.id, quantity=True, reason="Issue")),
            ("stock_in", dict(product_id="bad", quantity="1", reason="Delivery")),
            ("prepare_edit", dict(product_id="999")),
            ("movement_history", dict(limit="1.5")),
            ("archive", dict(product_id=product.id, confirmed="yes")),
            ("search", dict(query=None)),
            ("add_product", {}),
            ("missing", {}),
            ([], {}),
        ]
        for action, fields in attempts:
            with self.subTest(action=action, fields=fields):
                result = self.connection.execute(action, **fields)
                self.assertFalse(result.ok)
                self.assertTrue(result.error)
                self.assertTrue(self.connection.execute("summary").ok)
        self.assertEqual(self.connection.execute("movement_history").data, before)
        self.assertEqual(self.connection.execute("view_products").data, [product])


class PriceConversionTests(unittest.TestCase):
    def test_centavos_are_exact_even_with_small_decimal_context(self):
        with localcontext() as context:
            context.prec = 2
            for value, expected in (
                ("0.29", 29), ("50", 5000), (" 50.25 ", 5025),
                (Decimal("1.01"), 101),
                ("92233720368547758.07", 9223372036854775807),
            ):
                self.assertEqual(php_to_centavos(value), expected)

    def test_invalid_or_out_of_range_prices_are_rejected(self):
        for value in (
            "", "-1", "0.001", "1,000.00", "NaN", "Infinity", "1e3",
            "92233720368547758.08", 0.29, True, None,
        ):
            with self.subTest(value=value), self.assertRaises(ValueError):
                php_to_centavos(value)


class MenuConnectionTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / "menu.db"

    def run_app(self, *arguments):
        with redirect_stdout(io.StringIO()) as output:
            code = app.main(["--db", str(self.path), *arguments])
        return code, output.getvalue()

    def test_menu_receives_connected_application_and_returns_cleanly(self):
        seen = []

        def fixture_menu(connection):
            # A test-only UI stand-in verifies the hook; no production UI is added.
            seen.append(connection)
            added = connection.execute(
                "add_product", sku="PEN01", name="Pen", category="School",
                quantity="3", price_php="1.29", reorder_level="1",
            )
            self.assertTrue(added.ok, added.error)
            self.assertFalse(connection.execute("stock_in").ok)
            self.assertTrue(connection.execute("summary").ok)

        with (
            patch("app.import_module", return_value=SimpleNamespace(run_menu=fixture_menu)),
            patch("backend.exchange_service.fetch_exchange_rate") as fetch,
        ):
            code, output = self.run_app("--menu")
            self.assertEqual(code, 0, output)
            self.assertEqual(len(seen), 1)
            fetch.assert_not_called()
        self.assertEqual(
            create_application(self.path).execute("summary").data["total_value_cents"],
            387,
        )

    def test_missing_menu_reports_dependency_without_creating_database(self):
        missing = ModuleNotFoundError("No module named 'ui'", name="ui")
        with patch("app.import_module", side_effect=missing):
            code, output = self.run_app("--menu")
        self.assertEqual(code, 1)
        self.assertIn("run_menu(connection)", output)
        self.assertFalse(self.path.exists())

    def test_invalid_menu_entry_point_and_nested_dependency_report_clear_errors(self):
        for module in (SimpleNamespace(), SimpleNamespace(run_menu="not callable")):
            with patch("app.import_module", return_value=module):
                code, output = self.run_app("--menu")
                self.assertEqual(code, 1)
                self.assertIn("must expose", output)
        missing = ModuleNotFoundError("No module named 'menu_dependency'", name="menu_dependency")
        with patch("app.import_module", side_effect=missing):
            code, output = self.run_app("--menu")
        self.assertEqual(code, 1)
        self.assertIn("menu_dependency", output)
        self.assertFalse(self.path.exists())

    def test_eof_and_keyboard_interrupt_close_menu_without_traceback(self):
        for error in (EOFError(), KeyboardInterrupt()):
            def fixture_menu(connection):
                raise error

            with patch("app.import_module", return_value=SimpleNamespace(run_menu=fixture_menu)):
                code, output = self.run_app("--menu")
            self.assertEqual(code, 0)
            self.assertIn("Menu closed", output)

    def test_existing_summary_mode_works_without_importing_ui_or_calling_api(self):
        with (
            patch("app.import_module") as ui,
            patch("backend.exchange_service.fetch_exchange_rate") as fetch,
        ):
            code, output = self.run_app("--summary", "--demo")
        self.assertEqual(code, 0, output)
        self.assertIn("Units in stock: 25", output)
        ui.assert_not_called()
        fetch.assert_not_called()

    def test_menu_and_report_modes_are_mutually_exclusive(self):
        with (
            redirect_stdout(io.StringIO()),
            patch("sys.stderr", new_callable=io.StringIO),
            self.assertRaises(SystemExit) as result,
        ):
            app.main(["--menu", "--report"])
        self.assertEqual(result.exception.code, 2)
        self.assertFalse(self.path.exists())


if __name__ == "__main__":
    unittest.main()
