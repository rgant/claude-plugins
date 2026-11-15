#!/usr/bin/env python3
"""Read the Claude Code transcripts, and keep each draft that Claude wrote with the text the user sent.

The transcript format is internal to Claude Code, and a release can change it without notice. So
this script skips each record type that it does not know, and it reports a file that it cannot
read instead of failing the run.

Run: extract_feedback.py [--projects DIR] [--store DIR] {extract,pending,classify,labels,done}
"""

import argparse
import json
import os
import re
import subprocess
import sys
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "lib"))
from bodies import BODY_FILE, BODY_FLAG, HEREDOC, decode_jira, heredoc_bodies, prepare, unquote  # noqa: E402
from feedback_store import Record, Store, same_text  # noqa: E402

__all__ = ["PASTE_BACK", "Record", "main"]

# The request line that ends a draft of a Slack or Teams message. The reminder hook of the writing
# plugin tells Claude to write this exact line, so the line also marks the draft in the transcript.
PASTE_BACK = "Paste the sent version after SENT> so the writing review can learn."
SENT = "SENT>"
PASTE_TAG = re.compile(r"</?pasted_content\b[^>]*>")
# A PR or issue description. A comment and a review are messages, and they are out of scope.
PR_WRITE = re.compile(r"\bgh\s+(?:pr|issue)\s+(?:create|edit)\b")
PR_URL = re.compile(r"https://github\.com/[^\s/]+/[^\s/]+/(?:pull|issues)/\d+")
TICKET_WAIT = timedelta(days=7)
HARNESS_PREFIXES = ("<command-", "<local-command", "<system-reminder", "<task-notification")
# Markdown that ADF has no text for. The ticket script converts the draft from Markdown to ADF, and
# the final comes back as the text of the ADF, so the draft drops the same markup before the two
# texts compare.
FENCED_BLOCK = re.compile(r"^```.*?^```[^\n]*$", re.MULTILINE | re.DOTALL)
LINE_MARKUP = re.compile(r"^\s*(?:#{1,6}\s+|[-*+]\s+|\d+[.)]\s+|>\s?)", re.MULTILINE)
LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")
INLINE_CODE = re.compile(r"`([^`]*)`")
EMPHASIS = re.compile(r"(\*\*|__|`|(?<![\w*])\*(?=\S)|(?<=\S)\*(?![\w*]))")
# A plain shell assignment at the start of a statement, such as `S=/tmp/x;`, and a variable use.
ASSIGNMENT = re.compile(r"(?:^|[;&|\n])\s*([A-Za-z_][A-Za-z0-9_]*)=(\"[^\"]*\"|'[^']*'|[^\s;&|]+)")
VARIABLE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}|\$([A-Za-z_][A-Za-z0-9_]*)")

Event = dict[str, object]


def projects_dir() -> Path:
    config = os.environ.get("CLAUDE_CONFIG_DIR")
    return (Path(config) if config else Path.home() / ".claude") / "projects"


def transcripts(root: Path) -> list[Path]:
    """List each transcript under *root*. A subagent drafts nothing that the user sends, so its transcript drops out."""
    return sorted(path for path in root.rglob("*.jsonl") if "subagents" not in path.relative_to(root).parts)


def read_events(path: Path) -> list[Event]:
    """Read the user and assistant records of one transcript. Raise OSError if the file is unreadable."""
    events: list[Event] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if isinstance(event, dict) and event.get("type") in {"user", "assistant"}:
            events.append(event)
    return events


def text_of(event: Event) -> str:
    """Return the text blocks of *event*. A record of only tool calls, tool results, or thinking has none."""
    message = event.get("message")
    content = message.get("content") if isinstance(message, dict) else None
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    parts = [block.get("text", "") for block in content if isinstance(block, dict) and block.get("type") == "text"]
    return "\n".join(str(part) for part in parts)


def sent_text(event: Event) -> str | None:
    """Return the final in a user record whose first line that is not blank starts with SENT>."""
    if event.get("type") != "user" or event.get("isMeta"):
        return None
    lines = [line for line in PASTE_TAG.sub("", text_of(event)).splitlines() if line.strip()]
    if not lines or not lines[0].lstrip().startswith(SENT):
        return None
    lines[0] = lines[0].lstrip()[len(SENT) :]
    return "\n".join(lines).strip()


def user_request(event: Event) -> str:
    """Return the text of a request that the user typed.

    The harness also writes user records: a meta record, a compaction summary, a slash command, its
    output, a system reminder, and a task notification. None of them is a request, and a summary
    holds text that Claude wrote.
    """
    if event.get("type") != "user" or event.get("isMeta") or event.get("isCompactSummary"):
        return ""
    text = text_of(event).strip()
    return "" if text.startswith(HARNESS_PREFIXES) else text


def marked(text: str) -> bool:
    """Answer whether *text* ends with the paste-back line, so it is a draft of a message.

    A reply that quotes the line in a sentence, such as a reply about the reminder itself, is not a
    draft. Emphasis or code marks around the line do not count.
    """
    lines = [line for line in text.splitlines() if line.strip()]
    return bool(lines) and lines[-1].strip().strip("`*_ ") == PASTE_BACK


def message_pairs(events: list[Event]) -> list[Record]:
    """Pair each SENT> final with the nearest earlier draft that holds the paste-back line.

    The requests start at the first marked draft after the previous final, because the user often
    asks for several revisions before the last draft.
    """
    pairs: list[Record] = []
    # The index of the first marked draft after the last final, for each session.
    first_marked: dict[object, int] = {}
    last_marked: dict[object, int] = {}
    for index, event in enumerate(events):
        session = event.get("sessionId")
        if event.get("type") == "assistant" and marked(text_of(event)):
            first_marked.setdefault(session, index)
            last_marked[session] = index
            continue
        final = sent_text(event)
        if final is None:
            continue
        start = last_marked.pop(session, None)
        chain = first_marked.pop(session, None)
        if start is None or chain is None:
            continue
        draft_event = events[start]
        lines = text_of(draft_event).rstrip().splitlines()
        draft = "\n".join(lines[:-1]).strip()
        if same_text(draft, final):
            continue
        between = [other for other in events[chain + 1 : index] if other.get("sessionId") == session]
        requests = [text for other in between if (text := user_request(other))]
        pairs.append(
            Record(
                id=Record.make_id(str(session), str(draft_event.get("uuid"))),
                kind="message",
                session=str(session),
                timestamp=str(draft_event.get("timestamp", "")),
                cwd=str(draft_event.get("cwd", "")),
                draft=draft,
                final=final,
                requests=requests,
            )
        )
    return pairs


@dataclass(frozen=True)
class TicketTool:
    """A project's ticket script, as `tickets.json` in the store describes it.

    A ticket script belongs to its project, so the plugin cannot name it. Each pattern is a regular
    expression. `view` runs in the working directory of the record, with `{key}` in place of the
    ticket key, and prints the ticket as JSON. `field` is the dotted path of the description in that
    JSON.
    """

    name: str
    command: str
    body_flag: str
    key_in_command: str
    key_in_result: str
    view: list[str]
    field: str


def load_ticket_tools(store_root: Path) -> list[TicketTool]:
    """Read `tickets.json` in the store. A missing file gives no tools, and a malformed one raises ValueError."""
    try:
        text = (store_root / "tickets.json").read_text(encoding="utf-8")
    except FileNotFoundError:
        return []
    data = json.loads(text)
    if not isinstance(data, list):
        raise ValueError("tickets.json must hold a list")
    return [TicketTool(**entry) for entry in data]


@dataclass(frozen=True)
class Call:
    """One tool call that ran, with its result."""

    index: int
    event: Event
    name: str
    tool_input: dict[str, object]
    result: str


def calls(events: list[Event]) -> list[Call]:
    """Return each tool call whose result shows no error. A call that a hook denied did not run."""
    results: dict[str, tuple[bool, str]] = {}
    for event in events:
        message = event.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        for block in content if isinstance(content, list) else []:
            if isinstance(block, dict) and block.get("type") == "tool_result":
                results[str(block.get("tool_use_id"))] = (block.get("is_error") is True, result_text(block))
    found: list[Call] = []
    for index, event in enumerate(events):
        if event.get("type") != "assistant":
            continue
        message = event.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        for block in content if isinstance(content, list) else []:
            if not isinstance(block, dict) or block.get("type") != "tool_use":
                continue
            error, text = results.get(str(block.get("id")), (True, ""))
            tool_input = block.get("input")
            if not error and isinstance(tool_input, dict):
                found.append(Call(index, event, str(block.get("name")), tool_input, text))
    return found


def result_text(block: dict[str, object]) -> str:
    content = block.get("content")
    if isinstance(content, list):
        return "\n".join(str(part.get("text", "")) for part in content if isinstance(part, dict))
    return str(content or "")


def body_of(call: Call, flag_value: str, written: dict[str, str]) -> str | None:
    """Return the body that a flag names: the heredoc for `-`, or the last earlier `Write` of the file."""
    value = unquote(flag_value)
    if value == "-":
        heredoc = HEREDOC.search(str(call.tool_input.get("command", "")))
        if heredoc is None:
            return None
        rest = str(call.tool_input.get("command", ""))[heredoc.end() :]
        closer = re.search(r"^\s*" + re.escape(heredoc.group(2)) + r"\s*$", rest, re.MULTILINE)
        return rest[: closer.start()] if closer else rest
    path = Path(expand_variables(value, str(call.tool_input.get("command", "")))).expanduser()
    if not path.is_absolute():
        path = Path(str(call.event.get("cwd", ""))) / path
    return written.get(str(path))


def expand_variables(value: str, command: str) -> str:
    """Expand each `$NAME` in *value* that a plain `NAME=value` assignment in *command* sets."""
    names = {match.group(1): unquote(match.group(2)) for match in ASSIGNMENT.finditer(command)}
    return VARIABLE.sub(lambda match: names.get(match.group(1) or match.group(2), match.group(0)), value)


def apply_edits(written: dict[str, str], tool_input: dict[str, object]) -> None:
    """Apply an `Edit` or a `MultiEdit` to the text of a written file.

    A body file can change after its `Write`, for example after the `gh` hook denies its body. If an
    edit does not match, the text of the file is unknown, so the file drops out and a later call that
    names it gives a reported skip.
    """
    path = str(tool_input.get("file_path"))
    if path not in written:
        return
    edits = tool_input.get("edits") if isinstance(tool_input.get("edits"), list) else [tool_input]
    text = written[path]
    for edit in edits if isinstance(edits, list) else []:
        old = str(edit.get("old_string", "")) if isinstance(edit, dict) else ""
        if not old or old not in text:
            del written[path]
            return
        new = str(edit.get("new_string", ""))
        text = text.replace(old, new) if edit.get("replace_all") else text.replace(old, new, 1)
    written[path] = text


def markdown_text(markdown: str) -> str:
    """Return the text of a Markdown body in the form that the ADF of a ticket holds."""
    text = FENCED_BLOCK.sub("", markdown)
    text = LINK.sub(r"\1", text)
    text = LINE_MARKUP.sub("", text)
    # A code span keeps its text as it is, so `__init__` stays whole. Only the text between the spans
    # loses its emphasis marks.
    parts = INLINE_CODE.split(text)
    return "".join(part if index % 2 else EMPHASIS.sub("", part) for index, part in enumerate(parts)).strip()


def body_pairs(events: list[Event], tools: list[TicketTool]) -> tuple[list[Record], list[str]]:
    """Pair the first PR or ticket body for each target. Return the records and a line for each skipped call."""
    found: dict[str, tuple[Call, str, str, str]] = {}
    last: dict[str, int] = {}
    skipped: list[str] = []
    written: dict[str, str] = {}
    for call in calls(events):
        command = str(call.tool_input.get("command", ""))
        if call.name == "Write":
            written[str(call.tool_input.get("file_path"))] = str(call.tool_input.get("content", ""))
            continue
        if call.name in {"Edit", "MultiEdit"}:
            apply_edits(written, call.tool_input)
            continue
        if call.name != "Bash":
            continue
        pair = pr_body(call, command, written) if PR_WRITE.search(command) else ticket_body(call, command, written, tools)
        if pair is None:
            continue
        kind, target, body, tool = pair
        if body is None or not target:
            skipped.append(f"skipped: no body or target for {kind} in {call.event.get('sessionId')}: {command.splitlines()[0][:200]}")
            continue
        draft = prepare(body).strip()
        found.setdefault(target, (call, kind, markdown_text(draft) if kind == "ticket" else draft, tool))
        last[target] = call.index
    records: list[Record] = []
    for target, (call, kind, draft, tool) in found.items():
        session = call.event.get("sessionId")
        between = [other for other in events[call.index + 1 : last[target]] if other.get("sessionId") == session]
        records.append(
            Record(
                id=Record.make_id(str(session), str(call.event.get("uuid"))),
                kind=kind,
                session=str(session),
                timestamp=str(call.event.get("timestamp", "")),
                cwd=str(call.event.get("cwd", "")),
                draft=draft,
                final="",
                requests=[text for other in between if (text := user_request(other))],
                target=target,
                tool=tool,
            )
        )
    return records, skipped


def pr_body(call: Call, command: str, written: dict[str, str]) -> tuple[str, str, str | None, str] | None:
    """Return the body of a PR or issue write. An edit with no body, such as a label change, is no draft."""
    heredocs, remainder = heredoc_bodies(command)
    inline = [unquote(match.group(1)) for match in BODY_FLAG.finditer(remainder)]
    files = [match.group(1) for match in BODY_FILE.finditer(remainder)]
    if not (heredocs or inline or files):
        return None
    body = (heredocs + inline)[0] if heredocs or inline else body_of(call, files[0], written) if files else None
    url = PR_URL.search(call.result)
    return "pr", url.group(0) if url else "", body, ""


def ticket_body(call: Call, command: str, written: dict[str, str], tools: list[TicketTool]) -> tuple[str, str, str | None, str] | None:
    for tool in tools:
        if not re.search(tool.command, command):
            continue
        flag = re.search(re.escape(tool.body_flag) + r"(?:=|\s+)(\S+)", command)
        if flag is None:
            return None  # An edit of a parent, a label, or a summary changes no description.
        body = body_of(call, flag.group(1), written)
        key = re.search(tool.key_in_result, call.result) or re.search(tool.key_in_command, command)
        return "ticket", key.group(1) if key else "", body, tool.name
    return None


Runner = Callable[[list[str], str | None], str]


def run_command(command: list[str], cwd: str | None) -> str:
    return subprocess.run(command, cwd=cwd, check=True, capture_output=True, text=True, timeout=120).stdout


def fetch_finals(store: Store, tools: list[TicketTool], runner: Runner, now: datetime) -> list[str]:
    """Fill the final of each PR and ticket record that waits for one. Return a line for each failure.

    A PR final waits until the PR is merged or closed, because the user can still edit an open PR.
    A ticket has no state that marks the end of its edits, so its final waits 7 days.
    """
    by_name = {tool.name: tool for tool in tools}
    finals: dict[str, str] = {}
    failures: list[str] = []
    for record in store.records():
        if record.final or record.kind not in {"pr", "ticket"}:
            continue
        cwd = record.cwd if Path(record.cwd).is_dir() else None
        try:
            if record.kind == "pr":
                noun = "issue" if "/issues/" in record.target else "pr"
                data = json.loads(runner(["gh", noun, "view", record.target, "--json", "body,state"], cwd))
                if data.get("state") not in {"MERGED", "CLOSED"}:
                    continue
                final = str(data.get("body", ""))
            else:
                tool = by_name.get(record.tool)
                if tool is None:
                    failures.append(f"no ticket tool named {record.tool!r} for {record.target}")
                    continue
                if now - datetime.fromisoformat(record.timestamp) < TICKET_WAIT:
                    continue
                if cwd is None:
                    failures.append(f"working directory gone for {record.target}: {record.cwd}")
                    continue
                view = [part.replace("{key}", record.target) for part in tool.view]
                final = ticket_text(json.loads(runner(view, cwd)), tool.field)
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            failures.append(f"fetch failed for {record.target}: {error}")
            continue
        finals[record.id] = prepare(final).strip()
    if finals:
        store.update_finals(finals)
    return failures


def ticket_text(data: object, path: str) -> str:
    """Follow the dotted *path* into the view JSON, and decode the ADF description that it names."""
    for part in path.split("."):
        data = data.get(part) if isinstance(data, dict) else None
    if isinstance(data, str):
        return data
    return decode_jira(json.dumps(data)) if data is not None else ""


def extract(projects: Path, store: Store, *, fetch: bool = False) -> None:
    try:
        tools = load_ticket_tools(store.root)
    except (OSError, ValueError, TypeError) as error:
        print(f"tickets.json unreadable, so no ticket pairs: {error}")
        tools = []
    messages: list[Record] = []
    # A PR or a ticket can appear in several transcripts, and the store keeps the first draft for
    # each target. So the body records go to the store in time order, not in the order of the files.
    bodies: list[Record] = []
    for path in transcripts(projects):
        try:
            events = read_events(path)
        except (OSError, UnicodeDecodeError) as error:
            print(f"unreadable: {path} ({error})")
            continue
        found, skipped = body_pairs(events, tools)
        for line in skipped:
            print(line)
        bodies += found
        messages += message_pairs(events)
    # One add for each kind, because each add takes the lock and reads the whole store.
    added = store.add(messages) + store.add(sorted(bodies, key=lambda record: record.timestamp))
    print(f"added {added}")
    if store.skipped_lines:
        print(f"records.jsonl holds {store.skipped_lines} lines that are not records. The store keeps them as they are.")
    if fetch:
        for line in fetch_finals(store, tools, run_command, datetime.now(UTC)):
            print(line)


def default_store() -> Path | None:
    data = os.environ.get("CLAUDE_PLUGIN_DATA")
    return Path(data) / "feedback" if data else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--projects", type=Path, default=None, help="the transcripts (default: the Claude Code projects)")
    parser.add_argument("--store", type=Path, default=None, help="the store (default: $CLAUDE_PLUGIN_DATA/feedback)")
    sub = parser.add_subparsers(dest="command", required=True)
    extract_parser = sub.add_parser("extract", help="write the new pairs to the store")
    extract_parser.add_argument("--fetch", action="store_true", help="fill the finals of PRs and tickets")
    sub.add_parser("pending", help="print each unclassified record as one JSON line")
    classify = sub.add_parser("classify", help="record the cause and the correction label of one record")
    classify.add_argument("id")
    classify.add_argument("cause")
    classify.add_argument("label")
    sub.add_parser("labels", help="print each label with the count of each cause")
    sub.add_parser("done", help="record the time of this review, once no record is pending")
    args = parser.parse_args(argv)

    root = args.store or default_store()
    if root is None:
        parser.error("CLAUDE_PLUGIN_DATA is not set, so give --store")
    store = Store(root)
    if args.command == "extract":
        extract(args.projects or projects_dir(), store, fetch=args.fetch)
    elif args.command == "pending":
        for record in store.unclassified():
            print(json.dumps(asdict(record)))
    elif args.command == "classify":
        store.classify(args.id, args.cause, args.label)
    elif args.command == "labels":
        for label, causes in sorted(store.labels().items()):
            print(f"{label}: " + ", ".join(f"{cause} {count}" for cause, count in causes.most_common()))
    else:
        waiting = len(store.unclassified())
        if waiting:
            print(f"{waiting} records are pending. Classify each one before done.")
            return 1
        store.mark_reviewed()
    return 0


if __name__ == "__main__":
    sys.exit(main())
