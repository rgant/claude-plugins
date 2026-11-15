#!/usr/bin/env python3
"""Regression harness for agy-review.sh, with a fake agy on PATH.

The fake agy saves the workspace AGENTS.md and prints a result that the case sets. So the test
checks what the script gives the reviewer and how it reads the reply, with no model call.
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "skills" / "gemini-review" / "scripts" / "agy-review.sh"

FAKE_AGY = """#!/usr/bin/env bash
cp AGENTS.md "$FAKE_OUT/agents.md" 2>/dev/null || : >"$FAKE_OUT/agents.md"
printf '%s' "$FAKE_RESULT"
"""

FINDING = "1. severity: high\n   a.py:1 `x = 1`\n   The value is wrong.\n   Fix: use 2."


def result(response: str) -> str:
    return json.dumps(
        {
            "status": "SUCCESS",
            "response": response,
            "usage": {"input_tokens": 1, "output_tokens": 1},
            "duration_seconds": 1,
            "denied_actions": [],
        }
    )


def run(tmp: Path, response: str, standards: Path | None) -> tuple[int, str, str]:
    out = tmp / "out"
    out.mkdir(exist_ok=True)
    env = dict(
        os.environ,
        PATH=f"{tmp / 'bin'}{os.pathsep}{os.environ['PATH']}",
        FAKE_OUT=str(out),
        FAKE_RESULT=result(response),
        TMPDIR=str(tmp),
    )
    env.pop("AGY_REVIEW_GUIDE", None)
    env.pop("AGY_REVIEW_STANDARDS", None)
    if standards is not None:
        env["AGY_REVIEW_STANDARDS"] = str(standards)
    proc = subprocess.run(["bash", str(SCRIPT), "a.py"], cwd=tmp / "repo", capture_output=True, text=True, env=env)
    agents = (out / "agents.md").read_text() if (out / "agents.md").exists() else ""
    return proc.returncode, proc.stderr, agents


def main() -> None:
    failures = 0
    with tempfile.TemporaryDirectory() as name:
        tmp = Path(name)
        (tmp / "bin").mkdir()
        fake = tmp / "bin" / "agy"
        fake.write_text(FAKE_AGY)
        fake.chmod(0o755)
        repo = tmp / "repo"
        repo.mkdir()
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        (repo / "a.py").write_text("x = 1\n")
        (repo / "CLAUDE.md").write_text("Repo rule: keep it small.\n")
        standards = tmp / "standards.md"
        standards.write_text("Shared rule: lead with the outcome.\n")

        empty_code, empty_err, _ = run(tmp, "I read the review guide and the project rules.", None)
        none_code, _, _ = run(tmp, "No findings", None)
        finding_code, _, _ = run(tmp, FINDING, None)
        _, _, with_std = run(tmp, "No findings", standards)
        _, _, without_std = run(tmp, "No findings", None)

    checks = [
        ("reply with no review exits 2", empty_code == 2 and "no findings" in empty_err.lower()),
        ("No findings exits 0", none_code == 0),
        ("a finding exits 0", finding_code == 0),
        ("standards reach AGENTS.md", "Shared rule: lead with the outcome." in with_std and "Repo rule" in with_std),
        ("no standards without the variable", "Shared rule" not in without_std and "Repo rule" in without_std),
    ]
    for name, ok in checks:
        if not ok:
            failures += 1
        print(f"{'ok ' if ok else 'FAIL'} {name}")
    if failures:
        print("empty-reply stderr:", empty_err.strip()[-400:])
    print("FAILURES:" if failures else "ALL PASS", failures or "")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
