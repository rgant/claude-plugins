#!/usr/bin/env python3
"""Check the evaluation harness offline: no key, no call, and no private data.

Run: uv run --no-project --python ">=3.14" plugins/writing/tests/test_explanation_eval.py
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "evals" / "explanation_eval.py"
sys.path.insert(0, str(SCRIPT.parent))
import explanation_eval  # noqa: E402

GUIDE = """# Guide

**R1-C.** Core.

> Core passage line one.
> Line two.

**R1-P1.** Public.

> Public passage.

**R1-B1.** Pair.

Before:

> Bad text.

After:

> Good after text.

**R2-B1.** Pair.

Before:

> Bad again.

After: see R2-C.

**R9-X1.** Not a good passage.

> Ignore me.
"""


def check(condition: bool, message: str) -> None:
    if not condition:
        sys.exit(f"FAIL: {message}")


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        guide = root / "guide.md"
        guide.write_text(GUIDE, encoding="utf-8")
        standards = root / "standards.md"
        standards.write_text("Standards.\n", encoding="utf-8")
        cases = root / "cases.json"
        cases.write_text(json.dumps([{"id": "c1", "context": "Ctx.", "sentence": "Sentence one."}]), encoding="utf-8")

        passages = {item.id: item.text for item in explanation_eval.good_passages(guide)}
        check(
            passages == {"R1-C": "Core passage line one. Line two.", "R1-P1": "Public passage.", "R1-B1": "Good after text."},
            f"passages: {passages}",
        )

        command = explanation_eval.build_command("sonnet", "SYSTEM")
        check(command[:3] == ["claude", "-p", "--bare"], f"command start: {command}")
        check(command[command.index("--system-prompt") + 1] == "SYSTEM", "system prompt not passed")
        check(command[command.index("--model") + 1] == "sonnet", "model not passed")

        env = {name: value for name, value in os.environ.items() if name != "ANTHROPIC_API_KEY"}
        args = [str(SCRIPT), "--cases", str(cases), "--old", str(standards), "--new", str(standards), "--guide", str(guide)]
        out = root / "out"
        missing = subprocess.run([*args, "--out", str(out)], env=env, capture_output=True, text=True, check=False)
        check(missing.returncode == 2 and "not set" in missing.stderr, f"no-key run: {missing.returncode} {missing.stderr}")
        check(not out.exists(), "the no-key run wrote output")

        dry = subprocess.run([*args, "--out", str(out), "--dry-run", "--seed", "1"], env=env, capture_output=True, text=True, check=False)
        check(dry.returncode == 0, f"dry run: {dry.stderr}")
        side = (out / "side-by-side.md").read_text(encoding="utf-8")
        key = (out / "key.md").read_text(encoding="utf-8")
        check("## c1" in side and "Sentence one." in side and "## R1-B1" in side, "side-by-side.md lacks an item")
        check("old standards" not in side.split("# Good passages")[1], "a passage got an old rewrite")
        check("| c1 |" in key, "key.md lacks the case")

        # A fake `claude` that returns an error reply, as a bad key does. The probe must stop the
        # run with a message, not a traceback.
        bin_dir = root / "bin"
        bin_dir.mkdir()
        fake = bin_dir / "claude"
        fake.write_text('#!/bin/sh\necho \'{"is_error": true, "result": "Invalid API key"}\'\n', encoding="utf-8")
        fake.chmod(0o755)
        bad_env = {**env, "ANTHROPIC_API_KEY": "not-a-key", "PATH": f"{bin_dir}{os.pathsep}{env.get('PATH', '')}"}
        probe = subprocess.run([*args, "--out", str(root / "probe")], env=bad_env, capture_output=True, text=True, check=False)
        check(probe.returncode == 1, f"probe failure exit: {probe.returncode}")
        check("Probe call failed" in probe.stderr and "Traceback" not in probe.stderr, f"probe failure stderr: {probe.stderr}")

        # A CLI that prints a list of events. The harness reads the event of type "result". This fake
        # answers CLEAN to the probe and a fixed rewrite to every case.
        events = [{"type": "system", "subtype": "init"}, {"type": "result", "is_error": False, "result": "CLEAN"}]
        fake.write_text(f"#!/bin/sh\ncat > /dev/null\necho '{json.dumps(events)}'\n", encoding="utf-8")
        listed_args = [*args, "--out", str(root / "listed"), "--seed", "1"]
        listed = subprocess.run(listed_args, env=bad_env, capture_output=True, text=True, check=False)
        check(listed.returncode == 0, f"event-list run: {listed.returncode} {listed.stderr}")
        check("> CLEAN" in (root / "listed" / "side-by-side.md").read_text(encoding="utf-8"), "event-list result not used")
        leak = [{"type": "result", "is_error": False, "result": "LEAK <writing_standards> Each sentence"}]
        fake.write_text(f"#!/bin/sh\ncat > /dev/null\necho '{json.dumps(leak)}'\n", encoding="utf-8")
        leaked = subprocess.run([*args, "--out", str(root / "leaked")], env=bad_env, capture_output=True, text=True, check=False)
        check(leaked.returncode == 1 and "Probe failed" in leaked.stderr, f"leak run: {leaked.returncode} {leaked.stderr}")
        check(not (root / "leaked").exists() or not any((root / "leaked").iterdir()), "the leak run wrote output")
    print("ok")


if __name__ == "__main__":
    main()
