#!/usr/bin/env python3
"""Fail when a file names a location that only the author has, or a private name.

A plugin runs on a teammate's machine. A path into the author's own `~/.claude` folders, or into
`/Users/`, does not exist there. A file that every user has, such as `~/.claude/settings.json`, can
appear. The path check reads only `plugins/`, and skips each `README.md`. A README tells a person
how to set up their own machine, so it can name that person's own files.

The private names are client, employer, and internal project names. A public list of them is
itself a leak, so they live in `tests/private-names.txt`, which git ignores. Each line of that file
is one regular expression. A blank line or a line that starts with `#` is skipped. The name check
reads every file that git tracks or can add. If the file is absent, as in CI, the name check has
no names and passes.

Run: uv run --no-project --python ">=3.14" tests/test_no_private_paths.py
"""

import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
NAMES_FILE = REPO / "tests" / "private-names.txt"

HOME = r"(?:~|\$HOME|\$\{HOME\})"
PRIVATE_PATH = re.compile(
    r"/Users/"
    rf"|{HOME}/\.claude/(?:skills/|hooks/|guides/|CLAUDE\.md|subagent-mistake-reporting\.md"
    r"|ste_structural\.py)"
)


def load_names(names_file: Path) -> re.Pattern[str] | None:
    """Join the patterns in `names_file` into one regex. With no patterns, return None."""
    if not names_file.is_file():
        return None
    lines = names_file.read_text(encoding="utf-8").splitlines()
    patterns = [line.strip() for line in lines if line.strip() and not line.startswith("#")]
    if not patterns:
        return None
    return re.compile("|".join(f"(?:{pattern})" for pattern in patterns))


def repo_files(repo: Path) -> list[Path]:
    """List each file that git tracks or can add. Ignored files, such as the names file, drop out."""
    out = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return sorted(repo / name for name in out.split("\0") if name)


def hits(repo: Path, names: re.Pattern[str] | None) -> list[str]:
    found: list[str] = []
    plugins = repo / "plugins"
    for path in repo_files(repo):
        if not path.is_file():
            continue
        check_paths = path.is_relative_to(plugins) and path.name != "README.md"
        if not check_paths and names is None:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for number, line in enumerate(text.splitlines(), start=1):
            if (check_paths and PRIVATE_PATH.search(line)) or (names and names.search(line)):
                found.append(f"{path.relative_to(repo)}:{number}: {line.strip()}")
    return found


def main() -> None:
    names = load_names(NAMES_FILE)
    if names is None:
        print(f"note: no {NAMES_FILE.name}, so the private name check has no names")
    found = hits(REPO, names)
    for hit in found:
        print(hit)
    if found:
        print("FAIL: private paths or names")
        sys.exit(1)
    print("ok: no private paths or names")


if __name__ == "__main__":
    main()
