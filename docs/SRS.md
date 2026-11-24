# Software Requirements Specification

**System:** Inventory: Stock Tracking and Currency Reporting  
**Version:** 1.0.0 

## Purpose and scope

A terminal application for one stockroom operator managing nonnegative whole-unit stock locally. Products have a unique SKU, name, category, quantity, PHP unit cost and reorder level. Movements explain stock changes. The only network dependency is a read-only reference exchange-rate API.

## Functional requirements

| ID | Requirement | Acceptance criterion |
| --- | --- | --- |
| FR-01 | Register products | Valid unique SKU and metadata create a saved product. Positive opening quantity creates a movement atomically; zero opening quantity does not. |
| FR-02 | View products | Menu 1 shows active saved products, costs and status; empty results have a clear message. |
| FR-03 | Edit metadata | SKU, name, category, cost and reorder are editable; Enter keeps defaults. Quantity is unchanged and stale versions are rejected. |
| FR-04 | Receive stock | Positive quantity and valid reason increase stock and create history atomically. |
| FR-05 | Issue stock | Positive quantity and valid reason decrease stock. Overdraw changes neither product nor history. |
| FR-06 | Search | Case-insensitive substring search covers SKU, name and category. Blank query returns all active products. |
| FR-07 | Reorder list | Includes active products whose quantity is at or below reorder level, including zero. |
| FR-08 | History | Newest first, showing time, SKU snapshot, signed delta, balance and reason; positive limit required. |
| FR-09 | Archive | Only zero-stock active products after YES confirmation. History retained and SKU reserved. |
| FR-10 | Summary | Active count, total units, reorder count and sum of quantity times current cost. |
| FR-11 | Currency report | USD/EUR/SGD/JPY/GBP use a real or fresh cached quote with provider/date; errors preserve local functionality. |
| FR-12 | CSV | Active rows, exact amounts, quoted text and formula protection; .csv filename required, existing files require YES, active database protected. |
| FR-13 | Persistence/migration | Restart retains data. Supported old cost-column spelling is migrated transactionally after a consistent backup. Ambiguous columns are rejected. |
| FR-14 | Cancel/exit | :back cancels forms; 0, EOF or Ctrl+C closes the menu; completed actions remain saved. |

## Data rules

| Field | Rule |
| --- | --- |
| SKU | Trimmed uppercase, 1-30 characters; first A-Z/0-9, remainder A-Z/0-9/underscore/hyphen; unique including archived products |
| Name/category | Trimmed text, 1-100 / 1-60 characters; ASCII control characters rejected |
| Quantity/reorder/cost centavos | Integer 0 through 9,223,372,036,854,775,807; no booleans or fractions |
| PHP cost input | Nonnegative decimal text with at most two decimals, converted exactly to centavos |
| ID/version/history limit | Positive supported integer |
| Adjustment | Nonzero signed integer; resulting quantity must remain nonnegative and within range |
| Reason | Trimmed text 3-200 characters; no ASCII control characters |
| Search | Trimmed text up to 100 characters; empty permitted |

Opening stock is system-generated. Archive writes a zero-delta Product archived event; operators cannot submit zero adjustments. Existing movement SKU/name snapshots retain old values after edits.

## Nonfunctional requirements

| ID | Category | Requirement / evidence |
| --- | --- | --- |
| NFR-01 | Reliability | Atomic stock/history writes, rollback, guarded concurrent withdrawals and version checks; verified with real SQLite tests. |
| NFR-02 | Usability | Numbered menu, defaults, cancellation, wrapped tables and understandable errors; exercised by session tests. |
| NFR-03 | Precision | Integer centavos and Decimal conversion; tests include values beyond float precision. |
| NFR-04 | Performance | Local actions target under one second on small classroom data; not a benchmark guarantee. HTTP has an 8-second socket timeout and 64 KiB response cap; total wall time can vary. |
| NFR-05 | Security | Parameterized SQL, allowlisted currencies, no credentials, bounded inputs. Computer permissions protect local files; no application authentication. |
| NFR-06 | Maintainability | Separate UI, dispatcher, service, repository and HTTP modules; formatter/linter config and repeatable tests. |
| NFR-07 | Portability | Python 3.11+ / SQLite 3.25+. Verified on Windows with Python 3.12.14 and 3.14.3; other systems and 3.11 untested. |
| NFR-08 | Availability | Core work operates offline. Failures do not substitute fictional or expired rates. |

## Constraints

Small local inventory, not a simultaneous multi-user service. There are no accounts/operator attribution, sales/orders, tax, FIFO/weighted-average costing, encryption, historical cost ledger, restore interface or archive undo. Currency displays use two decimals, including JPY. Filtering occurs in Python and is not optimized for very large catalogs.

See [Test plan](TEST_PLAN.md) for traceability and [Test report](TEST_REPORT.md) for actual results. 