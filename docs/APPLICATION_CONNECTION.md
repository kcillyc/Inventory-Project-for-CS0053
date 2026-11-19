# Application connection

Responsible member: John Rich Bernaldez

This implements the Application connection assignment: create the repository
and service, expose the listed menu actions, and preserve the existing summary
and currency report commands. Prompts, displayed tables, confirmation dialogs,
and navigation remain in Kate's UI. Database SQL remains in the repository.

## Current integration status

The application connection and menu entry hook are implemented and tested.
Kate's `ui/cli.py` is not present in the checked GitHub branches. The hook below
defines the integration contract for that pending UI; it has been tested with a
test-only menu stand-in. A complete interactive session still needs Kate's
actual menu and a final integration check against its entry point.

The current connection uses the existing tested `SQLiteInventoryRepository`
and `InventoryService`. Teng's newly uploaded `invdb_repository.py` remains on
his branch; it has not been copied, edited, or merged. Selecting that repository
later requires aligning its imports and behavior with `InventoryRepository`
and rerunning storage and application tests.

## Run commands

The original commands keep their behavior:

```powershell
python app.py
python app.py --summary
python app.py --demo --report --currency USD
```

When the UI is available, launch it with:

```powershell
python app.py --menu
```

All modes accept `--db PATH`. The menu, summary, and report modes are mutually
exclusive. Demo data is seeded only into a new database when `--demo` is used.
Requesting a missing UI produces a clear message before database initialization;
it does not silently substitute a different menu.

## Menu entry contract

The menu module should expose `ui.cli.run_menu(connection)`. `app.py` creates
one repository, one service, and one `ApplicationConnection`, then passes the
connection to this function for the whole session. The connection offers:

```python
result = connection.execute("summary")
# result.ok: True on success
# result.data: the service result (product, list, summary, or currency report)
# result.error: a message on failure
```

The UI displays `result.error` when `result.ok` is false and continues its menu
loop. It displays `result.data` on success. Errors are returned as data so an
invalid input or failed API request does not terminate the session. The UI owns
the actual messages, prompts, tables, and choice of navigation.

| Action | Input fields | Service operation |
| --- | --- | --- |
| `view_products` | None | `search_products("")` |
| `add_product` | `sku`, `name`, `category`, `quantity`, `price_php`, `reorder_level` | `create_product(...)` |
| `prepare_edit` | `product_id` | Load the current product and version from the repository |
| `edit_product` | `product_id`, `sku`, `name`, `category`, `price_php`, `reorder_level`, `expected_version` | `update_product(...)` |
| `stock_in` | `product_id`, positive `quantity`, `reason` | `adjust_stock(id, positive_quantity, reason)` |
| `stock_out` | `product_id`, positive `quantity`, `reason` | `adjust_stock(id, -quantity, reason)` |
| `search` | `query` | `search_products(query)` |
| `low_stock` | None | `list_low_stock_products()` |
| `movement_history` | Optional positive `limit` (default 200) | `list_movements(limit)` |
| `archive` | `product_id`, `confirmed=True` after confirmation | `archive_product(id)` |
| `summary` | None | `get_summary()` |
| `currency_report` | Optional `currency` (default USD) | `get_currency_report(currency)` |

`connection.action_names` lists the available actions. Currency requests occur
only through `currency_report` or the existing `--report` command. Ordinary
product, stock, history, and summary actions do not request exchange rates.

## Input and editing flow

Ask for every input listed above. PHP prices are entered as decimal text such
as `50` or `50.25`, without commas or a currency symbol, with at most two decimal
places. The connection converts them exactly to integer centavos (`50.25`
becomes `5025`). Negative prices, fractions of a centavo, binary floats, and
amounts outside SQLite's integer range are rejected. Integer fields accept
whole-number text; IDs, stock-in/out amounts, versions, and limits must be
positive. Opening quantity and reorder level may be zero.

Before prompting for edits, call `prepare_edit` and retain its returned product.
Show its current fields, collect the edits, then pass that product's `version`
as `expected_version` to `edit_product`. Do not reload and replace the version
when saving: an intervening stock or metadata change must cause a conflict
message instead of overwriting someone else's changes.

Before calling `archive`, ask the user for confirmation and pass the Boolean
`True` only after they agree. Strings such as `"yes"` do not count as confirmation
at the connection boundary. The service still rejects archiving stocked items.

## Verification

```powershell
python -m unittest discover -s tests -v
```

`tests/test_application_connection.py` checks action-to-service wiring against
temporary SQLite files, exact price conversion, stale-edit detection, required
confirmation, persistence, API isolation, recovery after errors, legacy summary
behavior, and the pending UI hook. Its menu stand-in is a fixture, not a
completed implementation of Kate's UI. Existing database and API regression
tests remain part of the suite.
