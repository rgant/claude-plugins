#!/usr/bin/env python3
"""Regression harness for statusline-command.sh."""

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "statusline-command.sh"
ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]|\x1b\([A-Z]")


def render(repo: Path, home: str | None = None) -> str:
    payload = {
        "model": {"display_name": "Opus"},
        "workspace": {"current_dir": str(repo)},
        "context_window": {
            "used_percentage": 42,
            "total_input_tokens": 1500,
            "total_output_tokens": 500,
        },
    }
    env = dict(os.environ, TERM=os.environ.get("TERM") or "xterm-256color")
    if home is not None:
        env["HOME"] = home
    proc = subprocess.run(
        ["bash", str(SCRIPT)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
    )
    if proc.returncode != 0:
        return "EXIT " + str(proc.returncode) + ": " + proc.stderr.strip()
    return ANSI.sub("", proc.stdout)


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "a" / "b" / "c" / "d"
        repo.mkdir(parents=True)
        subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
        got = render(repo)
        inside = render(repo, home=tmp)
        outside = render(repo, home="/nonexistent-home")
    checks = [
        ("model", "Opus" in got),
        ("branch", "(main" in got),
        ("context", "[ctx:42%]" in got),
        ("tokens", "[tok:2.0k]" in got),
        ("folder under home", inside.startswith("~/…/c/d")),
        ("folder outside home", outside.startswith("/…/c/d")),
    ]
    failures = 0
    for name, ok in checks:
        if not ok:
            failures += 1
        print(f"{'ok ' if ok else 'FAIL'} {name}")
    if failures:
        print(repr(got))
    print("FAILURES:" if failures else "ALL PASS", failures or "")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
