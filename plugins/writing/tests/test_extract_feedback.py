#!/usr/bin/env python3
"""Regression harness for extract_feedback.py of the reviewing-edit-feedback skill.

Each case writes synthetic transcripts to a temporary directory. No real transcript enters the
repository.
"""

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "skills" / "reviewing-edit-feedback"))
import extract_feedback  # noqa: E402
from extract_feedback import PASTE_BACK  # noqa: E402
from feedback_store import Store  # noqa: E402


class Session:
    """Build the records of one synthetic session."""

    def __init__(self, folder: Path, session: str = "s1", day: str = "2026-11-01") -> None:
        self.folder = folder
        self.session = session
        self.day = day
        self.lines: list[dict[str, object]] = []

    def _base(self, kind: str) -> dict[str, object]:
        number = len(self.lines)
        return {
            "type": kind,
            "sessionId": self.session,
            "uuid": f"{self.session}-u{number}",
            "timestamp": f"{self.day}T10:{number:02d}:00Z",
            "cwd": str(self.folder / "repo"),
        }

    def user(self, text: str, **extra: object) -> Session:
        self.lines.append({**self._base("user"), "message": {"role": "user", "content": text}, **extra})
        return self

    def assistant(self, text: str) -> Session:
        content = [{"type": "text", "text": text}]
        self.lines.append({**self._base("assistant"), "message": {"role": "assistant", "content": content}})
        return self

    def tool(self, name: str, tool_input: dict[str, object], result: str, *, error: bool = False) -> Session:
        """Add a tool call and its result, linked by the call ID."""
        call_id = f"call{len(self.lines)}"
        call = {"type": "tool_use", "id": call_id, "name": name, "input": tool_input}
        self.lines.append({**self._base("assistant"), "message": {"role": "assistant", "content": [call]}})
        block: dict[str, object] = {"type": "tool_result", "tool_use_id": call_id, "content": result}
        if error:
            block["is_error"] = True
        self.lines.append({**self._base("user"), "message": {"role": "user", "content": [block]}})
        return self

    def bash(self, command: str, result: str, *, error: bool = False) -> Session:
        return self.tool("Bash", {"command": command, "description": "x"}, result, error=error)

    def raw(self, line: str) -> Session:
        self.lines.append({"raw": line})
        return self

    def write(self, path: Path | None = None) -> Path:
        target = path or self.folder / "projects" / "proj" / f"{self.session}.jsonl"
        target.parent.mkdir(parents=True, exist_ok=True)
        text = "".join((str(line["raw"]) if "raw" in line else json.dumps(line)) + "\n" for line in self.lines)
        target.write_text(text, encoding="utf-8")
        return target


def run(folder: Path, *args: str) -> tuple[int, str]:
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = extract_feedback.main(["--projects", str(folder / "projects"), "--store", str(folder / "store"), *args])
    return code, out.getvalue()


def records(folder: Path) -> list[extract_feedback.Record]:
    return Store(folder / "store").records()


def pair_from_a_pasted_final(folder: Path) -> bool:
    Session(folder).assistant(f"First draft.\n\n{PASTE_BACK}").user("Make it shorter.").assistant(f"Short draft.\n\n{PASTE_BACK}").user(
        "SENT> Short sent text."
    ).write()
    run(folder, "extract")
    found = records(folder)
    return (
        len(found) == 1
        and found[0].draft == "Short draft."
        and found[0].final == "Short sent text."
        and found[0].requests == ["Make it shorter."]
        and found[0].kind == "message"
    )


def unrelated_reply_between(folder: Path) -> bool:
    Session(folder).assistant(f"Marked draft.\n\n{PASTE_BACK}").user("Unrelated question?").assistant("Unrelated answer.").user(
        "SENT> Sent text."
    ).write()
    run(folder, "extract")
    found = records(folder)
    return len(found) == 1 and found[0].draft == "Marked draft."


def final_inside_a_paste_wrapper(folder: Path) -> bool:
    Session(folder).assistant(f"Draft.\n\n{PASTE_BACK}").user(
        '<pasted_content id="ab12">\nSENT> Sent text.\n</pasted_content id="ab12">'
    ).write()
    run(folder, "extract")
    found = records(folder)
    return len(found) == 1 and found[0].final == "Sent text."


def talk_about_the_prefix_is_not_a_final(folder: Path) -> bool:
    Session(folder).assistant(f"Draft.\n\n{PASTE_BACK}").user("Good idea. Use SENT> as the prefix.").write()
    run(folder, "extract")
    return records(folder) == []


def final_with_no_marked_draft(folder: Path) -> bool:
    Session(folder).assistant("Unmarked reply.").user("SENT> Sent text.").write()
    run(folder, "extract")
    return records(folder) == []


def unchanged_final(folder: Path) -> bool:
    Session(folder).assistant(f"Same   text.\n\n{PASTE_BACK}").user("SENT> Same text.").write()
    run(folder, "extract")
    return records(folder) == []


def meta_record_is_not_a_request(folder: Path) -> bool:
    Session(folder).assistant(f"Draft.\n\n{PASTE_BACK}").user("Caveat text.", isMeta=True).user("SENT> Sent text.").write()
    run(folder, "extract")
    found = records(folder)
    return len(found) == 1 and found[0].requests == []


def unknown_record_type(folder: Path) -> bool:
    session = Session(folder).assistant(f"Draft.\n\n{PASTE_BACK}").raw('{"type": "mode", "mode": "x"}').raw("not json")
    session.user("SENT> Sent text.").write()
    code, _ = run(folder, "extract")
    return code == 0 and len(records(folder)) == 1


def subagent_transcript_skipped(folder: Path) -> bool:
    session = Session(folder).assistant(f"Draft.\n\n{PASTE_BACK}").user("SENT> Sent text.")
    session.write(folder / "projects" / "proj" / "s1" / "subagents" / "agent-a.jsonl")
    run(folder, "extract")
    return records(folder) == []


def unreadable_file(folder: Path) -> bool:
    path = Session(folder).assistant("Reply.").write()
    path.chmod(0)
    try:
        code, out = run(folder, "extract")
    finally:
        path.chmod(0o600)
    return code == 0 and str(path) in out


def second_run_adds_nothing(folder: Path) -> bool:
    Session(folder).assistant(f"Draft.\n\n{PASTE_BACK}").user("SENT> Sent text.").write()
    _, first = run(folder, "extract")
    _, second = run(folder, "extract")
    return "added 1" in first and "added 0" in second


def pending_lists_unclassified(folder: Path) -> bool:
    Session(folder).assistant(f"Draft.\n\n{PASTE_BACK}").user("SENT> Sent text.").write()
    run(folder, "extract")
    _, out = run(folder, "pending")
    lines = [json.loads(line) for line in out.splitlines()]
    return len(lines) == 1 and lines[0]["final"] == "Sent text."


def classify_then_labels(folder: Path) -> bool:
    session = Session(folder).assistant(f"One.\n\n{PASTE_BACK}").user("SENT> One sent.")
    session.assistant(f"Two.\n\n{PASTE_BACK}").user("SENT> Two sent.").write()
    run(folder, "extract")
    for record in records(folder):
        run(folder, "classify", record.id, "wrong-rule", "drop-hedges")
    _, out = run(folder, "labels")
    return "drop-hedges" in out and "wrong-rule 2" in out


def done_writes_the_state(folder: Path) -> bool:
    run(folder, "done")
    state = json.loads((folder / "store" / "state.json").read_text(encoding="utf-8"))
    return bool(state.get("last_review"))


def done_refuses_while_pending(folder: Path) -> bool:
    Session(folder).assistant(f"Draft.\n\n{PASTE_BACK}").user("SENT> Sent text.").write()
    run(folder, "extract")
    code, out = run(folder, "done")
    return code == 1 and "pending" in out and not (folder / "store" / "state.json").exists()


def projects_dir_follows_config(folder: Path) -> bool:
    saved = os.environ.get("CLAUDE_CONFIG_DIR")
    os.environ["CLAUDE_CONFIG_DIR"] = str(folder / "config")
    try:
        return extract_feedback.projects_dir() == folder / "config" / "projects"
    finally:
        if saved is None:
            os.environ.pop("CLAUDE_CONFIG_DIR")
        else:
            os.environ["CLAUDE_CONFIG_DIR"] = saved


PR_URL = "https://github.com/o/r/pull/7"
TICKET_TOOL = {
    "name": "tickets",
    "command": r"tickets\.py (?:create|edit)\b",
    "body_flag": "--description-file",
    "key_in_command": r"edit (PROJ-\d+)",
    "key_in_result": r"created (PROJ-\d+)",
    "view": ["./tickets.py", "view", "{key}"],
    "field": "fields.description",
}


def pr_create(body: str) -> str:
    return f"gh pr create --title t --body \"$(cat <<'EOF'\n{body}\nEOF\n)\""


def write_tickets(folder: Path) -> None:
    (folder / "store").mkdir(parents=True, exist_ok=True)
    (folder / "store" / "tickets.json").write_text(json.dumps([TICKET_TOOL]), encoding="utf-8")


def pr_create_pair(folder: Path) -> bool:
    Session(folder).bash(pr_create("The parser reads the manifest first."), f"{PR_URL}\n").write()
    run(folder, "extract")
    found = records(folder)
    return (
        len(found) == 1
        and found[0].kind == "pr"
        and found[0].target == PR_URL
        and found[0].draft == "The parser reads the manifest first."
        and found[0].final == ""
    )


def body_file_from_an_earlier_write(folder: Path) -> bool:
    body = folder / "body.md"
    session = Session(folder).tool("Write", {"file_path": str(body), "content": "Written body."}, "ok")
    session.bash(f"gh pr create --title t --body-file {body}", f"{PR_URL}\n").write()
    run(folder, "extract")
    found = records(folder)
    return len(found) == 1 and found[0].draft == "Written body."


def body_file_with_no_write(folder: Path) -> bool:
    Session(folder).bash(f"gh pr create --title t --body-file {folder / 'gone.md'}", f"{PR_URL}\n").write()
    _, out = run(folder, "extract")
    return records(folder) == [] and "gone.md" in out


def body_file_through_a_shell_variable(folder: Path) -> bool:
    body = folder / "body.md"
    session = Session(folder).tool("Write", {"file_path": str(body), "content": "Written body."}, "ok")
    session.bash(f"D={folder}; gh pr create --title t --body-file $D/body.md", f"{PR_URL}\n").write()
    run(folder, "extract")
    found = records(folder)
    return len(found) == 1 and found[0].draft == "Written body."


def label_edit_is_not_a_draft(folder: Path) -> bool:
    Session(folder).bash("gh pr edit 7 --add-label bug", f"{PR_URL}\n").write()
    _, out = run(folder, "extract")
    return records(folder) == [] and "skipped" not in out


def denied_call_skipped(folder: Path) -> bool:
    Session(folder).bash(pr_create("Body."), "STE check denied the body.", error=True).write()
    run(folder, "extract")
    return records(folder) == []


def comment_skipped(folder: Path) -> bool:
    Session(folder).bash('gh pr comment 7 --body "A comment."', f"{PR_URL}#issuecomment-1\n").write()
    run(folder, "extract")
    return records(folder) == []


def first_draft_wins(folder: Path) -> bool:
    session = Session(folder).bash(pr_create("First body."), f"{PR_URL}\n").user("Name the parser.")
    session.bash("gh pr edit 7 --body \"$(cat <<'EOF'\nSecond body.\nEOF\n)\"", f"{PR_URL}\n").write()
    run(folder, "extract")
    found = records(folder)
    return len(found) == 1 and found[0].draft == "First body." and found[0].requests == ["Name the parser."]


def ticket_create_pair(folder: Path) -> bool:
    write_tickets(folder)
    body = folder / "ticket.md"
    session = Session(folder).tool("Write", {"file_path": str(body), "content": "Ticket body."}, "ok")
    session.bash(f"./tickets.py create --summary s --description-file {body}", "created PROJ-1\n").write()
    run(folder, "extract")
    found = records(folder)
    return len(found) == 1 and found[0].kind == "ticket" and found[0].target == "PROJ-1" and found[0].tool == "tickets"


def ticket_edit_with_no_description(folder: Path) -> bool:
    write_tickets(folder)
    Session(folder).bash("./tickets.py edit PROJ-1 --parent PROJ-2", "ok\n").write()
    _, out = run(folder, "extract")
    return records(folder) == [] and "skipped" not in out


def no_ticket_tools(folder: Path) -> bool:
    body = folder / "ticket.md"
    session = Session(folder).tool("Write", {"file_path": str(body), "content": "Ticket body."}, "ok")
    session.bash(f"./tickets.py create --summary s --description-file {body}", "created PROJ-1\n").write()
    run(folder, "extract")
    return records(folder) == []


def fetch(folder: Path, output: str | Exception, now: datetime) -> list[str]:
    def runner(command: list[str], cwd: str | None) -> str:
        if isinstance(output, Exception):
            raise output
        return output

    store = Store(folder / "store")
    return extract_feedback.fetch_finals(store, extract_feedback.load_ticket_tools(folder / "store"), runner, now)


NOW = datetime(2026, 11, 3, tzinfo=UTC)


def open_pr_waits(folder: Path) -> bool:
    Session(folder).bash(pr_create("Body."), f"{PR_URL}\n").write()
    run(folder, "extract")
    fetch(folder, json.dumps({"body": "Edited body.", "state": "OPEN"}), NOW)
    return records(folder)[0].final == ""


def merged_pr_fills(folder: Path) -> bool:
    Session(folder).bash(pr_create("Body."), f"{PR_URL}\n").write()
    run(folder, "extract")
    fetch(folder, json.dumps({"body": "Edited body.", "state": "MERGED"}), NOW)
    return records(folder)[0].final == "Edited body."


def young_ticket_waits(folder: Path) -> bool:
    write_tickets(folder)
    body = folder / "ticket.md"
    session = Session(folder).tool("Write", {"file_path": str(body), "content": "Ticket body."}, "ok")
    session.bash(f"./tickets.py create --summary s --description-file {body}", "created PROJ-1\n").write()
    (folder / "repo").mkdir()
    run(folder, "extract")
    adf = {"type": "doc", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Edited ticket."}]}]}
    view = json.dumps({"fields": {"description": adf}})
    fetch(folder, view, NOW)
    young = records(folder)[0].final
    fetch(folder, view, datetime(2026, 11, 9, tzinfo=UTC))
    return young == "" and records(folder)[0].final == "Edited ticket."


def fetch_failure(folder: Path) -> bool:
    Session(folder).bash(pr_create("Body."), f"{PR_URL}\n").write()
    run(folder, "extract")
    lines = fetch(folder, subprocess.CalledProcessError(1, ["gh"]), NOW)
    return len(lines) == 1 and records(folder)[0].final == ""


TICKET_MARKDOWN = (
    "## Scope\n\nThe **parser** reads `manifest.json` first, through `__init__`.\n\n- One step.\n- Two steps.\n\n```sh\nmake test\n```\n"
)


def adf_text(text: str) -> dict[str, object]:
    return {"type": "text", "text": text}


def adf_paragraph(*runs: dict[str, object]) -> dict[str, object]:
    return {"type": "paragraph", "content": list(runs)}


TICKET_ADF = {
    "type": "doc",
    "content": [
        {"type": "heading", "attrs": {"level": 2}, "content": [adf_text("Scope")]},
        adf_paragraph(
            adf_text("The "),
            {"type": "text", "text": "parser", "marks": [{"type": "strong"}]},
            adf_text(" reads "),
            {"type": "text", "text": "manifest.json", "marks": [{"type": "code"}]},
            adf_text(" first, through "),
            {"type": "text", "text": "__init__", "marks": [{"type": "code"}]},
            adf_text("."),
        ),
        {
            "type": "bulletList",
            "content": [
                {"type": "listItem", "content": [adf_paragraph(adf_text("One step."))]},
                {"type": "listItem", "content": [adf_paragraph(adf_text("Two steps."))]},
            ],
        },
        {"type": "codeBlock", "attrs": {"language": "sh"}, "content": [adf_text("make test")]},
    ],
}


def unchanged_ticket_is_not_pending(folder: Path) -> bool:
    write_tickets(folder)
    body = folder / "ticket.md"
    session = Session(folder).tool("Write", {"file_path": str(body), "content": TICKET_MARKDOWN}, "ok")
    session.bash(f"./tickets.py create --summary s --description-file {body}", "created PROJ-1\n").write()
    (folder / "repo").mkdir()
    run(folder, "extract")
    fetch(folder, json.dumps({"fields": {"description": TICKET_ADF}}), datetime(2026, 11, 9, tzinfo=UTC))
    _, out = run(folder, "pending")
    return records(folder)[0].final != "" and out.strip() == ""


def body_file_edited_after_a_denied_call(folder: Path) -> bool:
    body = folder / "body.md"
    session = Session(folder).tool("Write", {"file_path": str(body), "content": "Robust body."}, "ok")
    session.bash(f"gh pr create --title t --body-file {body}", "STE check denied the body.", error=True)
    edit = {"file_path": str(body), "old_string": "Robust body.", "new_string": "Plain body.", "replace_all": False}
    session.tool("Edit", edit, "ok")
    session.bash(f"gh pr create --title t --body-file {body}", f"{PR_URL}\n").write()
    run(folder, "extract")
    found = records(folder)
    return len(found) == 1 and found[0].draft == "Plain body."


def first_draft_by_time_across_transcripts(folder: Path) -> bool:
    edit = "gh pr edit 7 --body \"$(cat <<'EOF'\nSecond body.\nEOF\n)\""
    Session(folder, "a-later", day="2026-11-05").bash(edit, f"{PR_URL}\n").write()
    Session(folder, "b-earlier", day="2026-11-01").bash(pr_create("First body."), f"{PR_URL}\n").write()
    run(folder, "extract")
    found = records(folder)
    return len(found) == 1 and found[0].draft == "First body."


def torn_last_line_is_skipped(folder: Path) -> bool:
    Session(folder).assistant(f"Draft.\n\n{PASTE_BACK}").user("SENT> Sent text.").write()
    (folder / "store").mkdir(parents=True)
    (folder / "store" / "records.jsonl").write_text('{"id": "torn', encoding="utf-8")
    code, _ = run(folder, "extract")
    pending_code, out = run(folder, "pending")
    return code == 0 and pending_code == 0 and len(out.splitlines()) == 1


def harness_records_are_not_requests(folder: Path) -> bool:
    session = Session(folder).bash(pr_create("First body."), f"{PR_URL}\n")
    session.user("Summary of the earlier conversation.", isCompactSummary=True)
    session.user("<command-name>/compact</command-name>")
    session.user("<local-command-stdout>done</local-command-stdout>")
    session.user("<system-reminder>note</system-reminder>")
    session.user("<task-notification>done</task-notification>")
    session.user("Name the parser.")
    session.bash("gh pr edit 7 --body \"$(cat <<'EOF'\nSecond body.\nEOF\n)\"", f"{PR_URL}\n").write()
    run(folder, "extract")
    return records(folder)[0].requests == ["Name the parser."]


def invalid_utf8_transcript_is_reported(folder: Path) -> bool:
    Session(folder).assistant(f"Draft.\n\n{PASTE_BACK}").user("SENT> Sent text.").write()
    bad = folder / "projects" / "proj" / "a-bad.jsonl"
    bad.write_bytes(b"\xff\xfe not text\n")
    code, out = run(folder, "extract")
    return code == 0 and str(bad) in out and len(records(folder)) == 1


def quoted_paste_back_is_not_a_draft(folder: Path) -> bool:
    Session(folder).assistant(f"The reminder line reads: {PASTE_BACK} It marks the draft.").user("SENT> Sent text.").write()
    run(folder, "extract")
    return records(folder) == []


def paste_back_with_emphasis_marks_the_draft(folder: Path) -> bool:
    Session(folder).assistant(f"Draft.\n\n*{PASTE_BACK}*\n").user("SENT> Sent text.").write()
    run(folder, "extract")
    found = records(folder)
    return len(found) == 1 and found[0].draft == "Draft."


def short_flag_inside_an_option_value(folder: Path) -> bool:
    command = 'gh pr create --head my-b "x" --title t --body "Real body."'
    Session(folder).bash(command, f"{PR_URL}\n").write()
    run(folder, "extract")
    found = records(folder)
    return len(found) == 1 and found[0].draft == "Real body."


CASES: list[tuple[str, Callable[[Path], bool]]] = [
    ("invalid utf-8 transcript is reported", invalid_utf8_transcript_is_reported),
    ("quoted paste-back is not a draft", quoted_paste_back_is_not_a_draft),
    ("paste-back with emphasis marks the draft", paste_back_with_emphasis_marks_the_draft),
    ("short flag inside an option value", short_flag_inside_an_option_value),
    ("unchanged ticket is not pending", unchanged_ticket_is_not_pending),
    ("body file edited after a denied call", body_file_edited_after_a_denied_call),
    ("first draft by time across transcripts", first_draft_by_time_across_transcripts),
    ("torn last line is skipped", torn_last_line_is_skipped),
    ("harness records are not requests", harness_records_are_not_requests),
    ("pr create pair", pr_create_pair),
    ("body file from an earlier write", body_file_from_an_earlier_write),
    ("body file with no write", body_file_with_no_write),
    ("body file through a shell variable", body_file_through_a_shell_variable),
    ("label edit is not a draft", label_edit_is_not_a_draft),
    ("denied call skipped", denied_call_skipped),
    ("comment skipped", comment_skipped),
    ("first draft wins", first_draft_wins),
    ("ticket create pair", ticket_create_pair),
    ("ticket edit with no description", ticket_edit_with_no_description),
    ("no ticket tools", no_ticket_tools),
    ("open pr waits", open_pr_waits),
    ("merged pr fills", merged_pr_fills),
    ("young ticket waits", young_ticket_waits),
    ("fetch failure", fetch_failure),
    ("pair from a pasted final", pair_from_a_pasted_final),
    ("unrelated reply between", unrelated_reply_between),
    ("final inside a paste wrapper", final_inside_a_paste_wrapper),
    ("talk about the prefix is not a final", talk_about_the_prefix_is_not_a_final),
    ("final with no marked draft", final_with_no_marked_draft),
    ("unchanged final", unchanged_final),
    ("meta record is not a request", meta_record_is_not_a_request),
    ("unknown record type", unknown_record_type),
    ("subagent transcript skipped", subagent_transcript_skipped),
    ("unreadable file", unreadable_file),
    ("second run adds nothing", second_run_adds_nothing),
    ("pending lists unclassified", pending_lists_unclassified),
    ("classify then labels", classify_then_labels),
    ("done writes the state", done_writes_the_state),
    ("done refuses while pending", done_refuses_while_pending),
    ("projects dir follows config", projects_dir_follows_config),
]


def main() -> None:
    failures = 0
    for name, case in CASES:
        with tempfile.TemporaryDirectory() as folder:
            try:
                ok = case(Path(folder))
            except Exception as error:  # noqa: BLE001 - a crash in one case is a failure of that case
                print(f"     {type(error).__name__}: {error}")
                ok = False
        print(f"{'ok ' if ok else 'FAIL'} {name}")
        failures += not ok
    print("ALL PASS" if not failures else f"FAILURES: {failures}")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
