"""Save actual offline-test and separate live database-to-API execution results."""

import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def run(command):
    completed = subprocess.run(
        command, cwd=ROOT, capture_output=True, text=True, timeout=90
    )
    return {
        "exit_code": completed.returncode,
        "output": completed.stdout + completed.stderr,
    }


def main():
    evidence = ROOT / "evidence"
    evidence.mkdir(exist_ok=True)
    tests = run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"])
    (evidence / "test-results.txt").write_text(tests["output"], encoding="utf-8")
    with tempfile.TemporaryDirectory() as folder:
        live = run(
            [
                sys.executable,
                "app.py",
                "--demo",
                "--db",
                str(Path(folder) / "live-demo.db"),
                "--report",
                "--currency",
                "USD",
            ]
        )
    (evidence / "live-report.txt").write_text(live["output"], encoding="utf-8")
    report = {
        "executed_at_utc": datetime.now(timezone.utc).isoformat(),
        "python": sys.version.split()[0],
        "offline_tests": {
            "exit_code": tests["exit_code"],
            "output_file": "test-results.txt",
        },
        "actual_live_cli_report": {
            "exit_code": live["exit_code"],
            "output_file": "live-report.txt",
            "database": "isolated temporary demo, removed after verification",
        },
    }
    (evidence / "integration-results.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    print(tests["output"])
    print(live["output"])
    print(json.dumps(report, indent=2))
    return 0 if tests["exit_code"] == live["exit_code"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
