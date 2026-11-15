"""Find the prose bodies that a `gh` or an `acli` command publishes.

`ste-gh-body-hook.py` checks these bodies before a command runs, and the extractor of the
reviewing-edit-feedback skill reads them from a transcript. A Python module name cannot hold a
hyphen, so this shared code lives here, not in the hook.

A Jira body travels as Atlassian Document Format. `decode_jira` reads the text nodes out of the ADF
tree and skips a `codeBlock`, because code is not prose.
"""

import json
import re
from pathlib import Path

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
# A message can use contractions, and an explanation in it can use the present perfect and
# `should`. A PR description, an issue body and a Jira description are documents, so they keep
# the strict form.
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
# The lookbehind stops `-b` from matching the tail of a value such as `my-b`.
BODY_FLAG = re.compile(r"(?<![A-Za-z0-9-])(?:--body|--notes|-b)(?:=|\s+)(\"(?:[^\"\\]|\\.)*\"|'[^']*')")
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
