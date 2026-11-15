#!/usr/bin/env python3
"""Check the shape of the two explanation guides, and run the prose gate over their text.

Both guides hold the same rules in the same order. The core file loads in every session, so it
stays short and holds only good passages. The full guide holds the before-and-after pairs too.
A "before" passage breaks the rules on purpose, so the gate skips the full guide, and this test
checks every other part of it.

Run: uv run --no-project --python ">=3.14" plugins/writing/tests/test_explanation_guide.py
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "skills" / "prose-gate"))
import check_prose  # noqa: E402

# The full guide ends with the table of quoted sources, after the checks.
APPENDIX = "Sources quoted"
CORE = ROOT / "guides" / "explanations-core.md"
FULL = ROOT / "guides" / "explanations.md"
MAX_CORE_WORDS = 1300

H2 = re.compile(r"^## (.+)$", re.MULTILINE)
RULE_HEADING = re.compile(r"^R(\d)\. ")
EXAMPLE_ID = re.compile(r"^\*\*(R\d-[A-Z0-9]+)\.\*\*")
QUOTE = re.compile(r"^> ?")
FORBIDDEN = ("Review note", "old standard")

# A verbatim public quote can break a rule that the guide's own prose keeps. Each entry maps an
# example ID to the (rule, detail) pairs that its quote can report.
ALLOWED = {"R7-P2": {("ING-VERB", "reading")}}
# The core file quotes R5-C from the Rust book without the sources table, so the MIT notice
# stays on the citation line.
RUST_COPYRIGHT = "2010 The Rust Project Developers"

SOURCE_PROJECTS = (
    "The Rust Programming Language",
    "PostgreSQL documentation",
    "Python documentation",
    "SQLite documentation",
    "Go FAQ",
)
LICENSE_NOTES = (
    "ask that the copyright notice stay with",
    "CC BY 4.0 asks for attribution and a note of changes",
)

failures = 0


def case(name: str, passed: bool, detail: object = "") -> None:
    global failures
    failures += not passed
    print(f"{'ok ' if passed else 'FAIL'} {name}")
    if not passed and detail:
        print(f"     {detail}")


def read(path: Path) -> str:
    """Return the file text. A missing file reads as empty, so each case reports its own failure."""
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def sections(text: str) -> list[tuple[str, list[str]]]:
    """Split the text at each level-2 heading. Return (heading, body lines) pairs."""
    found: list[tuple[str, list[str]]] = []
    for line in text.splitlines():
        match = H2.match(line)
        if match:
            found.append((match.group(1).strip(), []))
        elif found:
            found[-1][1].append(line)
    return found


def examples(lines: list[str]) -> dict[str, dict[str, str]]:
    """Map each example ID to its quotes, keyed by "good", "before", or "after"."""
    found: dict[str, dict[str, list[str]]] = {}
    current = ""
    part = "good"
    for line in lines:
        match = EXAMPLE_ID.match(line)
        if match:
            current = match.group(1)
            part = "good"
            found[current] = {}
            continue
        if line.startswith("#"):
            current = ""
            continue
        if line.startswith("Before:"):
            part = "before"
        elif line.startswith("After:"):
            part = "after"
        elif current and QUOTE.match(line):
            found[current].setdefault(part, []).append(QUOTE.sub("", line))
    return {key: {name: "\n".join(body) for name, body in parts.items()} for key, parts in found.items()}


def all_examples(text: str) -> dict[str, dict[str, str]]:
    merged: dict[str, dict[str, str]] = {}
    for _, lines in sections(text):
        merged.update(examples(lines))
    return merged


def hard_findings(name: str, text: str) -> list[str]:
    """Run the prose gate over *text* as markdown. Return each hard finding as a short line."""
    findings = check_prose.check(f"{name}.md", text, None)
    return [f"{item.rule} ({item.detail}): {item.text[:100]}" for item in findings if item.rule in check_prose.HARD]


def without_quotes(text: str) -> str:
    """Blank every quote line, and keep the line numbers."""
    return "\n".join("" if QUOTE.match(line) else line for line in text.splitlines())


def rule_headings(text: str) -> list[str]:
    return [heading for heading, _ in sections(text) if RULE_HEADING.match(heading)]


def check_structure(label: str, text: str, appendix: str = "") -> None:
    headings = [heading for heading, _ in sections(text)]
    if appendix and headings and headings[-1] == appendix:
        headings = headings[:-1]
    rules = headings[1:-1]
    numbers = [RULE_HEADING.match(heading) for heading in rules]
    ordered = all(numbers) and [int(match.group(1)) for match in numbers if match] == list(range(1, len(rules) + 1))
    case(
        f"{label}: the goal, then the rules in order, then the checks",
        bool(headings) and headings[0] == "The goal" and headings[-1] == "The checks" and bool(rules) and ordered,
        headings,
    )
    present = [word for word in FORBIDDEN if word in text]
    case(f"{label}: no text for the reviewer of the draft", not present, present)
    problems = hard_findings(label, without_quotes(text))
    case(f"{label}: prose outside the quotes has no hard finding", not problems, problems)


def main() -> None:
    core = read(CORE)
    full = read(FULL)
    check_structure("core", core)
    check_structure("full", full, appendix=APPENDIX)

    core_rules = rule_headings(core)
    case("both files hold the same rules in the same order", bool(core_rules) and core_rules == rule_headings(full), core_rules)

    core_sections = [(heading, lines) for heading, lines in sections(core) if RULE_HEADING.match(heading)]
    counts = {heading: sorted(examples(lines)) for heading, lines in core_sections}
    one_core = bool(counts) and all(ids == [f"R{heading[1]}-C"] for heading, ids in counts.items())
    case("core: exactly one core example per rule", one_core, counts)
    labels = [line for line in core.splitlines() if line.startswith(("Before", "After"))]
    case("core: no before-and-after pair", not labels, labels)
    words = len(core.split())
    case(f"core: at most {MAX_CORE_WORDS} words", 0 < words <= MAX_CORE_WORDS, f"{words} words")

    full_examples = all_examples(full)
    core_examples = all_examples(core)
    drift = [key for key, parts in core_examples.items() if parts.get("good") != full_examples.get(key, {}).get("good")]
    case("core: each example quote is the same in both files", bool(core_examples) and not drift, drift)

    problems: list[str] = []
    used: set[tuple[str, str, str]] = set()
    for key, parts in full_examples.items():
        for part in ("good", "after"):
            if part not in parts:
                continue
            allowed = ALLOWED.get(key, set())
            for finding in check_prose.check(f"{key}.md", parts[part], None):
                if finding.rule not in check_prose.HARD:
                    continue
                if (finding.rule, finding.detail) in allowed:
                    used.add((key, finding.rule, finding.detail))
                else:
                    problems.append(f"{key} {part}: {finding.rule} ({finding.detail})")
    case("full: each good passage and each after has no hard finding", bool(full_examples) and not problems, problems)
    unused = [(key, *entry) for key, entries in ALLOWED.items() for entry in entries if (key, *entry) not in used]
    case("full: each allow entry matches a finding", not unused, unused)
    case("core: the R5-C citation keeps its copyright holder", RUST_COPYRIGHT in core, RUST_COPYRIGHT)
    befores = [key for key, parts in full_examples.items() if "before" in parts and hard_findings(key, parts["before"])]
    case("full: the gate finds a hard fault in at least one before", bool(befores))

    rows = [line for line in full.splitlines() if line.startswith("|")]
    missing = [name for name in SOURCE_PROJECTS if not any(name in row for row in rows)]
    case("full: the sources table names each project", bool(rows) and not missing, missing)
    joined = " ".join(full.split())
    absent = [note for note in LICENSE_NOTES if note not in joined]
    case("full: the license notes stay with the quotes", not absent, absent)

    print("ALL PASS" if not failures else f"FAILURES: {failures}")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
