"""Complete operator workflows using the existing ApplicationConnection contract."""

from datetime import datetime, timezone
from pathlib import Path

from .formatting import decimal_amount, decimal_text, money, status, table, timestamp


class CancelAction(Exception):
    """The operator explicitly returned from a form without saving."""


class TerminalUI:
    """Own prompts and display; all inventory rules remain in the backend."""

    def __init__(self, connection, input_fn=None, output_fn=None):
        self.connection = connection
        self.input = input_fn if input_fn is not None else input
        self.output = output_fn if output_fn is not None else print
        self.actions = {
            "1": self.view_products,
            "2": self.add_product,
            "3": self.edit_product,
            "4": lambda: self.adjust_stock(True),
            "5": lambda: self.adjust_stock(False),
            "6": self.search_products,
            "7": self.low_stock,
            "8": self.history,
            "9": self.archive_product,
            "10": self.summary,
            "11": self.currency_report,
            "12": self.export_csv,
        }

    def ask(self, prompt, default=None):
        suffix = f" [{default}]" if default is not None else ""
        value = self.input(prompt + suffix + ": ")
        if value.strip().casefold() == ":back":
            raise CancelAction
        return str(default) if not value.strip() and default is not None else value

    def perform(self, action, **fields):
        result = self.connection.execute(action, **fields)
        if not result.ok:
            self.output("Error: " + result.error)
            return None
        return result.data

    def show_products(self, products):
        self.output(
            table(
                ["ID", "SKU", "Product", "Category", "Qty", "Unit cost", "Reorder", "Status"],
                [
                    [
                        p.id,
                        p.sku,
                        p.name,
                        p.category,
                        p.quantity,
                        money(p.unit_cost_cents),
                        p.reorder_level,
                        status(p),
                    ]
                    for p in products
                ],
                [6, 16, 25, 17, 12, 25, 12, 12],
                numeric=(0, 4, 5, 6),
            )
        )

    def view_products(self):
        records = self.perform("view_products")
        if records is not None:
            self.output("ACTIVE PRODUCTS")
            self.show_products(records)

    def add_product(self):
        self.output("ADD PRODUCT - enter :back to cancel")
        fields = {
            "sku": self.ask("SKU"),
            "name": self.ask("Product name"),
            "category": self.ask("Category"),
            "quantity": self.ask("Opening quantity", "0"),
            "price_php": self.ask("Unit cost in PHP", "0.00"),
            "reorder_level": self.ask("Reorder level", "0"),
        }
        product = self.perform("add_product", **fields)
        if product is not None:
            self.output(f"Product saved: ID {product.id}, {product.sku}.")

    def edit_product(self):
        product = self.perform("prepare_edit", product_id=self.ask("Product ID to edit"))
        if product is None:
            return
        self.output(
            "EDIT PRODUCT - Enter keeps a value; :back cancels. Quantity uses stock in/out."
        )
        fields = {
            "product_id": product.id,
            "expected_version": product.version,
            "sku": self.ask("SKU", product.sku),
            "name": self.ask("Product name", product.name),
            "category": self.ask("Category", product.category),
            "price_php": self.ask("Unit cost in PHP", decimal_text(product.unit_cost_cents)),
            "reorder_level": self.ask("Reorder level", product.reorder_level),
        }
        updated = self.perform("edit_product", **fields)
        if updated is not None:
            self.output(f"Product updated: {updated.sku}. Quantity remains {updated.quantity}.")

    def adjust_stock(self, incoming):
        self.output("STOCK IN" if incoming else "STOCK OUT")
        product_id = self.ask("Product ID")
        quantity = self.ask("Quantity (positive whole number)")
        reason = self.ask("Reason (3 to 200 characters)")
        product = self.perform(
            "stock_in" if incoming else "stock_out",
            product_id=product_id,
            quantity=quantity,
            reason=reason,
        )
        if product is not None:
            self.output(f"Movement recorded: {product.sku}; remaining stock {product.quantity}.")

    def search_products(self):
        records = self.perform("search", query=self.ask("Search name, SKU, or category", ""))
        if records is not None:
            self.show_products(records)

    def low_stock(self):
        records = self.perform("low_stock")
        if records is not None:
            self.output("AT OR BELOW REORDER LEVEL")
            self.show_products(records)

    def history(self):
        movements = self.perform(
            "movement_history", limit=self.ask("Latest movements to show", "200")
        )
        if movements is not None:
            self.output(
                table(
                    ["ID", "Date and time", "SKU", "Change", "Balance", "Reason"],
                    [
                        [m.id, timestamp(m.created_at), m.sku, f"{m.delta:+d}", m.balance, m.reason]
                        for m in movements
                    ],
                    [7, 25, 16, 18, 18, 36],
                    numeric=(0, 3, 4),
                )
            )
            self.output(
                "New timestamps use UTC. A local* label identifies a preserved legacy timestamp."
            )

    def archive_product(self):
        product = self.perform("prepare_edit", product_id=self.ask("Product ID to archive"))
        if product is None:
            return
        if (
            self.ask(f"Archive {product.name} ({product.sku})? Type YES to confirm").strip().upper()
            != "YES"
        ):
            self.output("Archive cancelled.")
            return
        archived = self.perform("archive", product_id=product.id, confirmed=True)
        if archived is not None:
            self.output(f"Product archived: {archived.sku}. Movement history retained.")

    def summary(self):
        summary = self.perform("summary")
        if summary is not None:
            self.output("INVENTORY SUMMARY")
            self.output(f"Active products: {summary['total_products']}")
            self.output(f"Units in stock: {summary['total_quantity']}")
            self.output(f"At or below reorder level: {summary['low_stock_products']}")
            self.output(f"Current inventory value: {money(summary['total_value_cents'])}")

    def currency_report(self):
        report = self.perform(
            "currency_report", currency=self.ask("Currency: USD EUR SGD JPY GBP", "USD")
        )
        if report is not None:
            self.output("CURRENCY REPORT")
            self.output(f"Inventory value: PHP {decimal_amount(report['total_php'])}")
            self.output(
                f"Converted value: {report['currency']} {decimal_amount(report['converted_total'])}"
            )
            self.output(f"Exchange rate: 1 PHP = {report['rate']} {report['currency']}")
            self.output(f"Provider: {report['provider']} | Rate date: {report['rate_date']}")
            self.output(
                "Quote: " + ("Cached (under 15 minutes)" if report["cached"] else "Live request")
            )

    def export_csv(self):
        content = self.perform("export_csv")
        if content is None:
            return
        default = (
            "reports/inventory-" + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f") + ".csv"
        )
        path = Path(self.ask("CSV output path", default)).expanduser()
        if path.suffix.casefold() != ".csv":
            raise ValueError("Choose a filename ending in .csv.")
        database = self.connection.service.repository.path.resolve()
        if path.resolve() == database:
            raise ValueError("The export cannot replace the active inventory database.")
        exists = path.exists()
        if exists and self.ask("File exists. Type YES to replace it").strip().upper() != "YES":
            self.output("Export cancelled.")
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w" if exists else "x", encoding="utf-8-sig", newline="") as stream:
            stream.write(content)
        self.output(f"CSV exported: {path.resolve()}")

    def run(self):
        while True:
            self.output("\nSIMPLE INVENTORY 1.0.0 - local single-user application")
            self.output("1 View products       2 Add product        3 Edit product")
            self.output("4 Stock in            5 Stock out          6 Search")
            self.output("7 Low stock           8 Movement history   9 Archive")
            self.output("10 Summary            11 Currency report   12 Export CSV")
            self.output("0 Exit                :back cancels the current form")
            try:
                choice = self.ask("Choose an action").strip()
                if choice == "0":
                    self.output("Inventory closed. Saved records remain in the database.")
                    return
                action = self.actions.get(choice)
                if action is None:
                    self.output("Choose an action from 0 to 12.")
                else:
                    action()
            except CancelAction:
                self.output("Action cancelled.")
            except (OSError, ValueError) as error:
                self.output(f"Error: {error}")


def run_menu(connection):
    """Entry point expected by app.py and the existing application tests."""
    TerminalUI(connection).run()
