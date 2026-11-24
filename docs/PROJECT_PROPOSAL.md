# Project proposal

**Title:** Inventory: Stock Tracking and Currency Reporting  
**Course:** CS0053 - Programming Tools and Techniques  

## Abstract and objectives

Small stockrooms often keep deliveries and issues in separate notes, creating unclear balances and duplicate records. The application maintains products and stock movements in SQLite. Operators search, edit metadata, receive and issue quantities, inspect history, archive exhausted products and export inventory. An external API supplies reference currency conversions of current value.

Objectives: maintain validated unique SKUs and exact centavo costs; save balances and movements atomically; identify reorder needs; demonstrate HTTP integration, Repository pattern, repeatable testing and documented tools.

## Scope and resources

Intended for one stockroom operator on one local computer. Python, SQLite, a terminal and writable storage are sufficient; internet is optional except for live exchange reports. No runtime package installation or credentials are needed. Computer and network access are supplied by the team.

Included: products, stock movements, search, low stock, archival, summaries, currency reports, CSV, compatible migration, tests and documentation. Excluded: authentication, sales, purchase orders, multiple warehouses, barcode hardware, accounting, cloud synchronization and public hosting.

## Suggested four-member allocation

| Role | Main responsibility | Review handoff |
| --- | --- | --- |
| Requirements and integration | Castro	| SRS, acceptance and documentation |
| Backend and validation	| Cam	| Models, service, shared validators, service tests |
| Database and persistence	| Teng	| SQLite, migration, transactions |
| API |	Bernaldez |	Exchange integration |

