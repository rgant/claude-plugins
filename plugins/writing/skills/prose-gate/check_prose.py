#!/usr/bin/env python3
"""Report writing-standard violations in the prose this branch adds or changes.

Reads comments, docstrings, and markdown. Skips code. Reports one line per finding and never
rewrites anything. A finding is a candidate for a human read, not a verdict.

Scope: only sentences that touch a line the branch added or changed. Prose the base branch already
carries is left alone, so a check on a small edit does not turn into a rewrite of the whole file.

Usage:
    check_prose.py                      # the current branch against its merge-base
    check_prose.py --base main          # a different base branch
    check_prose.py --files a.md b.py    # named files, every line in scope
    check_prose.py --stdin              # text on standard input, for a draft not yet in a file
"""

import argparse
import ast
import io
import re
import subprocess
import sys
import tokenize
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

# The register rules and the structural checks live in modules that this script and the
# STE hooks share, in the lib folder of the writing plugin. The script needs that folder.
sys.path.append(str(Path(__file__).resolve().parents[2] / "lib"))
import register  # noqa: E402
import ste_lint  # noqa: E402
import ste_structural  # noqa: E402

MAX_DESCRIPTIVE = 25
MAX_PROCEDURAL = 20

SEMICOLON = re.compile(r";")
EM_DASH = re.compile(r"—")
CONTRACTION = re.compile(
    r"\b(\w+'(ll|re|ve|d)|can't|won't|don't|doesn't|didn't|isn't|aren't|wasn't|weren't|hasn't|haven't|it's|that's|there's|let's)\b",
    re.IGNORECASE,
)
_IRREGULAR = (
    "been|run|written|done|made|taken|seen|gone|given|known|shown|put|set|read|sent|kept|held|left|found|built"
    "|become|begun|brought|come|got|gotten"
)
PRESENT_PERFECT = re.compile(rf"\b(has|have|had)\s+(?:not\s+|never\s+)?({_IRREGULAR}|[a-z]+ed)\b", re.IGNORECASE)
PROGRESSIVE = re.compile(r"\b(is|are|was|were|be|been|being)\s+([a-z]+ing)\b", re.IGNORECASE)
PARTICIPIAL = re.compile(r",\s+([a-z]+ing)\b")
# After a form of "be", an "-ing" word is a verb for certain when nothing follows it, or when an
# object, a pronoun, a preposition, or code follows it: `is failing`, `is running make`. A bare
# word after it can be the noun that the "-ing" word modifies, as in `are working documents`, so
# that case is advisory. After a comma, an "-ing" word opens a trailing clause, so it is always hard.
VERB_AFTER_ING = re.compile(
    r"[\"'`*_\]]*\s*(?:$|[.,;:!?)\"'`*_\]]|(?-i:X)\b|(?:a|an|the|this|that|these|those|each|every|all|any|its|their|our|your|my|it|them"
    r"|him|her|us|me|nothing|something|anything|everything|to|on|in|into|at|for|from|with|without|by|of|up|out|over|through)\b)",
    re.IGNORECASE,
)
LATIN = re.compile(r"\b(e\.g\.|i\.e\.|etc\.)")
AND_OR = re.compile(r"\band/or\b", re.IGNORECASE)
TRAILING_CONDITION = re.compile(
    r"^\W*(?!(?:if|when|unless|until|while)\b)(?:\S+\s+){2,}(if|when|unless|until|while)\b",
    re.IGNORECASE,
)
# A count of members, not a quantity. ``three billed attempts`` measures. ``fourteen models`` counts a
# list that nothing keeps in step with the count.
COUNT_WORD = re.compile(
    r"\b(both|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty)\s+(?:[a-z-]+\s+)?([a-z]+s)\b",
    re.IGNORECASE,
)
COUNT_UNITS = {
    "attempts",
    "bytes",
    "gigabytes",
    "kilobytes",
    "megabytes",
    "processes",
    "requests",
    "calls",
    "characters",
    "chars",
    "columns",
    "days",
    "hours",
    "items",
    "lines",
    "minutes",
    "months",
    "pages",
    "retries",
    "rows",
    "seconds",
    "times",
    "tokens",
    "weeks",
    "words",
    "years",
}
PRIOR_STATE = re.compile(
    r"\b(previously|formerly|used to|no longer|the old |we changed|was changed|before this change|earlier version"
    r"|instead of the old|the deleted|now deleted|we removed|has been replaced|it replaced)",
    re.IGNORECASE,
)
SLOP = re.compile(
    r"\b(simply|seamlessly|effortlessly|robust|powerful|comprehensive|performant|leverage|utilize|in order to|prior to"
    r"|it is worth noting|functionality|gracefully|out of the box|under the hood|streamline|plethora|myriad|delve|dive into"
    r"|state-of-the-art|blazingly)\b",
    re.IGNORECASE,
)

# ``-ing`` words that read as a verb after ``is`` or a comma but are nouns or prepositions here. The house
# rules allow any ``-ing`` noun or modifier, so a sentence that opens with one is never checked.
ING_NOUNS = {
    "docstring",
    "logging",
    "string",
    "thing",
    "nothing",
    "something",
    "anything",
    "everything",
    "during",
    "ceiling",
    "recording",
    "reasoning",
    "meaning",
    "warning",
    "setting",
    "settings",
    "mapping",
    "encoding",
    "testing",
    "tooling",
    "handling",
    "wrapping",
    "casing",
    "spacing",
    "padding",
    "polling",
    "caching",
    "billing",
    "tracing",
    "sampling",
    "training",
    "building",
    "engineering",
    "morning",
    "according",
    "including",
    "remaining",
    "pending",
}

# Every rule the script can report. A hard rule fails the run. An advisory needs a human read.
HARD = {
    "LENGTH",
    "MODAL",
    "SEMICOLON",
    "EM-DASH",
    "CONTRACTION",
    "PRESENT-PERFECT",
    "ING-VERB",
    "LATIN",
    "AND-OR",
    "SLOP",
    # Shape defects from ste_structural.py. Each one is padding in every
    # context, so it fails the gate.
    "TRIPLE",
    "NOT-JUST",
    "REVERSAL",
    "FILLER",
    "ANNOUNCE",
}
# HEDGE and INTENSIFIER match a word that carries a fact in some sentences,
# such as "usually 5432". They report without failing the gate.
ADVISORY = {
    "TRAILING-CONDITION",
    "COUNT",
    "PRIOR-STATE",
    "LENGTH-READ",
    "MODAL-READ",
    "EM-DASH-READ",
    "ING-READ",
    "HEDGE",
    "INTENSIFIER",
}

CODE_SPAN = re.compile(r"``[^`]+``|`[^`]+`")
MD_SKIP = re.compile(r"^\s*(#{1,6}\s|\||!\[|<|\[!\[|:?-{3,}:?\s*$)")
LIST_ITEM = re.compile(r"^\s*([-*+]\s+|\d+[.)]\s+)")
SKIP_COMMENT = re.compile(r"^\s*#\s*(noqa|type:|pylint:|ruff:|mypy:|pyright:|!|-\*-)")

# An agent instruction file addresses a model, not a person. Its style rules are the ones
# inside it. `--files` still checks one on request.
AGENT_INSTRUCTION_FILES = frozenset({"claude.md", "agents.md", "gemini.md"})
# A generated file carries prose nobody wrote by hand. A changelog holds commit subjects, and the
# next release rewrites the whole file. `--files` still checks one on request.
GENERATED_FILES = frozenset({"changelog.md"})
# A repository lists its own third-party prose here, one glob per line, `#` for a comment. A
# vendored document is somebody else's writing, and a rewrite of it breaks what it vendors.
# `--files` still checks one on request.
IGNORE_FILE = ".prose-gate-ignore"


@dataclass
class Finding:
    """One reported violation, addressed by file and by the line its sentence starts on."""

    path: str
    line: int
    rule: str
    detail: str
    text: str


@dataclass
class Block:
    """One run of prose, with the source line each of its lines came from."""

    path: str
    lines: list[str] = field(default_factory=list)
    numbers: list[int] = field(default_factory=list)
    heading: str = ""
    callout: str = ""


def _run(args: list[str]) -> str:
    """Run a git command and return its output, or an empty string when git refuses."""
    try:
        done = subprocess.run(args, capture_output=True, text=True, check=False)
    except OSError:
        return ""
    return done.stdout if done.returncode == 0 else ""


def _default_base() -> str:
    """Name the branch this work forks from. Prefers the remote's own answer."""
    head = _run(["git", "symbolic-ref", "--quiet", "refs/remotes/origin/HEAD"]).strip()
    if head:
        return head.rsplit("/", 1)[-1]
    for name in ("develop", "main", "master"):
        if _run(["git", "rev-parse", "--verify", "--quiet", name]).strip():
            return name
    return "HEAD"


def changed_lines(base: str) -> dict[str, set[int]]:
    """Map each changed file to the line numbers this branch added or changed.

    Covers staged work, unstaged work, and untracked files. An untracked file counts as new in
    full, because every line of it arrived with this branch.
    """
    merge_base = _run(["git", "merge-base", "HEAD", base]).strip() or base
    diff = _run(["git", "diff", "--unified=0", "--no-color", merge_base])
    changes: dict[str, set[int]] = {}
    path = ""
    for line in diff.splitlines():
        if line.startswith("+++ "):
            name = line[4:].strip()
            path = "" if name == "/dev/null" else name.split("/", 1)[-1]
        elif line.startswith("@@") and path:
            match = re.search(r"\+(\d+)(?:,(\d+))?", line)
            if match:
                start = int(match.group(1))
                count = int(match.group(2) or 1)
                changes.setdefault(path, set()).update(range(start, start + count))
    for name in _run(["git", "ls-files", "--others", "--exclude-standard"]).splitlines():
        if name.strip():
            changes[name.strip()] = set(range(1, 100_000))
    skip = AGENT_INSTRUCTION_FILES | GENERATED_FILES
    patterns = _ignore_patterns()
    for name in [n for n in changes if Path(n).name.lower() in skip or _ignored(n, patterns)]:
        del changes[name]
    return changes


def _ignore_patterns() -> list[str]:
    """Read the repository's own list of vendored prose. An absent list ignores nothing."""
    root = _run(["git", "rev-parse", "--show-toplevel"]).strip()
    if not root:
        return []
    try:
        text = (Path(root) / IGNORE_FILE).read_text(encoding="utf-8")
    except OSError:
        return []
    return [line.strip() for line in text.splitlines() if line.strip() and not line.startswith("#")]


def _ignored(name: str, patterns: list[str]) -> bool:
    """Answer whether a repository-relative path matches one of the ignore globs."""
    path = PurePosixPath(name)
    return any(path.full_match(pattern) for pattern in patterns)


def _group(
    path: str,
    rows: list[tuple[int, str]],
    context: dict[int, tuple[str, str]] | None = None,
) -> list[Block]:
    """Split numbered lines into blocks. A blank line ends a block, and a list item starts one.

    *context* maps a line number to the (heading, callout) in force there. A change of either
    starts a new block, so a block always sits in one register context. A wholly bold line is
    a block of its own, so it never sets the register of the text under it.

    A list item is its own unit of prose. Joined with its neighbors it reads as one long sentence,
    and every length check on the list then reports a number nobody wrote.
    """
    blocks: list[Block] = []
    current = Block(path)
    for number, text in rows:
        heading, callout = (context or {}).get(number, ("", ""))
        if not text.strip():
            if current.lines:
                blocks.append(current)
                current = Block(path)
            continue
        item = register.TASK_BOX.sub("", LIST_ITEM.sub("", text).strip())
        bold = bool(register.BOLD_LINE.match(item))
        changed = (heading, callout) != (current.heading, current.callout)
        if current.lines and (changed or bold or LIST_ITEM.match(text)):
            blocks.append(current)
            current = Block(path)
        current.heading = heading
        current.callout = callout
        current.lines.append(item)
        current.numbers.append(number)
        if bold:
            # A wholly bold line is a lead-in. The text under it starts a new unit.
            blocks.append(current)
            current = Block(path)
    if current.lines:
        blocks.append(current)
    return blocks


def markdown_blocks(path: str, text: str) -> list[Block]:
    """Pull prose out of markdown. Fenced code, headings, tables, and images stay out.

    Each block records the last ATX heading and the open `> [!NAME]` callout. A wholly bold
    line is not a heading here, because a bold lead-in is also ordinary emphasis.
    """
    rows: list[tuple[int, str]] = []
    context: dict[int, tuple[str, str]] = {}
    tracker = register.MarkdownContext()
    lines = text.splitlines()
    fenced_lines = ste_lint.fence_mask(lines)
    # YAML frontmatter is machine-facing configuration, not prose a reader reads.
    start = register.frontmatter_end(lines)
    for number, raw in enumerate(lines[start:], start=start + 1):
        if fenced_lines[number - 1]:
            # `classify` reads a fenced line as a blank line, so the tracker does too.
            tracker.feed("")
            rows.append((number, ""))
            continue
        raw = tracker.feed(raw)
        context[number] = (tracker.heading, tracker.callout)
        rows.append((number, "" if MD_SKIP.match(raw) else raw))
    return _group(path, rows, context)


def python_blocks(path: str, text: str) -> list[Block]:
    """Pull comments and docstrings out of Python. The parser finds docstrings, not a pattern."""
    blocks: list[Block] = []
    try:
        tree = ast.parse(text)
    except SyntaxError:
        tree = None
    if tree is not None:
        for node in ast.walk(tree):
            if not isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            doc = ast.get_docstring(node, clean=False)
            if not doc:
                continue
            body = node.body[0]
            start = getattr(body, "lineno", 1)
            rows = [(start + offset, line.strip().strip('"')) for offset, line in enumerate(doc.splitlines())]
            blocks += _group(path, rows)
    rows = []
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(text).readline))
    except tokenize.TokenError, IndentationError, SyntaxError:
        tokens = []
    previous = -2
    for token in tokens:
        if token.type != tokenize.COMMENT or SKIP_COMMENT.match(token.string):
            continue
        number = token.start[0]
        if number != previous + 1:
            rows.append((number, ""))
        rows.append((number, token.string.lstrip("#").strip()))
        previous = number
    return blocks + _group(path, rows)


def script_blocks(path: str, text: str) -> list[Block]:
    """Pull ``//`` and ``/* */`` comments out of a TypeScript or JavaScript file."""
    blocks: list[Block] = []
    current = Block(path)
    previous = -2
    for number, raw in enumerate(text.splitlines(), start=1):
        stripped = raw.strip()
        body = ""
        if stripped.startswith("//"):
            body = stripped.lstrip("/").strip()
        elif stripped.startswith(("*", "/*")):
            body = stripped.lstrip("/*").rstrip("*/").strip()
        if not body or body.startswith(("eslint", "@ts-", "prettier")):
            if current.lines:
                blocks.append(current)
                current = Block(path)
            continue
        if number != previous + 1 and current.lines:
            blocks.append(current)
            current = Block(path)
        current.lines.append(body)
        current.numbers.append(number)
        previous = number
    if current.lines:
        blocks.append(current)
    return blocks


def extract(path: str, text: str) -> list[Block]:
    """Choose the reader for *path* by its suffix. An unknown suffix has no prose to read."""
    suffix = Path(path).suffix
    if suffix in {".md", ".markdown"}:
        return markdown_blocks(path, text)
    if suffix == ".py":
        return python_blocks(path, text)
    if suffix in {".ts", ".tsx", ".js", ".jsx", ".mts", ".cts"}:
        return script_blocks(path, text)
    return []


def word_count(sentence: str) -> int:
    """Count words the way the standard does. Code, a path, and a number each count as one word."""
    collapsed = CODE_SPAN.sub("X", sentence)
    collapsed = re.sub(r"\S*[/\\_]\S*", "X", collapsed)
    # A link target is one word. The words of a parenthetical remark still count.
    collapsed = re.sub(r"\]\([^)]*\)", "]", collapsed)
    return len([word for word in collapsed.split() if any(char.isalnum() for char in word)])


def sentences_of(block: Block) -> list[tuple[set[int], str]]:
    """Join the block's wrapped lines, then split the result into sentences.

    Each sentence carries the source lines it came from. A sentence wrapped over three lines belongs
    to all three, so a check scoped to changed lines can tell an edited sentence from its neighbor.
    """
    parts: list[str] = []
    line_of_char: list[int] = []
    for number, line in zip(block.numbers, block.lines, strict=True):
        if parts:
            parts.append(" ")
            line_of_char.append(number)
        parts.append(line)
        line_of_char.extend([number] * len(line))
    text = "".join(parts)
    # `register.sentence_spans` is the splitter `register.classify` uses, so the gate and the
    # hooks read the same sentences.
    return [(set(line_of_char[start:stop]), text[start:stop]) for start, stop in register.sentence_spans(text)]


def inspect(sentence: str, *, message: bool = False, procedural: bool = False) -> list[tuple[str, str]]:
    """Report every rule *sentence* breaks, as (rule, detail) pairs.

    A *procedural* sentence keeps the strict limits. In an explanation, the length limit, the
    soft modals (would, could, might), and the em dash report as advisory rules.

    A *message* is text between people, such as a review body or a PR comment. It can use contractions
    and the progressive, so neither reports.
    """
    found: list[tuple[str, str]] = []
    bare = CODE_SPAN.sub("X", sentence)
    count = word_count(sentence)
    if procedural and count > MAX_PROCEDURAL:
        found.append(("LENGTH", f"{count} words, limit {MAX_PROCEDURAL}"))
    elif not procedural and count > MAX_DESCRIPTIVE:
        found.append(("LENGTH-READ", f"{count} words, limit {MAX_DESCRIPTIVE}"))
    firm = register.FIRM_MODALS.search(bare)
    soft = register.SOFT_MODALS.search(bare)
    # In a procedure every modal is hard, so one finding covers the sentence.
    if firm:
        found.append(("MODAL", firm.group(1).strip()))
    if soft and not (procedural and firm):
        found.append(("MODAL" if procedural else "MODAL-READ", soft.group(1).strip()))
    for rule, pattern in (
        ("SEMICOLON", SEMICOLON),
        ("EM-DASH" if procedural else "EM-DASH-READ", EM_DASH),
        ("CONTRACTION", None if message else CONTRACTION),
        ("PRESENT-PERFECT", PRESENT_PERFECT),
        ("LATIN", LATIN),
        ("AND-OR", AND_OR),
        ("SLOP", SLOP),
        ("PRIOR-STATE", PRIOR_STATE),
    ):
        match = pattern.search(bare) if pattern is not None else None
        if match:
            found.append((rule, match.group(match.lastindex or 0).strip()))
    # Rule 5.4 puts the condition before the command, which is a rule about instructions. A trailing
    # ``when`` clause in an explanation is ordinary English, so only a procedural sentence reports.
    if procedural:
        trailing = TRAILING_CONDITION.search(bare)
        if trailing:
            found.append(("TRAILING-CONDITION", trailing.group(1)))
    counted = COUNT_WORD.search(bare)
    if counted and counted.group(2).lower() not in COUNT_UNITS:
        found.append(("COUNT", f"{counted.group(1)} ... {counted.group(2)}"))
    for pattern in (PARTICIPIAL,) if message else (PROGRESSIVE, PARTICIPIAL):
        for match in pattern.finditer(bare):
            word = match.group(match.lastindex or 0).lower()
            if word not in ING_NOUNS:
                certain = pattern is PARTICIPIAL or VERB_AFTER_ING.match(bare, match.end())
                found.append(("ING-VERB" if certain else "ING-READ", word))
                break
    found += ste_structural.find(bare)
    return found


def check(path: str, text: str, scope: set[int] | None, *, message: bool = False) -> list[Finding]:
    """Report the findings in *path*. *scope* limits them to the lines the branch touched."""
    findings: list[Finding] = []
    for block in extract(path, text):
        touched = scope is None or bool(scope.intersection(block.numbers))
        if not touched:
            continue
        for lines, sentence in sentences_of(block):
            if scope is not None and not scope.intersection(lines):
                continue
            procedural = register.is_procedural(sentence, heading=block.heading, callout=block.callout)
            for rule, detail in inspect(sentence, message=message, procedural=procedural):
                findings.append(Finding(path, min(lines, default=1), rule, detail, sentence))
    return findings


def report(findings: list[Finding]) -> int:
    """Print one line per finding, hard rules first. Return the exit status."""
    if not findings:
        print("prose-gate: no findings.")
        return 0
    hard = [item for item in findings if item.rule in HARD]
    soft = [item for item in findings if item.rule not in HARD]
    for title, group in (("VIOLATIONS", hard), ("READ AND JUDGE", soft)):
        if not group:
            continue
        print(f"\n== {title} ==")
        for item in sorted(group, key=lambda entry: (entry.path, entry.line)):
            print(f"{item.path}:{item.line}  {item.rule}  ({item.detail})")
            print(f"    {item.text[:160]}")
    print(f"\nprose-gate: {len(hard)} violations, {len(soft)} to read and judge.")
    return 1 if hard else 0


def main(argv: list[str] | None = None) -> int:
    """Check the selected prose and report every finding. Return 1 when a hard rule breaks."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    _ = parser.add_argument("--base", default="", help="base branch (default: the remote's own HEAD)")
    _ = parser.add_argument("--files", nargs="*", default=[], help="check these files in full")
    _ = parser.add_argument("--stdin", action="store_true", help="check markdown text on standard input")
    _ = parser.add_argument(
        "--message",
        action="store_true",
        help="the text is a message between people (a review body, a comment): allow contractions and the progressive",
    )
    args = parser.parse_args(argv)

    findings: list[Finding] = []
    if args.stdin:
        findings = check("<stdin>.md", sys.stdin.read(), None, message=args.message)
    elif args.files:
        for name in args.files:
            path = Path(name)
            if path.is_file():
                findings += check(
                    name,
                    path.read_text(encoding="utf-8", errors="replace"),
                    None,
                    message=args.message,
                )
    else:
        base = args.base or _default_base()
        scope = changed_lines(base)
        if not scope:
            print(f"prose-gate: nothing changed against {base}.")
            return 0
        for name, lines in sorted(scope.items()):
            path = Path(name)
            if path.is_file():
                findings += check(name, path.read_text(encoding="utf-8", errors="replace"), lines)
    return report(findings)


if __name__ == "__main__":
    raise SystemExit(main())
