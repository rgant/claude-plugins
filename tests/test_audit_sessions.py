#!/usr/bin/env python3
"""Check the session audit against fake transcripts in a temporary folder.

Run: uv run --no-project --python ">=3.14" tests/test_audit_sessions.py
"""

import contextlib
import importlib.util
import io
import json
import os
import re
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
# A line that `--sessions` prints: a check name and a session ID.
SESSION_LINE = re.compile(r"^(?:tests|debugging|delegation) \S+$")


def tool_use(name: str, tool_input: dict[str, object]) -> str:
    """Return one transcript line for an assistant event with one tool call."""
    block = {"type": "tool_use", "name": name, "input": tool_input}
    return json.dumps({"type": "assistant", "timestamp": STAMP, "message": {"content": [block]}})


def tests_counts(lines: list[str]) -> dict[str, int]:
    return dict(audit_sessions.audit_session(lines, audit_sessions.CHECKS).counts["tests"])


def debugging_counts(lines: list[str]) -> dict[str, int]:
    return dict(audit_sessions.audit_session(lines, audit_sessions.CHECKS).counts["debugging"])


def delegation_counts(lines: list[str]) -> dict[str, int]:
    return dict(audit_sessions.audit_session(lines, audit_sessions.CHECKS).counts["delegation"])


def user_prompt(content: object, **extra: object) -> str:
    """Return one transcript line for a user event."""
    return json.dumps({"type": "user", "timestamp": STAMP, "message": {"content": content}, **extra})


def reply(text: str) -> str:
    """Return one transcript line for an assistant event with one text block."""
    return json.dumps({"type": "assistant", "timestamp": STAMP, "message": {"content": [{"type": "text", "text": text}]}})


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


def run_main(folder: Path, totals: Path, *flags: str) -> int:
    """Run the audit with *totals* as the totals file, then restore the earlier value of the variable."""
    earlier = os.environ.get("SESSION_AUDIT_TOTALS")
    os.environ["SESSION_AUDIT_TOTALS"] = str(totals)
    try:
        return audit_sessions.main(["--projects", str(folder / "projects"), *flags])
    finally:
        if earlier is None:
            del os.environ["SESSION_AUDIT_TOTALS"]
        else:
            os.environ["SESSION_AUDIT_TOTALS"] = earlier


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


def debugging_skill_run_counts(_folder: Path) -> bool:
    lines = [tool_use("Skill", {"skill": "superpowers:systematic-debugging"}), tool_use("Skill", {"skill": "writing:prose-gate"})]
    return debugging_counts(lines).get("debug_skill") == 1


def tool_call_that_names_a_guide_counts(_folder: Path) -> bool:
    lines = [
        tool_use("Read", {"file_path": "/clone/plugins/debugging/guides/debugging-core.md"}),
        tool_use("Read", {"file_path": "/clone/plugins/debugging/guides/debugging.md"}),
        tool_use("Read", {"file_path": "/home/.claude/plugins/cache/rgant/debugging/0.1.0/guides/debugging.md"}),
        tool_use("Write", {"file_path": "/clone/plugins/debugging/guides/debugging.md", "content": "x"}),
        tool_use("Read", {"file_path": "/app/docs/debugging.md"}),
        tool_use("Read", {"file_path": "guides/tests.md"}),
    ]
    return debugging_counts(lines).get("guide_read") == 3


def reply_with_hypothesis_table_counts(_folder: Path) -> bool:
    table = "Facts so far:\n\n| Hypothesis | Fact A |\n| --- | --- |\n| Cache | ✓ |\n"
    forms = ["| **Hypothesis** | A |", "| `Hypothesis` | A |", "| # | Hypothesis | A |", "| Hypotheses | A |"]
    lines = [reply(table), reply("The hypothesis is a cache. | not a table |"), *(reply(form) for form in forms)]
    return debugging_counts(lines).get("table") == 1 + len(forms)


def user_prompt_with_bug_word_counts(_folder: Path) -> bool:
    lines = [
        user_prompt("The export fails on a large file"),
        user_prompt([{"type": "text", "text": "Why is the total wrong?"}]),
        user_prompt("Add a button"),
        user_prompt("The import is broken", origin={"kind": "human"}),
        user_prompt("Check why the deploy failed", origin={"kind": "loop"}),
        user_prompt("<system-reminder>a test failed</system-reminder>Add a button"),
        user_prompt("Base directory for this skill: debug a failure", isMeta=True),
        user_prompt("The summary names a bug", isCompactSummary=True),
        user_prompt("Find why the job fails", isSidechain=True),
        user_prompt("<task-notification>Agent failed</task-notification>", origin={"kind": "task-notification"}),
        user_prompt("<local-command-stdout>error</local-command-stdout>"),
        user_prompt([{"type": "tool_result", "content": "error: failed"}]),
    ]
    return debugging_counts(lines).get("bug_words") == 3


def sessions_flag_lists_bug_words_with_no_table(folder: Path) -> bool:
    project = folder / "projects" / "project"
    project.mkdir(parents=True)
    (project / "untabled.jsonl").write_text(user_prompt("The job fails") + "\n", encoding="utf-8")
    tabled = [user_prompt("The job fails"), reply("| Hypothesis | Fact |\n| --- | --- |\n")]
    (project / "tabled.jsonl").write_text("\n".join(tabled) + "\n", encoding="utf-8")
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = run_main(folder, folder / "totals.jsonl", "--sessions")
    listed = [line for line in out.getvalue().splitlines() if SESSION_LINE.match(line)]
    return code == 0 and listed == ["debugging untabled"]


def agent_calls_count_as_fork_or_fresh(_folder: Path) -> bool:
    lines = [
        tool_use("Agent", {"subagent_type": "fork", "prompt": "Write the tests"}),
        tool_use("Agent", {"subagent_type": "general-purpose", "prompt": "Find the config"}),
        tool_use("Agent", {"prompt": "Find the config"}),
        tool_use("Read", {"file_path": "/clone/README.md"}),
    ]
    return delegation_counts(lines) == {"fork": 1, "fresh": 2}


def fresh_call_that_asks_for_judgment_counts(_folder: Path) -> bool:
    lines = [
        tool_use("Agent", {"subagent_type": "general-purpose", "prompt": "Plan the migration of the cache"}),
        tool_use("Agent", {"prompt": "Recommend one of the two designs"}),
        tool_use("Agent", {"subagent_type": "Plan", "prompt": "Plan the migration of the cache"}),
        tool_use("Agent", {"subagent_type": "fork", "prompt": "Plan the migration of the cache"}),
        tool_use("Agent", {"subagent_type": "general-purpose", "prompt": "Read the planet page"}),
        tool_use("Agent", {"prompt": "Implement task 3 of the plan. Design: docs/plans/cache-design.md"}),
        tool_use("Agent", {"subagent_type": "web-fetch", "prompt": "Report each recommendation of the article"}),
        tool_use("Agent", {"subagent_type": "Explore", "prompt": "Find the design docs"}),
        tool_use("Agent", {"subagent_type": "claude-code-guide", "prompt": "Recommend the setting for hooks"}),
    ]
    counts = delegation_counts(lines)
    return counts.get("fresh_judgment") == 2 and counts.get("plan_agent") == 1


def sessions_flag_lists_fresh_judgment_and_plan_agent_calls(folder: Path) -> bool:
    project = folder / "projects" / "project"
    project.mkdir(parents=True)
    planned = tool_use("Agent", {"prompt": "Design the retry"})
    (project / "planned.jsonl").write_text(planned + "\n", encoding="utf-8")
    plan_agent = tool_use("Agent", {"subagent_type": "Plan", "prompt": "Write plan A for the retry"})
    (project / "plan-agent.jsonl").write_text(plan_agent + "\n", encoding="utf-8")
    forked = tool_use("Agent", {"subagent_type": "fork", "prompt": "Design the retry"})
    (project / "forked.jsonl").write_text(forked + "\n", encoding="utf-8")
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = run_main(folder, folder / "totals.jsonl", "--sessions")
    listed = sorted(line for line in out.getvalue().splitlines() if SESSION_LINE.match(line))
    return code == 0 and listed == ["delegation plan-agent", "delegation planned"]


def write_fork(folder: Path, spawn_id: str, meta_text: str | None = None) -> None:
    """Write a fork transcript that copies its parent's history up to the call that started it.

    *meta_text* replaces the `meta.json` that Claude Code writes, for a subagent that is not a fork
    or a meta file that is broken.
    """
    agents = folder / "projects" / "project" / "session" / "subagents"
    agents.mkdir(parents=True)
    spawn = {"type": "tool_use", "id": "toolu_spawn", "name": "Agent", "input": {"subagent_type": "fork", "prompt": "Write it"}}
    lines = [
        tool_use("Agent", {"prompt": "Find the config"}),
        json.dumps({"type": "assistant", "timestamp": STAMP, "message": {"content": [spawn]}}),
        tool_use("Agent", {"prompt": "Read the page"}),
    ]
    (agents / "agent-fork.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    meta = {"agentType": "fork", "isFork": True, "toolUseId": spawn_id, "parentAgentId": "parent", "spawnDepth": 2}
    text = json.dumps(meta) if meta_text is None else meta_text
    (agents / "agent-fork.meta.json").write_text(text, encoding="utf-8")


def fork_delegation_counts(folder: Path, uncut: list[str] | None = None) -> dict[str, int]:
    results = dict(audit_sessions.audit_projects(folder / "projects", audit_sessions.CHECKS, [], uncut))
    return dict(results["session/agent-fork"].counts["delegation"])


def fork_skips_the_history_it_inherits(folder: Path) -> bool:
    write_fork(folder, "toolu_spawn")
    return fork_delegation_counts(folder) == {"fresh": 1}


def fork_with_no_spawn_call_counts_every_event_and_is_listed(folder: Path) -> bool:
    write_fork(folder, "toolu_missing")
    uncut: list[str] = []
    return fork_delegation_counts(folder, uncut) == {"fork": 1, "fresh": 2} and uncut == ["session/agent-fork"]


def subagent_that_is_not_a_fork_keeps_every_event(folder: Path) -> bool:
    write_fork(folder, "toolu_spawn", json.dumps({"agentType": "general-purpose", "isFork": False, "toolUseId": "toolu_spawn"}))
    return fork_delegation_counts(folder) == {"fork": 1, "fresh": 2}


def broken_meta_file_keeps_every_event(folder: Path) -> bool:
    write_fork(folder, "toolu_spawn", '{"isFork": true, "toolUseId": ')
    return fork_delegation_counts(folder) == {"fork": 1, "fresh": 2}


def report_of_keyless_check_has_only_month_sessions_skipped(_folder: Path) -> bool:
    months = {"2026-11": audit_sessions.MonthTotals(sessions=1)}
    lines = audit_sessions.report(months, ["delegation"]).splitlines()
    rows = [line for line in lines if line.startswith("|")]
    return rows == ["| Month | Sessions | Skipped |", "| --- | --- | --- |", "| 2026-11 | 1 | 0 |"]


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
    ("a run of systematic-debugging counts", debugging_skill_run_counts),
    ("a Read of a debugging guide counts, and a write or another file does not", tool_call_that_names_a_guide_counts),
    ("a reply with a Hypothesis table counts, in each common form", reply_with_hypothesis_table_counts),
    ("a user prompt with a bug word counts, and a subagent brief or other user event does not", user_prompt_with_bug_word_counts),
    ("--sessions lists a session with bug words and no table", sessions_flag_lists_bug_words_with_no_table),
    ("an Agent call counts as a fork or a fresh subagent, and another tool does not", agent_calls_count_as_fork_or_fresh),
    ("a fresh judgment call counts, a Plan call counts apart, a fork or reader does not", fresh_call_that_asks_for_judgment_counts),
    ("--sessions lists a session with a fresh judgment call or a Plan agent call", sessions_flag_lists_fresh_judgment_and_plan_agent_calls),
    ("a fork transcript skips the history it copies from its parent", fork_skips_the_history_it_inherits),
    ("a fork transcript with no spawn call counts every event and is listed", fork_with_no_spawn_call_counts_every_event_and_is_listed),
    ("a subagent that is not a fork keeps every event", subagent_that_is_not_a_fork_keeps_every_event),
    ("a broken meta file keeps every event", broken_meta_file_keeps_every_event),
    ("the report of a check with no keys has only Month, Sessions and Skipped", report_of_keyless_check_has_only_month_sessions_skipped),
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
