#!/usr/bin/env python3
"""Check when the audit reminder says a run is due.

Run: uv run --no-project --python ">=3.14" tests/test_audit_reminder.py
"""

import importlib.util
import json
import sys
import tempfile
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "tools" / "audit_reminder.py"
SPEC = importlib.util.spec_from_file_location("audit_reminder", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
audit_reminder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit_reminder)

NOW = datetime(2026, 11, 25, 12, 0, tzinfo=UTC)


def totals_with_run(folder: Path, run: str) -> Path:
    totals = folder / "totals.jsonl"
    old = json.dumps({"run": (NOW - timedelta(days=90)).isoformat(), "months": {}})
    totals.write_text(old + "\n" + json.dumps({"run": run, "months": {}}) + "\n", encoding="utf-8")
    return totals


def missing_file_is_due(folder: Path) -> bool:
    return audit_reminder.due(folder / "absent.jsonl", NOW)


def run_22_days_old_is_due(folder: Path) -> bool:
    return audit_reminder.due(totals_with_run(folder, (NOW - timedelta(days=22)).isoformat()), NOW)


def run_20_days_old_is_not_due(folder: Path) -> bool:
    return not audit_reminder.due(totals_with_run(folder, (NOW - timedelta(days=20)).isoformat()), NOW)


def unparsed_time_is_due(folder: Path) -> bool:
    return audit_reminder.due(totals_with_run(folder, "last Tuesday"), NOW)


def cut_short_last_line_is_due(folder: Path) -> bool:
    totals = totals_with_run(folder, (NOW - timedelta(days=1)).isoformat())
    with totals.open("a", encoding="utf-8") as handle:
        handle.write('{"run": "2026-11')
    return audit_reminder.due(totals, NOW)


def long_last_line_is_read_whole(folder: Path) -> bool:
    totals = folder / "totals.jsonl"
    sessions = {f"session-{number}": {"month": "2026-11", "skipped": 0, "counts": {}} for number in range(5000)}
    line = json.dumps({"run": (NOW - timedelta(days=1)).isoformat(), "sessions": sessions})
    totals.write_text(line + "\n", encoding="utf-8")
    return len(line) > 4 * audit_reminder.CHUNK_BYTES and not audit_reminder.due(totals, NOW)


def long_last_line_after_a_short_line_is_read_whole(folder: Path) -> bool:
    totals = folder / "totals.jsonl"
    sessions = {f"session-{number}": {"month": "2026-11", "skipped": 0, "counts": {}} for number in range(1500)}
    old = json.dumps({"run": (NOW - timedelta(days=90)).isoformat(), "months": {}})
    line = json.dumps({"run": (NOW - timedelta(days=1)).isoformat(), "sessions": sessions})
    totals.write_text(old + "\n" + line + "\n", encoding="utf-8")
    size = totals.stat().st_size
    return size % audit_reminder.CHUNK_BYTES != 0 and size > audit_reminder.CHUNK_BYTES and not audit_reminder.due(totals, NOW)


CASES: list[tuple[str, Callable[[Path], bool]]] = [
    ("a long last line after a short line is read whole", long_last_line_after_a_short_line_is_read_whole),
    ("a missing totals file is due", missing_file_is_due),
    ("a last run 22 days old is due", run_22_days_old_is_due),
    ("a last run 20 days old is not due", run_20_days_old_is_not_due),
    ("a last run whose time does not parse is due", unparsed_time_is_due),
    ("a last line cut short is due", cut_short_last_line_is_due),
    ("a last line longer than one read is read whole", long_last_line_is_read_whole),
]


def main() -> None:
    failures = 0
    for name, case in CASES:
        with tempfile.TemporaryDirectory() as folder:
            try:
                ok = case(Path(folder))
            except Exception as error:  # A crash in one case fails that case, and the other cases still run.
                print(f"     {type(error).__name__}: {error}")
                ok = False
        print(f"{'ok ' if ok else 'FAIL'} {name}")
        failures += not ok
    print("ALL PASS" if not failures else f"FAILURES: {failures}")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
