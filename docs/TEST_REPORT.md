# Test report

**Verification date:** 23 November 2026  
**Recorded UTC time:** 2026-11-23T11:05:53.941867+00:00  
**Environment:** Windows, Python 3.12.14, SQLite 3.53.1

## Actual outcome

**102 tests passed; 0 failures, 0 errors, 0 skipped.** Offline run: 1.912 seconds. No test-coverage percentage is claimed.

| Test module | Cases |
| --- | ---: |
| test_application_connection | 13 |
| test_cli | 18 |
| test_csv_export | 3 |
| test_currency_reporting | 10 |
| test_exchange_service | 14 |
| test_import_safety | 1 |
| test_inventory_service | 3 |
| test_legacy_entry_points | 2 |
| test_repository_validation | 8 |
| test_schema_migration | 9 |
| test_sqlite_integration | 13 |
| test_validators | 8 |

## Additional actual checks

| Check | Result |
| --- | --- |
| Second interpreter | Same 102 tests passed on Python 3.14.3 / SQLite 3.52.0; 2.097 seconds |
| Real executable menu | Add, receive, issue, edit, view, search, low stock, history, summary and real CSV; invalid overdraw returned to menu, unchanged balance |
| Clean environment | Python 3.12.14 venv without pip or third-party packages; executable menu launched outside project folder, displayed demo and summary, exited 0 |
| Black 24.10.0 | Check passed; 26 Python files left unchanged |
| Ruff 0.8.6 | All configured checks passed |
| Live external calls | All five supported targets returned real dated provider data; each executable exited 0 |

| Currency | Actual CLI exit | Duration (s) |
| --- | ---: | ---: |
| USD | 0 | 1.052 |
| EUR | 0 | 0.73 |
| SGD | 0 | 0.752 |
| JPY | 0 | 0.652 |
| GBP | 0 | 0.637 |

## Evidence and reproduction

See evidence/integration-results.json, test-results.txt, test-results-python314.txt, menu-session.txt, menu-inputs.json, example-export.csv, clean-environment.txt, format-results.txt, lint-results.txt and live-*.txt. These are actual program/tool outputs. Controlled API tests are separate from live calls. Temporary verification databases were removed.

Run python -m unittest discover -s tests -v for repeatable offline tests. Run python scripts/verify_integration.py --live --clean-env to refresh full evidence; network results and timing can differ.

## Scope and limitations

Tests cover validation types/bounds, real persistence, atomic rollback, concurrent stock updates, stale edits, archives, historical snapshots, supported migrations/backups, HTTP failures/malformed payloads, cache, exact conversion, CSV protection and menu recovery. They do not establish arbitrary schema/corrupt-file recovery, heavy-load performance, formal accessibility, Python 3.11 execution or other-OS support. Formatter/linter results apply to the configured rule set.

No instructor approval, extension installation, student contribution or account/history evidence was inferred from these tests. The package archive is checked separately in evidence/package-verification.json after assembly.
