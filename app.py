"""Run the team's SQLite inventory summary and external currency report."""

import argparse
import sqlite3
from decimal import Decimal, localcontext
from importlib import import_module
from pathlib import Path

from application_connection import create_application

ROOT = Path(__file__).resolve().parent


def load_menu():
    """Load the operator menu only when explicitly requested."""
    try:
        module = import_module("ui.cli")
    except ModuleNotFoundError as error:
        if error.name in ("ui", "ui.cli"):
            raise RuntimeError(
                "Menu UI is not available yet. Add ui/cli.py with "
                "run_menu(connection). Use --summary or --report meanwhile."
            ) from error
        raise RuntimeError(f"Menu dependency is missing: {error.name}.") from error
    runner = getattr(module, "run_menu", None)
    if not callable(runner):
        raise RuntimeError("ui/cli.py must expose run_menu(connection).")
    return runner


def main(argv=None):
    parser = argparse.ArgumentParser(description="Inventory summary and currency reporting")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--menu", action="store_true", help="Launch the menu UI")
    mode.add_argument("--summary", action="store_true", help="Show offline totals")
    parser.add_argument(
        "--db", type=Path, default=ROOT / "inventory.db", help="SQLite database path"
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Seed fictional stock only if the database file is new",
    )
    mode.add_argument(
        "--report",
        action="store_true",
        help="Fetch a rate and convert the stored inventory total",
    )
    parser.add_argument("--currency", default="USD", help="USD, EUR, SGD, JPY, or GBP")
    args = parser.parse_args(argv)
    try:
        # Resolve the optional UI before creating or migrating any database.
        menu_runner = load_menu() if args.menu else None
        new_database = not args.db.exists()
        connection = create_application(args.db)
        service = connection.service
        if args.demo and new_database:
            # Reproduce the original SQLite branch's demonstration through the
            # actual service/repository contract, including its stock movements.
            item = service.create_product("NB001", "Notebook", "School Supplies", 20, 5000, 5)
            service.adjust_stock(item.id, 10, "Supplier delivery")
            service.adjust_stock(item.id, -5, "Issued to classroom")
            print("Fictional demonstration stock created in the new database.")
        if menu_runner is not None:
            try:
                menu_runner(connection)
            except (EOFError, KeyboardInterrupt):
                print("Menu closed.")
            return 0
        summary = service.get_summary()
        with localcontext() as context:
            context.prec = max(28, len(str(summary["total_value_cents"])) + 8)
            total_php = Decimal(summary["total_value_cents"]) / 100
        print(f"Database: {args.db.resolve()}")
        print(f"Active products: {summary['total_products']}")
        print(f"Units in stock: {summary['total_quantity']}")
        print(f"Inventory value: PHP {total_php:.2f}")
        if args.report:
            report = service.get_currency_report(args.currency)
            print(f"Converted value: {report['currency']} {report['converted_total']}")
            print(f"Exchange rate: 1 PHP = {report['rate']} {report['currency']}")
            print(f"Provider: {report['provider']} | Rate date: {report['rate_date']}")
            print("Quote: " + ("Cached quote" if report["cached"] else "Live request"))
        else:
            print("Add --report --currency USD to retrieve an external exchange quote.")
        return 0
    except (ValueError, RuntimeError, sqlite3.Error, OSError, OverflowError) as error:
        print(f"Error: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
