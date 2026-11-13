# Coding and commit standards

Use `snake_case` for Python files, functions, and variables; `PascalCase` for
classes; and uppercase names for constants. Use four spaces for each indentation
level. The workspace `.editorconfig` records UTF-8, whitespace, and indentation
preferences for editors that support it.

Keep application SQL, schema initialization, and database migrations in
`backend/sqlite_repository.py`. Business rules belong in `InventoryService`,
input checks in `validators.py`, and external HTTP requests in
`exchange_service.py`. The compatibility functions in `inventory.py` call these
layers and do not contain SQL. Test fixtures may use SQL against temporary
databases to verify storage behavior and migration safety.

Choose descriptive names and useful validation errors. Reuse the service and
repository instead of maintaining a second implementation of stock changes.
Use comments and docstrings to explain transactions, migrations, precision, and
other behavior that is not obvious from a statement alone.

Keep actual secrets, `.env` files, local environments, caches, operational
databases, and migration backups out of Git. Commit only placeholder values in
an `.env.example` if configuration examples are needed. Run the tests before
committing:

```powershell
python -m unittest discover -s tests -v
git diff --check
```

## Commit messages

Use `type: short description`. Choose `feat`, `fix`, `docs`, `test`, `refactor`,
`style`, or `chore` to match the change. Start the description with an action
verb, use lowercase wording without a final period, and aim for approximately
50 to 72 characters when practical. For example:

```text
fix: migrate the legacy inventory cost column safely
refactor: keep inventory queries in the repository
test: verify migration preserves stock and movement history
docs: explain the database backup and migration procedure
chore: configure workspace indentation and cache exclusions
```

Keep each commit focused. Add a body after a blank line when the reason needs
explanation, and reference a relevant GitHub Issue when one exists. Preserve
published team history; apply this convention to new commits rather than
rewriting existing authors, commit IDs, or pull requests.

## Database migration and recovery

The database specification names the monetary column `unit_cost_cents`, storing
integer PHP centavos. Older databases used `unit_costs_cents`. Before the first
opening with the updated code, stop other database writers and keep a separate
backup. The repository also automatically creates a unique
`<name>.before-unit-cost-migration-<unique>.db` beside a legacy database using
SQLite's backup API, including committed data in its WAL file.

The column rename and schema initialization run in one transaction. Product
IDs, quantities, costs, versions, archived flags, movement history, and
relationships are preserved. If migration fails, initialization rolls back.
An already migrated database is reused without generating another backup.

The automatic backup retains the old column name. To recover, stop the app and
all other writers, retain the current database and its WAL/SHM files together,
then copy the backup to a new recovery path with no existing WAL/SHM files. Open
that recovery copy with
the previous code, or with the updated app to migrate it again. Do not mix WAL
or SHM files from a different database snapshot. Keep the failed database and
backup until recovery is verified.

Migration needs SQLite 3.25 or newer. An ambiguous database containing both
cost-column spellings requires review rather than an automatic choice between
values.
