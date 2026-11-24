# Test plan

Deterministic tests exercise units and real temporary SQLite databases. API failure tests inject responses; actual executable sessions verify navigation and files. Tests do not modify the operator's database.

```powershell
python -m unittest discover -s tests -v
python scripts/verify_integration.py --live --clean-env
```

The second command refreshes evidence, makes five real requests and launches a new environment without pip/packages. Temporary databases are removed. Omit --live for offline testing. Results describe the last invocation, not a general benchmark.

| Requirement | Primary tests |
| --- | --- |
| FR-01/02 product creation/listing | inventory_service, sqlite_integration, application_connection, cli |
| FR-03 editing/version | application_connection, sqlite_integration, cli stale-edit workflow |
| FR-04/05 stock integrity | sqlite_integration atomic/concurrency cases, cli session |
| FR-06/07 search/reorder | inventory_service, application_connection, cli |
| FR-08/09 history/archive | sqlite_integration, repository_validation, cli |
| FR-10 summary/precision | currency_reporting, cli money formatting |
| FR-11 external reporting | exchange_service, currency_reporting, cli and actual live-*.txt |
| FR-12 CSV | csv_export, cli actual files/overwrite/database protection |
| FR-13 persistence/migration | schema_migration, legacy_entry_points, import_safety |
| FR-14 cancel/close | cli :back, invalid choice, EOF, outside-folder subprocess |
| NFR integrity/precision/security | rollback, concurrent withdrawal, version, numeric/text and formula checks |
| NFR usability/portability/offline | menu sessions, clean environment, controlled API errors |

## Manual acceptance

1. Start with a new --db path; verify empty lists.
2. Add NB001 / Notebook / School Supplies / 10 / 12.50 / 3.
3. Receive 5, then issue 12 with meaningful reasons: balance 3, low-stock status.
4. Edit name to Revised notebook and cost to 20.00: quantity 3, total PHP 60.00.
5. Search revised; inspect history and summary; export CSV.
6. Attempt issue 4: rejected, unchanged balance/history.
7. Trigger a real currency report; observe provider/date or clear connection error.
8. Exit and restart the same database: saved values persist.
9. Issue final 3 for a real reason; archive with YES: hidden from active list, history preserved.

No formal coverage percentage, large-data benchmark, arbitrary corruption recovery, other-OS verification or personal IDE evidence is claimed. Failures must not be replaced by fabricated results.
