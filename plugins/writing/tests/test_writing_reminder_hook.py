#!/usr/bin/env python3
"""Regression harness for writing-reminder-hook.py."""

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOOK = ROOT / "hooks" / "writing-reminder-hook.py"
sys.path.insert(0, str(ROOT / "skills" / "reviewing-edit-feedback"))
from extract_feedback import PASTE_BACK  # noqa: E402


def context(plugin_root: str) -> str:
    env = dict(os.environ, CLAUDE_PLUGIN_ROOT=plugin_root)
    proc = subprocess.run([sys.executable, str(HOOK)], input="{}", capture_output=True, text=True, env=env)
    if proc.returncode != 0 or proc.stderr.strip():
        return "STDERR: " + proc.stderr.strip()
    payload = json.loads(proc.stdout)["hookSpecificOutput"]
    if payload.get("hookEventName") != "UserPromptSubmit":
        return "WRONG EVENT: " + str(payload.get("hookEventName"))
    return str(payload["additionalContext"])


def main() -> None:
    got = context("/plugins/writing")
    checks = [
        (
            "reminder block",
            "<writing_standards>" in got and "</writing_standards>" in got,
        ),
        ("standards pointer", "/plugins/writing/standards.md" in got),
        ("short", len(got.split()) <= 140),
        ("paste-back rule", PASTE_BACK in got),
        ("core guide pointer", "/plugins/writing/guides/explanations-core.md" in got),
        ("full guide pointer", "/plugins/writing/guides/explanations.md" in got),
        ("names both registers", "procedure" in got and "explanation" in got),
        (
            "no explanation word limit",
            "Maximum 20 words for an instruction, 25 for an explanation" not in got,
        ),
    ]
    failures = 0
    for name, ok in checks:
        if not ok:
            failures += 1
        print(f"{'ok ' if ok else 'FAIL'} {name}")
    if failures:
        print(got)
    print("FAILURES:" if failures else "ALL PASS", failures or "")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
