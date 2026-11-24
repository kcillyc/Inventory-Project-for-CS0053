"""Record repeatable offline tests and optional real network/clean-environment checks."""

import argparse
import io
import json
import os
import platform
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
import venv
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def command(arguments, *, cwd=ROOT, text_input=None, timeout=120):
    started = time.perf_counter()
    completed = subprocess.run(
        arguments,
        cwd=cwd,
        input=text_input,
        capture_output=True,
        text=True,
        timeout=timeout,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONIOENCODING": "utf-8"},
    )
    return {
        "exit_code": completed.returncode,
        "seconds": round(time.perf_counter() - started, 3),
        "output": completed.stdout + completed.stderr,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Make five real external API requests")
    parser.add_argument(
        "--clean-env",
        action="store_true",
        help="Also launch using a new venv without pip or packages",
    )
    args = parser.parse_args()
    evidence = ROOT / "evidence"
    evidence.mkdir(exist_ok=True)
    stream = io.StringIO()
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"))

    def cases(suite):
        for case in suite:
            if isinstance(case, unittest.TestSuite):
                yield from cases(case)
            else:
                yield case

    groups = dict(sorted(Counter(test.__class__.__module__ for test in cases(suite)).items()))
    started = time.perf_counter()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    seconds = round(time.perf_counter() - started, 3)
    (evidence / "test-results.txt").write_text(stream.getvalue(), encoding="utf-8")
    report = {
        "executed_at_utc": datetime.now(timezone.utc).isoformat(),
        "python": platform.python_version(),
        "sqlite": sqlite3.sqlite_version,
        "platform": platform.system(),
        "offline_tests": {
            "run": result.testsRun,
            "failures": len(result.failures),
            "errors": len(result.errors),
            "skipped": len(result.skipped),
            "successful": result.wasSuccessful(),
            "seconds": seconds,
            "by_module": groups,
            "output_file": "test-results.txt",
        },
    }
    with tempfile.TemporaryDirectory(prefix="inventory-verification-") as directory:
        temporary = Path(directory)
        export = temporary / "inventory.csv"
        answers = [
            "2",
            "NB001",
            "Notebook",
            "School Supplies",
            "10",
            "12.50",
            "3",
            "4",
            "1",
            "5",
            "Supplier delivery",
            "5",
            "1",
            "12",
            "Issued to classroom",
            "3",
            "1",
            "",
            "Revised notebook",
            "",
            "20.00",
            "",
            "1",
            "6",
            "revised",
            "7",
            "8",
            "200",
            "10",
            "12",
            str(export),
            "5",
            "1",
            "4",
            "Excessive issue rejected",
            "10",
            "0",
        ]
        workflow = command(
            [
                sys.executable,
                "-B",
                str(ROOT / "app.py"),
                "--menu",
                "--db",
                str(temporary / "workflow.db"),
            ],
            cwd=temporary,
            text_input="\n".join(answers) + "\n",
        )
        (evidence / "menu-session.txt").write_text(workflow["output"], encoding="utf-8")
        (evidence / "menu-inputs.json").write_text(json.dumps(answers, indent=2), encoding="utf-8")
        export_ok = export.is_file()
        if export_ok:
            (evidence / "example-export.csv").write_bytes(export.read_bytes())
        report["actual_menu_session"] = {
            "exit_code": workflow["exit_code"],
            "csv_created": export_ok,
            "error_recovered": "negative quantity" in workflow["output"]
            and "Current inventory value: PHP 60.00" in workflow["output"],
            "output_file": "menu-session.txt",
            "input_file": "menu-inputs.json",
        }
        if args.live:
            live = {}
            for target in ("USD", "EUR", "SGD", "JPY", "GBP"):
                data = command(
                    [
                        sys.executable,
                        "-B",
                        str(ROOT / "app.py"),
                        "--demo",
                        "--db",
                        str(temporary / "live.db"),
                        "--report",
                        "--currency",
                        target,
                    ]
                )
                name = "live-" + target.lower() + ".txt"
                (evidence / name).write_text(data.pop("output"), encoding="utf-8")
                live[target] = {**data, "output_file": name}
            report["actual_live_cli_reports"] = live
        if args.clean_env:
            env_path = temporary / "clean-python"
            builder = venv.EnvBuilder(with_pip=False)
            builder.create(env_path)
            executable = Path(builder.ensure_directories(env_path).env_exe)
            clean = command(
                [
                    str(executable),
                    "-B",
                    str(ROOT / "app.py"),
                    "--menu",
                    "--demo",
                    "--db",
                    str(temporary / "clean.db"),
                ],
                cwd=temporary,
                text_input="1\n10\n0\n",
            )
            (evidence / "clean-environment.txt").write_text(clean.pop("output"), encoding="utf-8")
            report["clean_environment"] = {
                **clean,
                "packages_installed": 0,
                "output_file": "clean-environment.txt",
            }
    (evidence / "integration-results.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2))
    success = (
        result.wasSuccessful()
        and workflow["exit_code"] == 0
        and export_ok
        and report["actual_menu_session"]["error_recovered"]
    )
    if args.live:
        success = success and all(
            item["exit_code"] == 0 for item in report["actual_live_cli_reports"].values()
        )
    if args.clean_env:
        success = success and report["clean_environment"]["exit_code"] == 0
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
