#!/usr/bin/env python3
"""Fail when the shared CLAUDE.md, or a file it imports, names a guide that does not exist.

Claude Code reports no error for an `@` import of a missing file, and a pointer such as "read
`guides/tests.md`" is plain text. So a renamed guide drops out of every session with no warning,
and this test is the only check. Each reference resolves against the folder of the file that holds
it, as Claude Code resolves an import.

Run: uv run --no-project --python ">=3.14" tests/test_claude_md_references.py
"""

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SHARED = REPO / "claude-md" / "CLAUDE.md"

IMPORT = re.compile(r"^@(\S+)$")
POINTER = re.compile(r"`([^`\s]+\.md)`")


def references(text: str) -> list[str]:
    """Return the path of each `@` import line and each backticked path that ends in `.md`."""
    found: list[str] = []
    for line in text.splitlines():
        imported = IMPORT.match(line.strip())
        if imported:
            found.append(imported.group(1))
        else:
            found.extend(POINTER.findall(line))
    return found


def imports(text: str) -> list[str]:
    return [match.group(1) for line in text.splitlines() if (match := IMPORT.match(line.strip()))]


def missing(shared: Path) -> list[str]:
    """Check *shared* and each file it imports. Return each reference that names no file."""
    text = shared.read_text(encoding="utf-8")
    files = [shared] + [(shared.parent / path).resolve() for path in imports(text)]
    problems: list[str] = []
    for path in files:
        if not path.is_file():
            continue
        for reference in references(path.read_text(encoding="utf-8")):
            if not (path.parent / reference).resolve().is_file():
                problems.append(f"{path.relative_to(REPO)}: `{reference}` names no file")
    return problems


def main() -> None:
    failures: list[str] = []
    if references("Before you debug, read `a/b.md`.") != ["a/b.md"]:
        failures.append("references() missed a backticked pointer")
    if references("@../x/y.md") != ["../x/y.md"]:
        failures.append("references() missed an @ import")
    failures.extend(missing(SHARED))
    for failure in failures:
        print(f"FAIL {failure}")
    print("ALL PASS" if not failures else f"FAILURES: {len(failures)}")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
