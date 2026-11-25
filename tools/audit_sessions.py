#!/usr/bin/env python3
"""Count, for each month, how Claude's sessions follow the guides that the shared CLAUDE.md loads.

Rob runs this by hand, and a SessionStart hook runs `audit_reminder.py` to remind him when a run is
due. The audit reads each transcript under `~/.claude/projects`, one line at a time. A subagent
transcript counts as its own session, because a subagent loads the same CLAUDE.md and its edits do
not appear in the parent transcript.

Each entry in `CHECKS` counts things in one transcript event. The `tests` check counts the added
lines of a test-file edit that hold a pattern which `plugins/writing/guides/tests.md` warns about.
A mock of a third-party SDK is correct, so a count is a reason to read the session, not a fault.

Transcripts hold client text. So the audit prints to the terminal, and it writes counts only to
the totals file, never text from a transcript. Claude Code deletes a transcript after about 30
days, so one run sees only part of a month. Each run appends the counts of every session it can
read, keyed by session ID. The report rebuilds each month from the union of all runs, and the
newest record of a session wins, so no session counts twice. The environment variable
`SESSION_AUDIT_TOTALS` names another totals file, which the tests use.

A line that is not JSON, and a user or assistant event with no `message`, add 1 to the skipped
count and stop nothing. Only user and assistant events need a `message`, so the audit checks only
those. A transcript that cannot be opened is listed, and the run goes on.
"""

import argparse
import json
import os
import re
import sys
from collections import Counter
from collections.abc import Callable, Iterable, Iterator, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

DEFAULT_PROJECTS = Path.home() / ".claude" / "projects"
DEFAULT_TOTALS = Path.home() / ".claude" / "session-audit" / "totals.jsonl"
TOTALS_VARIABLE = "SESSION_AUDIT_TOTALS"

TEST_FILE = re.compile(r"^(?:test_.*\.py|.*_test\.py|conftest\.py|.*\.(?:test|spec)\.(?:tsx?|jsx?|mjs))$")
# Each name is the key in the report. A call pattern must not follow a word character, so `patch(`
# does not match `dispatch(`, and `cast(` does not match `broadcast(`.
TEST_PATTERNS = {
    "MagicMock": re.compile(r"MagicMock"),
    "patch(": re.compile(r"(?<!\w)patch\("),
    "vi.mock": re.compile(r"\bvi\.mock\b"),
    "cast(": re.compile(r"(?<!\w)cast\("),
    "type: ignore": re.compile(r"type:\s*ignore"),
    "noqa": re.compile(r"\bnoqa\b"),
    "as unknown as": re.compile(r"\bas unknown as\b"),
}

type Event = dict[str, object]
type Check = Callable[[Event], Counter[str]]


@dataclass(frozen=True)
class SessionResult:
    started: str
    skipped: int
    counts: dict[str, Counter[str]] = field(default_factory=dict)

    @property
    def month(self) -> str:
        return self.started[:7] or "unknown"


@dataclass
class KeyTotal:
    sessions: int = 0
    count: int = 0


@dataclass
class MonthTotals:
    sessions: int = 0
    skipped: int = 0
    checks: dict[str, dict[str, KeyTotal]] = field(default_factory=dict)


def tool_uses(event: Event) -> Iterator[tuple[str, dict[str, object]]]:
    """Yield the name and input of each tool call in an assistant event."""
    if event.get("type") != "assistant":
        return
    message = event.get("message")
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, list):
        return
    for block in content:
        if isinstance(block, dict) and block.get("type") == "tool_use":
            name, tool_input = block.get("name"), block.get("input")
            if isinstance(name, str) and isinstance(tool_input, dict):
                yield name, tool_input


def added_lines(name: str, tool_input: dict[str, object]) -> list[str]:
    """Return the lines that a Write, Edit or MultiEdit call adds.

    The transcript does not hold the file that a Write replaces, so every line of a Write counts as
    added. A count from a Write is an upper bound.
    """
    if name == "Write":
        content = tool_input.get("content")
        return content.splitlines() if isinstance(content, str) else []
    pairs: list[object] = [tool_input] if name == "Edit" else []
    if name == "MultiEdit" and isinstance(tool_input.get("edits"), list):
        pairs = tool_input["edits"]
    lines: list[str] = []
    for pair in pairs:
        if not isinstance(pair, dict):
            continue
        old, new = pair.get("old_string"), pair.get("new_string")
        if isinstance(new, str):
            before = set(old.splitlines()) if isinstance(old, str) else set()
            lines.extend(line for line in new.splitlines() if line not in before)
    return lines


def tests_check(event: Event) -> Counter[str]:
    """Count test-file edits, and their added lines that hold a pattern from `TEST_PATTERNS`."""
    counts: Counter[str] = Counter()
    for name, tool_input in tool_uses(event):
        path = tool_input.get("file_path")
        if name not in {"Write", "Edit", "MultiEdit"} or not isinstance(path, str):
            continue
        if not TEST_FILE.match(Path(path).name):
            continue
        counts["edited"] += 1
        for line in added_lines(name, tool_input):
            hits = [name for name, pattern in TEST_PATTERNS.items() if pattern.search(line)]
            counts.update(hits)
            counts["flagged"] += bool(hits)
    return counts


CHECKS: dict[str, Check] = {"tests": tests_check}


def audit_session(lines: Iterable[str], checks: Mapping[str, Check]) -> SessionResult:
    """Run each check over each event of one transcript."""
    started = ""
    skipped = 0
    counts: dict[str, Counter[str]] = {name: Counter() for name in checks}
    for line in lines:
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            skipped += 1
            continue
        if not isinstance(event, dict):
            skipped += 1
            continue
        if event.get("type") in {"user", "assistant"} and "message" not in event:
            skipped += 1
            continue
        stamp = event.get("timestamp")
        if not started and isinstance(stamp, str):
            started = stamp
        for name, check in checks.items():
            counts[name].update(check(event))
    return SessionResult(started=started, skipped=skipped, counts=counts)


def transcripts(projects: Path) -> Iterator[tuple[str, Path]]:
    """Yield the session ID and path of each transcript. A subagent's ID is `<session>/<agent>`."""
    for path in sorted(projects.glob("*/*.jsonl")):
        yield path.stem, path
    for path in sorted(projects.glob("*/*/subagents/*.jsonl")):
        yield f"{path.parent.parent.name}/{path.stem}", path


def audit_projects(projects: Path, checks: Mapping[str, Check], unreadable: list[str]) -> Iterator[tuple[str, SessionResult]]:
    """Audit each transcript under *projects*, one line at a time. Add the ID of each file that cannot be read to *unreadable*."""
    for session_id, path in transcripts(projects):
        try:
            with path.open(encoding="utf-8", errors="replace") as handle:
                result = audit_session(handle, checks)
        except OSError:
            unreadable.append(session_id)
            continue
        yield session_id, result


def record(sessions: Mapping[str, SessionResult], totals: Path) -> None:
    """Append one line with the counts of each session to *totals*. The line holds no text from a transcript."""
    totals.parent.mkdir(parents=True, exist_ok=True)
    entries = {
        session_id: {
            "month": result.month,
            "skipped": result.skipped,
            "counts": {name: dict(counts) for name, counts in result.counts.items()},
        }
        for session_id, result in sessions.items()
    }
    with totals.open("a+", encoding="utf-8") as handle:
        # An interrupted run can leave a last line with no newline. Without this newline, the new
        # line would join the broken one, and the reader would drop both.
        if handle.tell() > 0:
            handle.seek(handle.tell() - 1)
            if handle.read(1) != "\n":
                handle.write("\n")
        handle.write(json.dumps({"run": datetime.now(UTC).isoformat(), "sessions": entries}) + "\n")


def recorded_sessions(totals: Path) -> dict[str, SessionResult]:
    """Read every run in *totals*. A later record of a session replaces an earlier one. A damaged line is ignored."""
    sessions: dict[str, SessionResult] = {}
    if not totals.is_file():
        return sessions
    with totals.open(encoding="utf-8") as handle:
        for line in handle:
            try:
                entries = json.loads(line)["sessions"]
                for session_id, entry in entries.items():
                    counts = {name: Counter(values) for name, values in entry["counts"].items()}
                    sessions[session_id] = SessionResult(started=entry["month"], skipped=entry["skipped"], counts=counts)
            except ValueError, KeyError, TypeError, AttributeError:
                continue
    return sessions


def monthly(results: Iterable[SessionResult]) -> dict[str, MonthTotals]:
    """Sum the sessions for each month. For each key of a check, count the sessions above 0 and the sum."""
    months: dict[str, MonthTotals] = {}
    for result in results:
        month = months.setdefault(result.month, MonthTotals())
        month.sessions += 1
        month.skipped += result.skipped
        for name, counts in result.counts.items():
            check = month.checks.setdefault(name, {})
            for key, value in counts.items():
                total = check.setdefault(key, KeyTotal())
                total.sessions += value > 0
                total.count += value
    return dict(sorted(months.items()))


def report(months: Mapping[str, MonthTotals], checks: Iterable[str]) -> str:
    """Return one Markdown table for each check. A cell holds the sessions, then the count."""
    out: list[str] = []
    for name in checks:
        keys = sorted({key for month in months.values() for key in month.checks.get(name, {})})
        out.append(f"## {name}\n\nEach cell is sessions / count.\n")
        out.append("| Month | Sessions | Skipped | " + " | ".join(f"`{key}`" for key in keys) + " |")
        out.append("|" + " --- |" * (len(keys) + 3))
        for month_name, month in months.items():
            check = month.checks.get(name, {})
            cells = [f"{check[key].sessions} / {check[key].count}" if key in check else "0 / 0" for key in keys]
            out.append(f"| {month_name} | {month.sessions} | {month.skipped} | " + " | ".join(cells) + " |")
        out.append("")
    return "\n".join(out)


def totals_path() -> Path:
    named = os.environ.get(TOTALS_VARIABLE)
    return Path(named) if named else DEFAULT_TOTALS


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--projects", type=Path, default=DEFAULT_PROJECTS, help="the folder of transcripts")
    parser.add_argument("--sessions", action="store_true", help="also print the ID of each session with a flagged line")
    args = parser.parse_args(argv)
    unreadable: list[str] = []
    current = dict(audit_projects(args.projects, CHECKS, unreadable))
    if not current:
        print(f"No transcript found under {args.projects}. Nothing was recorded.", file=sys.stderr)
        return 1
    if args.sessions:
        for session_id, result in current.items():
            if any(counts["flagged"] for counts in result.counts.values()):
                print(session_id)
    totals = totals_path()
    record(current, totals)
    print(report(monthly(recorded_sessions(totals).values()), CHECKS))
    for session_id in unreadable:
        print(f"Could not read the transcript of session {session_id}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
