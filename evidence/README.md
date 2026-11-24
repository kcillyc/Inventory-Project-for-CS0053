# Actual execution evidence

integration-results.json records UTC execution time, Python/SQLite versions, tests, menu workflow, optional live calls and clean-environment launch. test-results.txt lists each test. live-<currency>.txt contains actual external reports; new dates/rates may differ.

menu-session.txt is stdout from the actual app.py executable. menu-inputs.json records exact input. Piped input is not echoed, so prompts may share a line. Logs retain actual temporary paths; temporary databases are removed after verification. example-export.csv was copied from the actual generated file before cleanup.

screenshots/application contains rendered excerpts of these actual logs for readability, not native terminal or IDE screenshots. No personal approvals, extension use or remote history are fabricated.

Run python scripts/verify_integration.py --live --clean-env to refresh evidence. Requested live or clean-environment failures and offline failures produce a nonzero exit. Omit --live for offline checks.
