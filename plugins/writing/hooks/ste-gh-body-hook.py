#!/usr/bin/env python3
"""PreToolUse hook. Blocks a `gh` or `acli` command whose body breaks ASD-STE100.

`ste-lint-hook.py` covers markdown that Write and Edit produce. It cannot see a
PR body, an issue body, a review body, or a Jira description, because those
travel through Bash to `gh` and to `acli`. This hook closes that gap.

A Jira body travels as Atlassian Document Format. The hook reads the text nodes
out of the ADF tree, so the linter never sees the JSON scaffolding. It skips a
`codeBlock`, because code is not prose.

The hook denies instead of reporting. A posted body is public and costs more to
correct than a retry. ste_lint.py is a regex pass, so the hook strips tables and
code first. A PR body or an issue body is mostly explanation. The hook denies only on a rule that
is hard in both registers. `would`, `could`, `might`, and a long sentence never deny, whatever
the register of the sentence. A body that has advisory counts only passes in silence, because a
note cannot change a body that is posted.

Escape hatch: after MAX_STRIKES consecutive denials in one session, the hook
lets the command through and says so. A clean check resets the count.
"""

import json
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
from register import FIRM_MODALS, classify
from ste_lint import (
    CONTRACTION,
    ING_CLAUSE,
    LATIN,
    PERFECT,
    SLOP,
    lint,
    strip_code,
)

# gh subcommands that publish prose. `gh api` needs no subcommand filter,
# because a read-only call carries no body field and drops out below.
GH_WRITE = re.compile(
    r"\bgh\s+(?:pr|issue|release)\b.*?\b(?:create|edit|comments?|reviews?)\b"
    r"|\bgh\s+api\b",
    re.DOTALL | re.IGNORECASE,
)

# acli subcommands that publish prose. A link, an assign, and a transition
# carry none, so they never reach the linter.
ACLI_WRITE = re.compile(
    r"\bacli\s+jira\s+workitem\s+"
    r"(?:create-bulk|create|edit|comment\s+(?:create|update))\b",
    re.DOTALL | re.IGNORECASE,
)

# Commands that post a message between people: a review, a PR or issue comment, a Jira comment.
# A message can use contractions. A PR description, an issue body and a Jira description are
# documents, so they keep the strict form.
MESSAGE_WRITE = re.compile(
    r"\bgh\s+(?:pr|issue)\s+(?:comment|review)\b"
    r"|\bgh\s+api\b.*?/(?:pulls|issues)/\d+/(?:reviews|comments)\b"
    r"|\bgh\s+api\b.*?/pulls/comments/\d+\b"
    r"|\bgh\s+api\b.*?/issues/comments/\d+\b"
    r"|\bacli\s+jira\s+workitem\s+comment\b",
    re.DOTALL | re.IGNORECASE,
)

HEREDOC = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")
# Shell separators that end one statement. The lookback for the consuming command stops at these.
# One backslash before a newline continues the line. Two backslashes are an escaped backslash,
# so only an odd count continues it.
LINE_CONTINUATION = re.compile(r"(?<!\\)((?:\\\\)*)\\\n")
STATEMENT_BREAK = re.compile(r";|&&|\|\||\n")
# The command that eats a heredoc. Only `gh` and `acli` publish prose, so only their heredocs are
# a body. A `python3 - <<'PY'` that builds the JSON is source code, and linting it reports
# violations in code that nobody publishes.
HEREDOC_CONSUMER = re.compile(r"(?<![A-Za-z0-9_-])(?:gh|acli)(?![A-Za-z0-9_-])")
BODY_FLAG = re.compile(r"(?:--body|--notes|-b)(?:=|\s+)(\"(?:[^\"\\]|\\.)*\"|'[^']*')")
BODY_FILE = re.compile(r"--body-file(?:=|\s+)(\S+)")
# `gh api --input` sends a JSON file as the request. A review carries its text in `body` and in the
# `body` of each inline comment. `-` reads standard input, which the hook cannot see.
INPUT_FILE = re.compile(r"--input(?:=|\s+)(\S+)")
API_FIELD = re.compile(r"(?:-f|-F|--field|--raw-field)(?:=|\s+)body=(\"[^\"]*\"|'[^']*'|\S+)")

# A `-file` suffix keeps these apart, because each pattern demands `=` or a
# space straight after the flag name. The lookbehind stops a short flag from
# matching the tail of a longer one.
ACLI_TEXT = re.compile(
    r"(?<![A-Za-z0-9-])(?:--summary|--description|--body|-s|-d|-b)(?:=|\s+)"
    r"(\"(?:[^\"\\]|\\.)*\"|'[^']*'|[^\s\"']+)"
)
ACLI_FILE = re.compile(
    r"(?<![A-Za-z0-9-])"
    r"(?:--description-file|--body-file|--from-file|--from-json|-F|-f)(?:=|\s+)(\S+)"
)

# ADF nodes that hold one block of prose. Every other container recurses.
ADF_BLOCKS = frozenset({"paragraph", "heading"})

TABLE_ROW = re.compile(r"^\s*\|.*$", re.MULTILINE)
HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
MD_LINK_TARGET = re.compile(r"\]\([^)]*\)")

# The checks that deny. Each one is hard in both registers. `banned_modal` counts `should` and
# `may` only. `synonym_rotation` fires on correct English, so it never denies.
BLOCKING = (
    "banned_modal",
    "semicolon",
    "contraction",
    "latin_abbrev",
    "slop_word",
    "ing_clause",
    "perfect_tense",
)

# The longest part of the first flagged sentence that a denial quotes.
QUOTE_LIMIT = 120

EXAMPLE_PATTERNS = {
    "banned_modal": FIRM_MODALS,
    "contraction": CONTRACTION,
    "latin_abbrev": LATIN,
    "slop_word": SLOP,
    "ing_clause": ING_CLAUSE,
    "perfect_tense": PERFECT,
}

# A plugin update replaces the plugin folder, so the strike state lives in the plugin data folder.
_DATA = os.environ.get("CLAUDE_PLUGIN_DATA", "")
STATE_DIR = Path(_DATA) / "ste-gh-body-state" if _DATA else None
MAX_STRIKES = 2
STANDARDS = Path(__file__).resolve().parent.parent / "standards.md"


def unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def publishes_heredoc(prefix: str) -> bool:
    """Answer whether the statement that opens this heredoc runs `gh` or `acli`.

    The prefix is everything before the `<<`. Only the last statement of it counts, so an earlier
    `acli` on another line never adopts a heredoc that feeds a different command.
    """
    # A backslash at the end of a line continues the statement, as in `gh pr create \` with
    # `--body "$(cat <<EOF` on the next line.
    statement = STATEMENT_BREAK.split(LINE_CONTINUATION.sub(r"\1 ", prefix))[-1]
    return bool(HEREDOC_CONSUMER.search(statement))


def heredoc_bodies(command: str) -> tuple[list[str], str]:
    """Return each published heredoc body, and the command with every heredoc region removed.

    A heredoc that feeds another command is dropped from the bodies. Its region still leaves the
    remainder, so a flag quoted inside it never reads as a real flag.
    """
    bodies: list[str] = []
    spans: list[tuple[int, int]] = []
    for match in HEREDOC.finditer(command):
        delimiter = match.group(2)
        rest = command[match.end() :]
        closer = re.search(r"^\s*" + re.escape(delimiter) + r"\s*$", rest, re.MULTILINE)
        stop = match.end() + (closer.end() if closer else len(rest))
        if publishes_heredoc(command[: match.start()]):
            bodies.append(rest[: closer.start()] if closer else rest)
        spans.append((match.start(), stop))
    remainder = command
    for start, stop in reversed(spans):
        remainder = remainder[:start] + " " + remainder[stop:]
    return bodies, remainder


def read_body_file(raw: str) -> str:
    path = Path(unquote(raw)).expanduser()
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def input_bodies(raw: str) -> list[str]:
    """Return the prose fields of a `gh api --input` JSON file: its `body`, then each comment's."""
    if unquote(raw) == "-":
        return []
    try:
        data = json.loads(read_body_file(raw))
    except ValueError:
        return []
    if not isinstance(data, dict):
        return []
    found = [data.get("body")]
    comments = data.get("comments")
    if isinstance(comments, list):
        found += [entry.get("body") for entry in comments if isinstance(entry, dict)]
    return [value for value in found if isinstance(value, str)]


def adf_blocks(node: object, lines: list[str]) -> None:
    """Append one line per prose block found in an ADF tree."""
    if isinstance(node, list):
        for entry in node:
            adf_blocks(entry, lines)
        return
    if not isinstance(node, dict):
        return
    kind = node.get("type")
    if kind == "codeBlock":
        return
    if kind in ADF_BLOCKS:
        parts: list[str] = []
        adf_runs(node.get("content"), parts)
        joined = "".join(parts).strip()
        if joined:
            lines.append(joined)
        return
    adf_blocks(node.get("content"), lines)


def adf_runs(node: object, parts: list[str]) -> None:
    """Append the text of every text node under one prose block."""
    if isinstance(node, list):
        for entry in node:
            adf_runs(entry, parts)
        return
    if not isinstance(node, dict):
        return
    if node.get("type") == "text":
        value = node.get("text")
        if isinstance(value, str):
            parts.append(value)
        return
    adf_runs(node.get("content"), parts)


def decode_jira(raw: str) -> str:
    """Return prose from an acli value. ADF and a work item definition both parse."""
    stripped = raw.strip()
    if not stripped.startswith(("{", "[")):
        return raw
    try:
        data = json.loads(stripped)
    except ValueError:
        return raw
    lines: list[str] = []
    if isinstance(data, dict):
        summary = data.get("summary")
        if isinstance(summary, str):
            lines.append(summary)
    adf_blocks(data, lines)
    return "\n\n".join(lines)


def collect_jira_bodies(command: str) -> list[str]:
    bodies, remainder = heredoc_bodies(command)
    bodies += [unquote(m.group(1)) for m in ACLI_TEXT.finditer(remainder)]
    bodies += [read_body_file(m.group(1)) for m in ACLI_FILE.finditer(remainder)]
    return [text for text in (decode_jira(b) for b in bodies) if text.strip()]


def collect_bodies(command: str) -> list[str]:
    bodies, remainder = heredoc_bodies(command)
    bodies += [unquote(m.group(1)) for m in BODY_FLAG.finditer(remainder)]
    bodies += [unquote(m.group(1)) for m in API_FIELD.finditer(remainder)]
    bodies += [read_body_file(m.group(1)) for m in BODY_FILE.finditer(remainder)]
    if re.search(r"\bgh\s+api\b", remainder):
        for match in INPUT_FILE.finditer(remainder):
            bodies += input_bodies(match.group(1))
    return [b for b in bodies if b.strip()]


def prepare(text: str) -> str:
    """Remove markup that inflates the sentence count."""
    text = HTML_COMMENT.sub(" ", text)
    text = TABLE_ROW.sub(" ", text)
    return MD_LINK_TARGET.sub("]", text)


def blocking_hits(text: str, *, message: bool) -> tuple[dict[str, int], str]:
    """Count the denying checks in *text*, and return the first sentence that breaks one.

    A *message* between people can use contractions, so they do not count in one.
    """
    hits: dict[str, int] = {}
    first = ""
    for sentence in classify(text):
        violations = lint(sentence.text, "descriptive")["violations"]
        found = {name: violations.get(name, 0) for name in BLOCKING}
        found["banned_modal"] = len(FIRM_MODALS.findall(strip_code(sentence.text)))
        if message:
            found["contraction"] = 0
        for name, number in found.items():
            if number:
                hits[name] = hits.get(name, 0) + number
                first = first or sentence.text
    return hits, first


def examples(name: str, text: str) -> str:
    if name not in EXAMPLE_PATTERNS:
        return ""
    matches = list(EXAMPLE_PATTERNS[name].finditer(strip_code(text)))
    found: list[str] = []
    for match in matches:
        word = match.group(0).strip()
        if word and word.lower() not in [f.lower() for f in found]:
            found.append(word)
        if len(found) == 4:
            break
    return f" ({', '.join(found)})" if found else ""


def strike_file(session: str, tool: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_-]", "_", session)[:64] or "nosession"
    return STATE_DIR / f"{tool}-{safe}.json"


def read_strikes(path: Path) -> int:
    try:
        return int(json.loads(path.read_text(encoding="utf-8")).get("strikes", 0))
    except OSError, ValueError, TypeError:
        return 0


def prune_state(keep_days: int = 7) -> None:
    """Drop strike files from sessions that ended long ago."""
    cutoff = time.time() - keep_days * 86400
    try:
        for stale in [*STATE_DIR.glob("gh-*.json"), *STATE_DIR.glob("acli-*.json")]:
            if stale.stat().st_mtime < cutoff:
                stale.unlink()
    except OSError:
        pass


def write_strikes(path: Path, count: int) -> None:
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"strikes": count}), encoding="utf-8")
        prune_state()
    except OSError:
        pass


def build_reason(hits: dict[str, int], text: str, first: str, tool: str) -> str:
    counts = ", ".join(f"{name} {number}{examples(name, text)}" for name, number in sorted(hits.items()))
    quoted = first if len(first) <= QUOTE_LIMIT else first[:QUOTE_LIMIT].rstrip() + "..."
    lines = [
        f"STE check on the body you passed to {tool}. The command did not run.",
        f"Violations: {counts}.",
        f'First flagged sentence: "{quoted}"',
    ]
    lines.append(
        f"Rewrite the body to the standards in {STANDARDS}. "
        f"Show the corrected text to the user and get approval before you call {tool} again."
    )
    return " ".join(lines)


def emit(payload: dict[str, object]) -> None:
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", **payload}}))


def main() -> None:
    try:
        event = json.load(sys.stdin)
    except json.JSONDecodeError, UnicodeDecodeError:
        return
    if not isinstance(event, dict) or event.get("tool_name") != "Bash":
        return

    tool_input = event.get("tool_input")
    if not isinstance(tool_input, dict):
        return
    command = tool_input.get("command")
    if not isinstance(command, str):
        return
    if GH_WRITE.search(command):
        tool, bodies = "gh", collect_bodies(command)
    elif ACLI_WRITE.search(command):
        tool, bodies = "acli", collect_jira_bodies(command)
    else:
        return
    if not bodies:
        return
    if STATE_DIR is None:
        print(
            "ste-gh-body-hook: CLAUDE_PLUGIN_DATA is not set, so the body check did not run.",
            file=sys.stderr,
        )
        return

    text = prepare("\n\n".join(bodies))
    hits, first = blocking_hits(text, message=bool(MESSAGE_WRITE.search(command)))

    path = strike_file(str(event.get("session_id", "")), tool)
    if not hits:
        write_strikes(path, 0)
        return

    strikes = read_strikes(path) + 1
    if strikes > MAX_STRIKES:
        write_strikes(path, 0)
        emit(
            {
                "additionalContext": (
                    f"STE check still reports {sum(hits.values())} violations in this {tool} body. "
                    f"The hook allowed the command after {MAX_STRIKES} denials. Tell the user."
                ),
            }
        )
        return

    write_strikes(path, strikes)
    emit(
        {
            "permissionDecision": "deny",
            "permissionDecisionReason": build_reason(hits, text, first, tool),
        }
    )


if __name__ == "__main__":
    main()
