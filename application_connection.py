"""Connect menu actions to the inventory service without owning the menu UI."""

import re
import sqlite3
from dataclasses import dataclass
from decimal import Decimal, localcontext

from backend.inventory_service import InventoryService
from backend.sqlite_repository import MAX_INTEGER, SQLiteInventoryRepository


@dataclass(frozen=True)
class ActionResult:
    """Let the UI display an error and continue its own menu loop."""

    ok: bool
    data: object = None
    error: str | None = None


def whole_number(value, label, minimum=0):
    """Accept terminal integer text without silently truncating fractions."""
    if isinstance(value, str):
        text = value.strip()
        if not re.fullmatch(r"[0-9]{1,19}", text):
            raise ValueError(f"{label} must be a whole number.")
        value = int(text)
    if type(value) is not int or not minimum <= value <= MAX_INTEGER:
        raise ValueError(f"{label} must be a whole number from {minimum} to {MAX_INTEGER}.")
    return value


def php_to_centavos(value):
    """Convert entered decimal PHP text exactly, without binary floats."""
    if not isinstance(value, (str, Decimal)):
        raise ValueError("PHP price must be decimal text, for example 50.25.")
    text = str(value).strip()
    if len(text) > 22 or not re.fullmatch(r"[0-9]+(?:\.[0-9]{1,2})?", text):
        raise ValueError("Enter a nonnegative PHP price with at most two decimals.")
    with localcontext() as context:
        context.prec = max(28, len(text) + 2)
        cents = int(Decimal(text) * 100)
    return whole_number(cents, "Unit cost in centavos")


def text_input(value, label):
    """Reject wrong input types before invoking the team's string validators."""
    if not isinstance(value, str):
        raise ValueError(f"{label} must be text.")
    return value


class ApplicationConnection:
    """Own application wiring; the UI owns prompts, tables, and navigation."""

    def __init__(self, service):
        self.service = service
        self._actions = {
            "view_products": lambda: service.search_products(""),
            "add_product": self._add_product,
            "prepare_edit": self._prepare_edit,
            "edit_product": self._edit_product,
            "stock_in": self._stock_in,
            "stock_out": self._stock_out,
            "search": self._search,
            "low_stock": service.list_low_stock_products,
            "movement_history": self._movement_history,
            "archive": self._archive,
            "summary": service.get_summary,
            "currency_report": self._currency_report,
            "export_csv": service.export_inventory_csv,
        }

    @property
    def action_names(self):
        return tuple(self._actions)

    def execute(self, action, **fields):
        """Dispatch one action and return recoverable input/API/storage errors."""
        if not isinstance(action, str) or action not in self._actions:
            return ActionResult(False, error="Choose a supported menu action.")
        try:
            return ActionResult(True, data=self._actions[action](**fields))
        except (
            ValueError,
            TypeError,
            RuntimeError,
            sqlite3.Error,
            OSError,
            ArithmeticError,
        ) as error:
            return ActionResult(False, error=str(error))

    def _add_product(self, sku, name, category, quantity, price_php, reorder_level):
        return self.service.create_product(
            text_input(sku, "SKU"),
            text_input(name, "Name"),
            text_input(category, "Category"),
            whole_number(quantity, "Quantity"),
            php_to_centavos(price_php),
            whole_number(reorder_level, "Reorder level"),
        )

    def _prepare_edit(self, product_id):
        """Load fields and version before the UI starts asking for edits."""
        product_id = whole_number(product_id, "Product ID", 1)
        product = self.service.repository.get_product_by_id(product_id)
        if product is None:
            raise ValueError(f"Product with ID '{product_id}' does not exist.")
        if product.archived:
            raise ValueError("Archived products cannot be edited.")
        return product

    def _edit_product(
        self,
        product_id,
        sku,
        name,
        category,
        price_php,
        reorder_level,
        expected_version,
    ):
        # Keep the version loaded before prompting; do not replace it at save time.
        return self.service.update_product(
            whole_number(product_id, "Product ID", 1),
            text_input(sku, "SKU"),
            text_input(name, "Name"),
            text_input(category, "Category"),
            php_to_centavos(price_php),
            whole_number(reorder_level, "Reorder level"),
            whole_number(expected_version, "Expected version", 1),
        )

    def _stock_in(self, product_id, quantity, reason):
        return self.service.adjust_stock(
            whole_number(product_id, "Product ID", 1),
            whole_number(quantity, "Stock-in quantity", 1),
            text_input(reason, "Reason"),
        )

    def _stock_out(self, product_id, quantity, reason):
        return self.service.adjust_stock(
            whole_number(product_id, "Product ID", 1),
            -whole_number(quantity, "Stock-out quantity", 1),
            text_input(reason, "Reason"),
        )

    def _search(self, query):
        return self.service.search_products(text_input(query, "Search query"))

    def _movement_history(self, limit=200):
        return self.service.list_movements(whole_number(limit, "Movement limit", 1))

    def _archive(self, product_id, confirmed=False):
        if confirmed is not True:
            raise ValueError("Archiving cancelled: explicit confirmation is required.")
        return self.service.archive_product(whole_number(product_id, "Product ID", 1))

    def _currency_report(self, currency="USD"):
        return self.service.get_currency_report(text_input(currency, "Currency"))


def create_application(db_path):
    """Create one repository and service for the complete menu session."""
    return ApplicationConnection(InventoryService(SQLiteInventoryRepository(db_path)))
