"""Verify cache semantics and the real command-line report wiring."""

import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import app
from backend.exchange_service import ExchangeService
from backend.inventory_service import InventoryService
from backend.sqlite_repository import SQLiteInventoryRepository

QUOTE = {
    "base": "PHP",
    "quote": "USD",
    "rate": "0.015754",
    "date": "2026-11-12",
    "provider": "Frankfurter",
}


class QuoteCacheTests(unittest.TestCase):
    def test_large_stored_total_keeps_exact_centavo_precision(self):
        with tempfile.TemporaryDirectory() as folder:
            inventory = InventoryService(
                SQLiteInventoryRepository(Path(folder) / "stock.db"),
                exchange_service=ExchangeService(lambda target: dict(QUOTE)),
            )
            quantity, cost = 1234567, 999999999999999999
            inventory.create_product(
                "BIG001", "Large value", "Testing", quantity, cost, 0
            )
            report = inventory.get_currency_report()
            total_cents = quantity * cost
            # Exact integer reference for rate .015754 and half-up rounding.
            expected_cents = (total_cents * 15754 + 500000) // 1000000
            expected = f"{expected_cents // 100}.{expected_cents % 100:02d}"
            self.assertEqual(report["converted_total"], expected)
            self.assertEqual(
                report["total_php"], f"{total_cents // 100}.{total_cents % 100:02d}"
            )

    def test_cached_quote_recalculates_the_current_sqlite_total(self):
        with tempfile.TemporaryDirectory() as folder:
            calls = []

            def fetch(target):
                calls.append(target)
                return dict(QUOTE)

            inventory = InventoryService(
                SQLiteInventoryRepository(Path(folder) / "stock.db"),
                exchange_service=ExchangeService(fetcher=fetch),
            )
            item = inventory.create_product("NB001", "Notebook", "School", 20, 5000, 5)
            first = inventory.get_currency_report()
            inventory.adjust_stock(item.id, 5, "Supplier delivery")
            second = inventory.get_currency_report()
            self.assertFalse(first["cached"])
            self.assertTrue(second["cached"])
            self.assertEqual(first["total_php"], "1000.00")
            self.assertEqual(second["total_php"], "1250.00")
            self.assertEqual(second["converted_total"], "19.69")
            self.assertEqual(calls, ["USD"])

    def test_cache_expires_at_15_minutes_and_keeps_pairs_separate(self):
        now = [0]
        calls = []

        def fetch(target):
            calls.append(target)
            return {**QUOTE, "quote": target}

        exchange = ExchangeService(fetch, lambda: now[0])
        exchange.get_quote(" usd ")
        self.assertTrue(exchange.get_quote("USD")["cached"])
        self.assertFalse(exchange.get_quote("EUR")["cached"])
        now[0] = 900
        self.assertFalse(exchange.get_quote("USD")["cached"])
        self.assertEqual(calls, ["USD", "EUR", "USD"])

    def test_failed_refresh_does_not_return_expired_rate(self):
        now = [0]

        def fetch(target):
            if now[0]:
                raise RuntimeError("Connection unavailable")
            return dict(QUOTE)

        exchange = ExchangeService(fetch, lambda: now[0])
        exchange.get_quote()
        now[0] = 901
        with self.assertRaisesRegex(RuntimeError, "Connection"):
            exchange.get_quote()

    def test_invalid_target_is_rejected_before_fetch(self):
        with patch("backend.exchange_service.fetch_exchange_rate") as fetch:
            exchange = ExchangeService()
            with self.assertRaises(ValueError):
                exchange.get_quote("../../usd")
            fetch.assert_not_called()

    def test_returned_dictionary_cannot_change_cached_quote(self):
        exchange = ExchangeService(lambda target: dict(QUOTE))
        first = exchange.get_quote()
        first["rate"] = "999"
        self.assertEqual(exchange.get_quote()["rate"], QUOTE["rate"])


class CommandLineTests(unittest.TestCase):
    def run_app(self, arguments):
        output = io.StringIO()
        with patch("sys.argv", ["app.py", *arguments]), redirect_stdout(output):
            status = app.main()
        return status, output.getvalue()

    def test_report_uses_real_database_and_demo_does_not_reseed(self):
        with tempfile.TemporaryDirectory() as folder:
            database = Path(folder) / "test.db"
            args = ["--db", str(database), "--demo", "--report", "--currency", "USD"]
            with patch(
                "backend.exchange_service.fetch_exchange_rate", return_value=dict(QUOTE)
            ):
                first_status, first = self.run_app(args)
                second_status, second = self.run_app(args)
            self.assertEqual((first_status, second_status), (0, 0))
            self.assertIn("Units in stock: 25", first)
            self.assertIn("Inventory value: PHP 1250.00", first)
            self.assertIn("Converted value: USD 19.69", first)
            self.assertIn("Quote: Live request", first)
            self.assertIn("Units in stock: 25", second)
            self.assertNotIn("demonstration stock created", second)

    def test_summary_never_requests_external_data(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch("backend.exchange_service.fetch_exchange_rate") as fetch:
                status, output = self.run_app(["--db", str(Path(folder) / "test.db")])
            self.assertEqual(status, 0)
            self.assertIn("Active products: 0", output)
            fetch.assert_not_called()

    def test_report_failure_displays_error_and_does_not_remove_stock(self):
        with tempfile.TemporaryDirectory() as folder:
            database = Path(folder) / "test.db"
            with patch(
                "backend.exchange_service.fetch_exchange_rate",
                side_effect=RuntimeError("Connection unavailable"),
            ):
                status, output = self.run_app(
                    ["--db", str(database), "--demo", "--report"]
                )
            self.assertEqual(status, 1)
            self.assertIn("Error: Connection unavailable", output)
            inventory = InventoryService(SQLiteInventoryRepository(database))
            self.assertEqual(inventory.get_summary()["total_quantity"], 25)


if __name__ == "__main__":
    unittest.main()
