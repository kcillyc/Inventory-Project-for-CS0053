# Simple Inventory: Stock Tracking and Currency Reporting

A local Python and SQLite application for a small stockroom, combining the supplied backend, SQLite and API functionality. Version 1.0.0 labels this local package.

## Quick start

1. Extract the entire folder to a writable location.
2. Install Python 3.11+ with its standard sqlite3 module.
3. Open a terminal in this folder:

```powershell
python app.py --menu
```

On Windows you can also double-click **Run Inventory.cmd**. It uses an installed py -3 or python runtime. No runtime packages, account, API key or paid database are required. Internet is needed only for currency reports.

For fictional data in a separate database:

```powershell
python app.py --menu --demo --db demo.db
```

Demo stock is inserted only if the selected file does not already exist. Normal launch opens or creates inventory.db beside app.py. Relative --db paths are relative to the terminal's current folder.

## Menu

| Menu | Action |
| --- | --- |
| 1 / 2 / 3 | List, add and edit products |
| 4 / 5 | Receive or issue stock with a reason |
| 6 / 7 | Search and show products at or below reorder level |
| 8 / 9 | Movement history and zero-stock archival |
| 10 / 11 / 12 | Summary, currency conversion and CSV export |
| 0 | Close safely |

Type :back inside a form to cancel. Enter retains bracketed defaults. Invalid submissions return to the menu without changing saved inventory.

```powershell
python app.py --summary --db demo.db
python app.py --report --currency USD --db demo.db
python -m backend.exchange_service --target EUR
python -m unittest discover -s tests -v
python scripts/verify_integration.py --live --clean-env
```

No flags runs the offline summary for compatibility. inventory.py retains original demonstration helper names and uses inventory.db in the current working folder; use app.py --menu for normal operation.

## Structure

```text
CS0053-Inventory-Complete/
|-- app.py                         # CLI entry point
|-- application_connection.py      # Validated action dispatcher
|-- inventory.py                   # Original helper compatibility
|-- backend/
|   |-- models.py
|   |-- validators.py
|   |-- repository_interface.py
|   |-- inventory_service.py
|   |-- sqlite_repository.py
|   `-- exchange_service.py
|-- ui/
|   |-- cli.py
|   `-- formatting.py
|-- tests/                         # 102 offline tests
|-- scripts/verify_integration.py
|-- docs/                          # Requirements, design, API, manual, reports
|-- docs/diagrams/                 # Mermaid and SVG illustrations
|-- screenshots/application/       # Rendered actual-output excerpts
|-- evidence/                      # Actual execution logs and example CSV
|-- output/pdf/                    # Printable manual
|-- .vscode/                       # Debugging, tests and extension settings
|-- .editorconfig
|-- .env.example
|-- .gitignore                     # Handwritten configuration
|-- pyproject.toml
|-- requirements.txt               # Standard library only
|-- requirements-dev.txt           # Optional development tools
|-- Run Inventory.cmd
`-- VERSION
```

Start with [User manual](docs/USER_MANUAL.md), [SRS](docs/SRS.md), [Architecture](docs/architecture.md), [API documentation](docs/API_DOCUMENTATION.md), and [Test report](docs/TEST_REPORT.md). 

This is a local single-user tool with no accounts, web server, sales processing or restore button. Value means current quantity multiplied by current unit cost. Close every instance before copying the database for backup. CSV exports contain active products only and cannot restore history.

