#!/usr/bin/env python3
"""PostToolUse hook. Reports ASD-STE100 violations in text that Claude writes.

Three paths:
  Markdown   - scores the whole change against every check. A procedure keeps
               every rule. An explanation moves `would`, `could`, `might`, and
               the length limit to the advisory "Read again" count.
  Docstring  - a docstring is a prose paragraph, so it takes the same checks.
  Comment    - an inline comment is a fragment. Code identifiers defeat the
               length and tense regexes there, so only the word-level checks
               run. A soft modal is advisory there too.

Every path also takes the structural checks from ste_structural.py. Those catch
a shape rather than a word, so an identifier cannot defeat them.

The hook scores the text of the change. It never reads the file on disk. An
edit to a document that predates this hook gets a score for the new text only,
so an existing backlog of non-compliant prose stays invisible here.

The hook reports and never blocks. ste_lint.py is a regex pass with known
false positives, so Claude judges each report.
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
import ste_structural
from register import SOFT_MODALS, is_procedural, lint_registers
from ste_lint import lint, strip_code

MARKDOWN_SUFFIXES = (".md", ".markdown", ".mdx")
CODE_SUFFIXES = (".py", ".ts", ".tsx", ".js", ".jsx", ".mts", ".cts")

# Short edits carry too few words for a sentence-length score.
MIN_WORDS = 25

# An agent instruction file addresses a model, not a person. Its style rules are the ones
# inside it.
AGENT_INSTRUCTION_FILES = frozenset({"claude.md", "agents.md", "gemini.md"})

# These two checks fire on correct English. Name them so Claude discounts them.
NOISY = ("synonym_rotation", "trailing_condition")

# An inline comment carries identifiers and fragments. Only the word-level
# checks survive that. Length, tense, and semicolons produce noise there, so
# they stay out. A docstring is ordinary prose and takes the full set.
CODE_CHECKS = ("banned_modal", "slop_word", "contraction", "latin_abbrev")

EXPLANATIONS_GUIDE = Path(__file__).resolve().parent.parent / "guides" / "explanations.md"

PY_DOCSTRING = re.compile(r'("""|\'\'\')(.*?)\1', re.DOTALL)
PY_COMMENT = re.compile(r"^[ \t]*#[ \t]?(.*)$", re.MULTILINE)
JS_BLOCK_COMMENT = re.compile(r"/\*(.*?)\*/", re.DOTALL)
JS_LINE_COMMENT = re.compile(r"(?<![:\w])//[ \t]?(.*)$", re.MULTILINE)
JS_DOC_MARKER = re.compile(r"^[ \t]*\*[ \t]?", re.MULTILINE)
PRAGMA = re.compile(
    r"^\s*(noqa|type:|pyright:|mypy:|ruff:|pylint:|eslint|dprint|prettier|"
    r"@ts-|TODO|FIXME|NOTE:|nosec|coverage:|fmt:)",
    re.IGNORECASE,
)


def changed_text(tool_name: str, tool_input: dict[str, object]) -> str:
    """Return the text this tool call wrote, or an empty string."""
    if tool_name == "Write":
        value = tool_input.get("content")
    else:
        value = tool_input.get("new_string")
    return value if isinstance(value, str) else ""


def comment_prose(text: str, suffix: str) -> tuple[str, str]:
    """Return the docstring prose and the inline comment prose of a source change.

    The two come back apart because they take different check sets. A block
    comment in a JavaScript file counts as a docstring.
    """
    blocks: list[str] = []
    inline: list[str] = []
    if suffix == ".py":
        for match in PY_DOCSTRING.finditer(text):
            blocks.append(match.group(2))
        stripped = PY_DOCSTRING.sub(" ", text)
        inline += PY_COMMENT.findall(stripped)
    else:
        for match in JS_BLOCK_COMMENT.finditer(text):
            blocks.append(JS_DOC_MARKER.sub("", match.group(1)))
        stripped = JS_BLOCK_COMMENT.sub(" ", text)
        inline += JS_LINE_COMMENT.findall(stripped)

    def keep(parts: list[str]) -> str:
        wanted = [p.strip() for p in parts if p.strip() and not PRAGMA.match(p.strip())]
        return "\n".join(wanted)

    return keep(blocks), keep(inline)


def merge(into: dict[str, int], more: dict[str, int]) -> None:
    """Add the non-zero counts of *more* into *into*."""
    for name, number in more.items():
        if number:
            into[name] = into.get(name, 0) + number


def merge_structural(hits: dict[str, int], advisory: dict[str, int], counts: dict[str, int]) -> None:
    """Add the shape counts: a hard key to *hits*, and a hedge or an intensifier to *advisory*."""
    merge(hits, {name: number for name, number in counts.items() if name not in ste_structural.ADVISORY_KEYS})
    merge(advisory, {name: number for name, number in counts.items() if name in ste_structural.ADVISORY_KEYS})


def structural_note(hits: dict[str, int]) -> str:
    """Return a line that names the shape defects in *hits*, or an empty string."""
    named = [name for name in ste_structural.KEYS if name in hits]
    if not named:
        return ""
    return (
        f"Shape defects: {', '.join(named)}. Delete the padding and state the fact once. See ste_structural.py for what each name matches."
    )


def build_message(report: dict[str, object], hits: dict[str, int], advisory: dict[str, int], code: bool) -> str:
    note = structural_note(hits)
    lines = [
        "STE check on the comments and docstrings you wrote."
        if code
        else "STE check on the markdown you wrote. The limit is 20 words for a procedure sentence."
    ]
    if hits:
        counts = ", ".join(f"{name} {number}" for name, number in sorted(hits.items()))
        lines.append(f"Violations: {counts}.")
    if code:
        lines.append("In an instruction, the approved modals are can, will, and must.")
    else:
        lines.append(f"Longest sentence: {report['longest_sentence_words']} words. Mean: {report['mean_sentence_words']} words.")
    if advisory:
        counts = ", ".join(f"{name} {number}" for name, number in sorted(advisory.items()))
        lines.append(
            f"Read again: {counts}. In an explanation, would, could, and might fit a case that is not real or not certain. "
            "A long sentence fits one line of reasoning. A hedge or an intensifier fits only when it carries a fact. "
            f"Read each flagged sentence and keep it if it fits. See {EXPLANATIONS_GUIDE}."
        )
    noisy_hits = [name for name in NOISY if name in hits]
    if noisy_hits and not code:
        lines.append(f"Discount {' and '.join(noisy_hits)} when the English is correct. The check is a regex.")
    if note:
        lines.append(note)
    if code:
        lines.append("Correct the real violations in your next edit. Do not rewrite prose you did not write.")
    else:
        lines.append(
            "A table row counts as a sentence. Correct the real violations in your next edit. Do not rewrite text you did not write."
        )
    return " ".join(lines)


def main() -> None:
    try:
        event = json.load(sys.stdin)
    except json.JSONDecodeError, UnicodeDecodeError:
        return
    if not isinstance(event, dict):
        return

    tool_name = event.get("tool_name")
    if tool_name not in ("Write", "Edit"):
        return

    tool_input = event.get("tool_input")
    if not isinstance(tool_input, dict):
        return

    path = tool_input.get("file_path")
    if not isinstance(path, str):
        return
    lowered = path.lower()
    if Path(lowered).name in AGENT_INSTRUCTION_FILES:
        return
    is_code = lowered.endswith(CODE_SUFFIXES)
    if not is_code and not lowered.endswith(MARKDOWN_SUFFIXES):
        return

    text = changed_text(tool_name, tool_input)
    hits: dict[str, int] = {}
    advisory: dict[str, int] = {}
    if is_code:
        docstrings, comments = comment_prose(text, Path(lowered).suffix)
        prose = f"{docstrings}\n{comments}".strip()
        if len(prose.split()) < MIN_WORDS:
            return
        report = lint_registers(docstrings)
        merge(hits, report["hard"])
        merge(advisory, report["advisory"])
        if comments.split():
            partial = dict(lint(comments, "descriptive")["violations"])
            # A soft modal is the only modal an explanation can keep. A comment line
            # that gives an instruction is a procedure, so its soft modal stays banned.
            soft = sum(len(SOFT_MODALS.findall(strip_code(line))) for line in comments.split("\n") if not is_procedural(line))
            partial["banned_modal"] = max(0, partial.get("banned_modal", 0) - soft)
            merge(hits, {n: partial[n] for n in CODE_CHECKS if partial.get(n)})
            merge(advisory, {"modal_read": soft})
        merge_structural(hits, advisory, ste_structural.count(prose))
    else:
        if len(text.split()) < MIN_WORDS:
            return
        report = lint_registers(text)
        merge(hits, report["hard"])
        merge(advisory, report["advisory"])
        merge_structural(hits, advisory, ste_structural.count(text))
    if not hits and not advisory:
        return

    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PostToolUse",
                    "additionalContext": build_message(report, hits, advisory, is_code),
                },
            }
        )
    )


if __name__ == "__main__":
    main()
