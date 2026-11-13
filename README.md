# Inventory-Project-for-CS0053
Programming Tools Project

## Run the connected SQLite and currency report

Requires Python 3.11+ and no pip packages. In a terminal opened in this project:

```powershell
python app.py --demo --report --currency USD
```

This command reads real products from SQLite, calculates their total through
`InventoryService.get_summary()`, and requests a reference exchange rate from
Frankfurter. It displays the converted value, rate, provider and observation date.
Internet is required only for a fresh currency quote.

`--demo` creates fictional sample stock only when the database file is new. The
default database is `inventory.db` in this project. Existing database data is kept.
To practice independently, use a separate database:

```powershell
python app.py --demo --db tmp/practice.db --report --currency SGD
```

The demonstration mirrors the team's SQLite example: 20 notebooks, a delivery of
10 and an issue of 5, giving 25 units at PHP 50.00 each (PHP 1,250.00 total).
Actual exchange rates and dates change. No API key or account is needed.

For an offline database summary:

```powershell
python app.py
```

Supported reporting currencies: USD, EUR, SGD, JPY, GBP. Invalid inputs or API
failures produce readable errors; a failed report does not change stored stock.

## How the team code fits together

```text
inventory.py: original SQLite schema
    -> backend/sqlite_repository.py: InventoryRepository implementation
    -> backend/inventory_service.py: summary and currency report
    -> backend/exchange_service.py: real HTTPS request and 15-minute quote cache
    -> app.py: user-triggered terminal report
```

The SQLite adapter retains the original `unit_costs_cents` database column and
maps it to the model's `unit_cost_cents` field. Stock movements are atomic,
metadata edits check versions, and history is retained after zero-stock archive.
Importing the original `inventory.py` no longer runs its sample stock changes.
Running that legacy file explicitly still runs its original example; use `app.py`
for the connected service flow.

Quotes cache for 15 minutes within one process. A new terminal invocation starts
a new process and requests a fresh quote. Repeated service calls reuse the rate
but recalculate against the current database total. Converted reports round to
two decimals for every currency, including JPY as a report convention.

## Test

```powershell
python -m unittest discover -s tests -v
```

Tests use temporary SQLite files and controlled external responses. Actual live
checks are recorded separately in `evidence/`. See
[API integration documentation](docs/API_INTEGRATION.md) for the contract and
integration details. Database files and temporary demonstration stock are ignored
by Git; stop all database writers before copying a database backup.

This local integration combines the team's `backend-structure` and
`python-sqlite-inventory-code` branches on `api-integration`. That branch is
uploaded to GitHub; its pull request into `backend-structure` is still pending.
The current app is command-line based;
there is no web button or browser UI in this team repository yet.
