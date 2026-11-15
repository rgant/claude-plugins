#!/usr/bin/env python3
"""Run each command in hooks.json the way Claude Code runs it, through a shell.

The test catches a quoting error, a wrong path, or a launcher that cannot start. The plugin root
holds a space, because a teammate's home folder can hold one.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIRTY = (
    "You should run the tests before each release; it is a robust way to leverage the logs, "
    "ensuring the build passes. We have seen that a team may skip this step, and it might break later."
)

# (event, matcher tool, hook input, text the output must hold)
CASES = {
    "UserPromptSubmit": ({"prompt": "hello"}, "<writing_standards>"),
    "PostToolUse": ({"tool_name": "Write", "tool_input": {"file_path": "notes.md", "content": DIRTY}}, "STE check"),
    "SessionStart": ({"source": "startup"}, "writing:reviewing-edit-feedback"),
    "PreToolUse": (
        {"tool_name": "Bash", "session_id": "t", "tool_input": {"command": f'gh pr create --title "x" --body "{DIRTY}"'}},
        '"deny"',
    ),
}


def main() -> None:
    failures = 0
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "plugin root"
        shutil.copytree(ROOT, root, ignore=shutil.ignore_patterns("__pycache__", "tests"))
        hooks = json.loads((root / "hooks" / "hooks.json").read_text())["hooks"]
        matchers = [group.get("matcher") for group in hooks.get("SessionStart", [])]
        if matchers != ["startup|resume"]:
            failures += 1
            print(f"FAIL SessionStart matcher  got={matchers}")
        # A recent extraction time stops the SessionStart hook from starting a detached extraction,
        # which could still write to the temporary directory when the test removes it.
        store = Path(tmp) / "data" / "feedback"
        store.mkdir(parents=True)
        stamp = datetime.now(UTC).isoformat(timespec="seconds")
        (store / "reminder.json").write_text(json.dumps({"last_extract": stamp}), encoding="utf-8")
        env = dict(
            os.environ,
            CLAUDE_PLUGIN_ROOT=str(root),
            CLAUDE_PLUGIN_DATA=str(Path(tmp) / "data"),
            CLAUDE_CONFIG_DIR=str(Path(tmp) / "config"),
        )
        for event, (payload, wanted) in CASES.items():
            for group in hooks[event]:
                for hook in group["hooks"]:
                    proc = subprocess.run(
                        ["bash", "-c", hook["command"]],
                        input=json.dumps({"hook_event_name": event, **payload}),
                        capture_output=True,
                        text=True,
                        env=env,
                        timeout=hook.get("timeout", 60),
                    )
                    ok = proc.returncode == 0 and not proc.stderr.strip() and wanted in proc.stdout
                    if not ok:
                        failures += 1
                    print(f"{'ok ' if ok else 'FAIL'} {event}")
                    if not ok:
                        print(f"     exit={proc.returncode} stderr={proc.stderr.strip()[:300]} stdout={proc.stdout[:200]}")
    print("FAILURES:" if failures else "ALL PASS", failures or "")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
