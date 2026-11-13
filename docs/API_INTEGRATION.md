# Connected SQLite inventory and currency API

## Purpose and team code

This integration combines the GitHub `backend-structure` and
`python-sqlite-inventory-code` branches on `api-integration`
branch. The SQLite branch was merged locally with its original author history.
The additional adapter, report method, cache, terminal entry point and tests are
published on that GitHub branch. A pull request and team review are still pending;
later local verification or fixes must be committed and pushed separately.

The application reads actual SQLite products and calculates their current PHP
value through the team's `InventoryService.get_summary()`. It then requests an
external exchange rate, multiplies locally using Decimal and displays a report.
This is a command-line application; adding a web interface is separate work.

## Run

From the team project folder:

```powershell
python app.py --demo --report --currency USD
```

`--report` is the explicit user action that requests an external quote. The
default database is `inventory.db` in the project. `--demo` reproduces the
original branch's fictional 20 notebooks, +10 delivery and -5 issue, only when
the database file does not exist. Existing databases are never reseeded.

For a separate practice database:

```powershell
python app.py --demo --db tmp/practice.db --report --currency SGD
```

For offline inventory totals, omit `--report`. To check the API independently,
run `python backend/exchange_service.py --target USD`. Python 3.11+ and its
standard library are sufficient; internet is needed only for fresh quotes.

## Data flow

```text
app.py --report --currency USD
  -> SQLiteInventoryRepository reuses inventory.py's original schema
  -> InventoryService.get_summary() reads stored active products
  -> total_value_cents / 100 becomes the total PHP amount
  -> ExchangeService.get_quote("USD") fetches or reuses a successful quote
  -> InventoryService.get_currency_report() converts using Decimal
  -> app.py displays amount, currency, rate, observation date and provider
```

`get_currency_report()` returns `total_php`, `converted_total`, `currency`,
`rate`, `rate_date`, `provider` and `cached`. Amounts and rates are decimal
strings. Reports round half up to two decimals for every supported currency,
including JPY as a reporting convention. Conversion precision scales with the
stored total rather than relying on binary floating-point values.

## Database compatibility and transaction behavior

The original schema names its monetary column `unit_costs_cents` (plural). The
adapter maps it to the team's `Product.unit_cost_cents` without renaming columns
or deleting data. It implements every method in `InventoryRepository`. Product
listing includes archived rows, which the existing service filters from active
summaries/searches.

New positive opening balances create Opening stock movements. Stock updates
lock with BEGIN IMMEDIATE before reading the current balance. Balance/version
and movement writes commit together or roll back together. Metadata edits check
the expected version and preserve old movement labels. Only zero-stock items
can be archived; history remains and their SKUs stay reserved case-insensitively.

`inventory.py` retains the original example when run directly, but importing it
now only defines its functions. The connected app uses the service/repository
flow rather than invoking that example. Existing legacy timestamps/records are
retained; new movements use UTC. This initial integration does not add a schema
migration framework, web interface, accounts, or historical cost layers.

## External request contract

- Provider/documentation: https://frankfurter.dev/
- Method: GET.
- Endpoint: `https://api.frankfurter.dev/v2/rate/php/{target}`.
- Supported targets: USD, EUR, SGD, JPY, GBP; validated before inserting the
  lower-case code in the fixed endpoint. No additional query parameters.
- Headers: Accept application/json and an educational-project User-Agent.
- No account, API key, or credentials required for the public endpoint.
- Eight-second socket timeout and maximum response size of 65,536 bytes.
- Requests contain only the currency pair; product records and inventory value
  stay local. The public API applies abuse rate limiting; no automatic retries.

Response example recorded during the live check on 13 November 2026:

```json
{"date":"2026-11-12","base":"PHP","quote":"USD","rate":0.015754}
```

Rate observations can differ from today's date and are reference rates rather
than guaranteed real-time market prices. Display the returned date and provider.
The adapter validates JSON shape, matching pair, ISO date and finite positive
numeric rate; numeric parsing uses Decimal to retain returned precision.

## Cache and failures

Successful quotes cache for 900 seconds in an ExchangeService instance using a
monotonic clock. Each pair has a separate entry. A cached quote still converts
the current SQLite inventory total, and reports label it cached. A new CLI
invocation starts a new process/cache. Failed requests are not cached; a failed
refresh never silently returns an expired rate.

Unsupported input raises ValueError before network access. HTTP 429 displays
wait-before-retry guidance; other HTTP failures include status. Connection
failures, timeouts, interrupted HTTP responses, oversized/empty/malformed data and invalid rates/dates raise
RuntimeError with useful messages. The CLI displays the error and returns status
1; database stock is unchanged. SQLite setup/access failures also display errors.
The service caller can catch these errors and continue other inventory work.

## Verification and evidence

```powershell
python -m unittest discover -s tests -v
python scripts/verify_integration.py
```

The evidence script runs offline tests and a separate real CLI report using an
isolated temporary demo database. It records actual statuses, output and
timestamps under `evidence/`. Controlled API tests do not prove internet
availability; the live CLI result does. Review results after every relevant
change rather than reusing an earlier pass count.

Coverage includes existing team service tests, quote validation, API failures,
cache boundaries/recalculation, original-module import safety, legacy data
preservation, persistence, atomic rollbacks, concurrent withdrawals, stale edits,
archives and actual SQLite-to-report wiring.

The original branches and final API changes still need team review on GitHub.
Instructor approval, personal extension evidence and presentation are course
tasks beyond this local connection. Review the combined branch diff before
choosing a PR base; both team backend branches are now dependencies.
