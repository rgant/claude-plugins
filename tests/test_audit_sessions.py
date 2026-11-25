#!/usr/bin/env python3
"""Check the session audit against fake transcripts in a temporary folder.

Run: uv run --no-project --python ">=3.14" tests/test_audit_sessions.py
"""

import importlib.util
import json
import os
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "tools" / "audit_sessions.py"
SPEC = importlib.util.spec_from_file_location("audit_sessions", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
audit_sessions = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit_sessions)

STAMP = "2026-11-03T10:00:00Z"


def tool_use(name: str, tool_input: dict[str, object]) -> str:
    """Return one transcript line for an assistant event with one tool call."""
    block = {"type": "tool_use", "name": name, "input": tool_input}
    return json.dumps({"type": "assistant", "timestamp": STAMP, "message": {"content": [block]}})


def tests_counts(lines: list[str]) -> dict[str, int]:
    return dict(audit_sessions.audit_session(lines, audit_sessions.CHECKS).counts["tests"])


def write_to_test_file_counts_the_pattern(_folder: Path) -> bool:
    line = tool_use("Write", {"file_path": "tests/test_x.py", "content": "from unittest.mock import MagicMock\n"})
    counts = tests_counts([line])
    return counts.get("MagicMock") == 1 and counts.get("edited") == 1 and counts.get("flagged") == 1


def edit_counts_only_added_lines(_folder: Path) -> bool:
    old = "a\nvi.mock('x')\n"
    new = "a\nvi.mock('x')\nvi.mock('y')\n"
    line = tool_use("Edit", {"file_path": "src/a.test.tsx", "old_string": old, "new_string": new})
    return tests_counts([line]).get("vi.mock") == 1


def edit_of_other_file_counts_nothing(_folder: Path) -> bool:
    line = tool_use("Edit", {"file_path": "src/app.py", "old_string": "", "new_string": "MagicMock()\n"})
    return tests_counts([line]) == {}


def malformed_lines_are_skipped(_folder: Path) -> bool:
    lines = [
        "not json",
        json.dumps({"type": "assistant", "timestamp": STAMP}),
        json.dumps({"type": "mode", "timestamp": STAMP}),
        tool_use("Write", {"file_path": "conftest.py", "content": "x = cast(int, y)\n"}),
    ]
    result = audit_sessions.audit_session(lines, audit_sessions.CHECKS)
    return result.skipped == 2 and result.counts["tests"].get("cast(") == 1


def subagent_transcript_is_read_as_its_own_session(folder: Path) -> bool:
    project = folder / "project"
    (project / "session" / "subagents").mkdir(parents=True)
    line = tool_use("Write", {"file_path": "test_a.py", "content": "noqa\n"})
    (project / "session.jsonl").write_text(line + "\n", encoding="utf-8")
    (project / "session" / "subagents" / "agent.jsonl").write_text(line + "\n", encoding="utf-8")
    ids = [session_id for session_id, _ in audit_sessions.audit_projects(folder, audit_sessions.CHECKS, [])]
    return ids == ["session", "session/agent"]


def unreadable_transcript_is_listed_and_the_rest_counted(folder: Path) -> bool:
    project = folder / "project"
    (project / "broken.jsonl").mkdir(parents=True)
    line = tool_use("Write", {"file_path": "test_a.py", "content": "noqa\n"})
    (project / "session.jsonl").write_text(line + "\n", encoding="utf-8")
    unreadable: list[str] = []
    ids = [session_id for session_id, _ in audit_sessions.audit_projects(folder, audit_sessions.CHECKS, unreadable)]
    return ids == ["session"] and unreadable == ["broken"]


def run_main(folder: Path, totals: Path) -> int:
    os.environ["SESSION_AUDIT_TOTALS"] = str(totals)
    try:
        return audit_sessions.main(["--projects", str(folder / "projects")])
    finally:
        del os.environ["SESSION_AUDIT_TOTALS"]


def run_records_each_session_and_no_text(folder: Path) -> bool:
    project = folder / "projects" / "project"
    project.mkdir(parents=True)
    content = "# PRIVATE-MARKER\nfrom unittest.mock import MagicMock\n"
    line = tool_use("Write", {"file_path": "tests/test_x.py", "content": content})
    (project / "session.jsonl").write_text(line + "\n", encoding="utf-8")
    totals = folder / "audit" / "totals.jsonl"
    code = run_main(folder, totals)
    recorded = totals.read_text(encoding="utf-8").splitlines()
    record = json.loads(recorded[0])
    session = record["sessions"]["session"]
    return (
        code == 0
        and len(recorded) == 1
        and "PRIVATE-MARKER" not in recorded[0]
        and "run" in record
        and session["month"] == "2026-11"
        and session["counts"]["tests"]["MagicMock"] == 1
    )


def months_join_every_run_and_newest_record_wins(folder: Path) -> bool:
    totals = folder / "totals.jsonl"
    old = {"month": "2026-10", "skipped": 0, "counts": {"tests": {"MagicMock": 2}}}
    first = {"month": "2026-11", "skipped": 0, "counts": {"tests": {"noqa": 1}}}
    second = {"month": "2026-11", "skipped": 0, "counts": {"tests": {"noqa": 3}}}
    lines = [
        json.dumps({"run": "2026-11-01T00:00:00+00:00", "sessions": {"gone": old, "kept": first}}),
        "not json",
        json.dumps({"run": "2026-11-20T00:00:00+00:00", "sessions": {"kept": second}}),
    ]
    totals.write_text("\n".join(lines) + "\n", encoding="utf-8")
    months = audit_sessions.monthly(audit_sessions.recorded_sessions(totals).values())
    october = months["2026-10"].checks["tests"]["MagicMock"]
    november = months["2026-11"].checks["tests"]["noqa"]
    return (october.sessions, october.count, november.sessions, november.count) == (1, 2, 1, 3)


def call_patterns_skip_longer_words(_folder: Path) -> bool:
    content = "dispatch(event)\nbroadcast(x)\nforecast(y)\nmock.patch(z)\ntyping.cast(int, w)\n"
    counts = tests_counts([tool_use("Write", {"file_path": "tests/test_x.py", "content": content})])
    return counts.get("patch(") == 1 and counts.get("cast(") == 1


def javascript_test_files_count(_folder: Path) -> bool:
    paths = ("src/a.test.js", "src/b.spec.jsx", "src/c.test.mjs")
    lines = [tool_use("Write", {"file_path": path, "content": "vi.mock('x')\n"}) for path in paths]
    return tests_counts(lines).get("edited") == 3


def cut_short_totals_line_keeps_the_next_run(folder: Path) -> bool:
    project = folder / "projects" / "project"
    project.mkdir(parents=True)
    line = tool_use("Write", {"file_path": "tests/test_x.py", "content": "noqa\n"})
    (project / "session.jsonl").write_text(line + "\n", encoding="utf-8")
    totals = folder / "audit" / "totals.jsonl"
    totals.parent.mkdir()
    totals.write_text('{"run": "2026-11', encoding="utf-8")
    code = run_main(folder, totals)
    return code == 0 and "session" in audit_sessions.recorded_sessions(totals)


def empty_projects_records_nothing(folder: Path) -> bool:
    (folder / "projects").mkdir()
    totals = folder / "audit" / "totals.jsonl"
    return run_main(folder, totals) == 1 and not totals.exists()


CASES: list[tuple[str, Callable[[Path], bool]]] = [
    ("a Write to a test file counts the pattern", write_to_test_file_counts_the_pattern),
    ("an Edit counts only the added lines", edit_counts_only_added_lines),
    ("an Edit of a file that is not a test counts nothing", edit_of_other_file_counts_nothing),
    ("a malformed line and a user or assistant event with no message are skipped", malformed_lines_are_skipped),
    ("a subagent transcript is read as its own session", subagent_transcript_is_read_as_its_own_session),
    ("an unreadable transcript is listed, and the rest are counted", unreadable_transcript_is_listed_and_the_rest_counted),
    ("a run records each session and no transcript text", run_records_each_session_and_no_text),
    ("months join every run, and the newest record of a session wins", months_join_every_run_and_newest_record_wins),
    ("a folder with no transcripts records nothing", empty_projects_records_nothing),
    ("a call pattern does not match a longer word", call_patterns_skip_longer_words),
    ("a JavaScript test file counts as a test file", javascript_test_files_count),
    ("a cut-short totals line does not swallow the next run", cut_short_totals_line_keeps_the_next_run),
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
