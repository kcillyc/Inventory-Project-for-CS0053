# User manual

## Purpose and requirements

Simple Inventory records products, stock receipts/issues and current value for a local stockroom operator. Use Python 3.11+ with SQLite 3.25+, a terminal and a writable local folder. A typical Windows computer is sufficient; no formal minimum RAM/CPU benchmark was performed. Python/SQLite are the only runtime requirements. Internet is needed only for reference currency reports.

## Install and start

1. Extract the entire package; do not run one file from inside the ZIP.
2. Open a terminal in the extracted folder and check python --version.
3. Run python app.py --menu, or double-click Run Inventory.cmd on Windows.
4. For a practice session use python app.py --menu --demo --db demo.db. This creates fictional Notebook stock only if demo.db does not already exist.
5. Choose an action number and press Enter. Use :back inside any form to cancel. Enter retains values shown in brackets.

Default inventory.db is beside app.py. A relative --db path is relative to the terminal's current directory. Saved actions commit immediately; there is no separate Save All step. No flags runs a summary, so use --menu for interactive operation.


## 1. View products

Choose 1. Read product ID, SKU, name, category, quantity, PHP unit cost, reorder level and stock status. Only active products appear. Long values wrap instead of being discarded. Empty lists display No matching records. Keep the ID for edit, stock and archive actions.

## 2. Add a product

Choose 2 and enter SKU, name, category, opening quantity, unit cost in PHP and reorder level. Example: NB001 / Notebook / School Supplies / 10 / 12.50 / 3. A successful message gives the new ID. Positive opening stock creates an Opening stock movement; zero opening stock does not.

SKUs are uppercase, maximum 30 characters, start with a letter or digit, and otherwise allow letters, digits, hyphens and underscores. Names are up to 100 characters; categories up to 60. Quantities and thresholds are nonnegative whole numbers. Costs use at most two decimals, without PHP signs, commas or scientific notation. Duplicate SKUs, including archived ones, are rejected.

## 3. Edit product details

Choose 3 and enter an active product ID. Enter new SKU, name, category, cost and reorder level, or press Enter to keep each bracketed value. Quantity changes belong to stock in/out. If another action changes the product after the form opens, saving is rejected; open the edit form again and reapply the change after checking current data. Changing current cost changes current valuation, not movement quantities or historical snapshots.

## 4-5. Receive and issue stock

Choose 4 for stock in or 5 for stock out. Enter ID, positive whole quantity and a specific 3-200 character reason. Example: Supplier delivery or Issued to classroom. The program reports remaining stock. Enter the amount as positive for either menu action; the application applies the sign.

Overdrawing stock, zero amounts and invalid reasons are rejected without a partial change. Product balance and movement are saved together. An incorrect completed stock transaction should be corrected by an opposite adjustment with a clear reason; do not edit the database manually or erase history.

## 6-7. Search and reorder list

Choose 6 and type any part of SKU, name or category. Search ignores letter case; blank search returns all active rows. Choose 7 to list active products whose quantity is less than or equal to reorder level, including out-of-stock products. These are alerts, not automatically generated orders.


## 8. Movement history

Choose 8 and enter a positive number of recent events, or Enter for 200. Events appear newest first with time, SKU, signed change, balance and reason. Positive delta means stock in, negative means stock out, and a zero event means archived. New records show UTC. A local* marker identifies a preserved old timestamp with unknown timezone. To convert known UTC to Philippine time, add eight hours.

Movement SKU/name are snapshots from event time. Editing a product does not rewrite earlier records. This history covers stock and archival events, not every metadata edit or operator identity.


## 9. Archive an exhausted product

First reduce stock to zero through a legitimate stock-out adjustment. Choose 9, enter ID, review the product and type YES to confirm. Any other answer cancels. Archival hides the product from active lists and summaries, preserves its history and reserves its SKU. The menu has no unarchive or permanent-delete function. Do not issue stock solely to hide an item if that does not reflect a real stock event.

## 10. Summary

Choose 10 to see active product count, total units, number at or below reorder level, and current inventory value. Value is the sum of current quantity multiplied by current unit cost. This is not sales revenue, profit, FIFO valuation or an accounting ledger.


## 11. Currency report

Choose 11 and enter USD, EUR, SGD, JPY or GBP (Enter defaults to USD). The application requests a reference rate, then shows local value, converted total, rate, provider and observation date. Only currency codes leave the computer. A successful quote is cached per currency for 15 minutes in the current session and labeled Cached on reuse. The rate date can precede the current date; reference rates are not trading quotes. All converted targets use two decimals, including JPY.

If the provider or internet is unavailable, an error returns you to the menu. Use local inventory normally and retry later. No fictional or expired fallback rate is shown. The request has an eight-second socket timeout, although total network wait may vary.


## 12. Export CSV

Choose 12, accept the timestamped reports/inventory-....csv path or enter another .csv filename. Relative paths use the terminal's current folder. Directories are created as needed. Existing files require YES before replacement. The active database cannot be selected as the export destination, even if its filename ends in .csv.

The UTF-8 CSV includes active SKU, name, category, quantity, unit cost, reorder and value. Text starting with a spreadsheet formula character is prefixed with an apostrophe. Costs remain exact decimal strings. The export is a report, not a backup: it has no movements, archived rows, product IDs or versions and there is no CSV import function. See evidence/example-export.csv for an actual generated example.

## Exit, backup and restore

Choose 0. Ctrl+C or end of input also closes the menu; completed actions remain saved and incomplete forms do not submit. Restart with the same --db path to reopen the same data.

Close every application instance before manual backup, then copy the database to a separate safe folder. Do not copy only a live WAL database's main file. Keep automatic pre-migration backups. To restore manually, close all instances, preserve current data separately, and replace the chosen database with a known valid closed backup. See DATABASE_SCHEMA.md for the supported legacy migration. Use separate practice databases to avoid accidental changes to real inventory.

## Troubleshooting

| Symptom | Action |
| --- | --- |
| Python is not recognized | Install Python 3.11+ and enable its command-line launcher/PATH, then reopen the terminal |
| A summary appears instead of menu | Include --menu |
| Database appears empty | Check the selected path; relative --db paths depend on current folder |
| SKU already exists | Search for it; archived SKUs remain reserved |
| Stock operation rejected | Check positive whole amount, available quantity, active ID and reason length |
| Product changed since opening | Reopen the edit form and review current values |
| Database is locked | Close other writers and retry; avoid shared/network-drive use |
| Cannot write database/CSV | Move to a writable folder and check filename, open-file locks and free space |
| Currency error | Check connection, allowlisted currency and provider availability; local work stays available |
| Migration reports ambiguous columns | Retain backups and ask the database maintainer to inspect; do not delete data to force startup |
| Table wraps awkwardly | Widen the terminal; the original text is preserved across wrapped rows |

The program is intended for local trusted use. There is no application login, encryption, cloud synchronization or high-volume/multi-user deployment support.
