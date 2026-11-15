#!/usr/bin/env python3
"""Check that check_prose.py applies the two registers and finds ste_structural.py in lib/.

Each case runs the script as a subprocess. The run gets an empty HOME, so a copy of
ste_structural.py in the author's own ~/.claude cannot make a case pass.
"""

import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHECKER = ROOT / "skills" / "prose-gate" / "check_prose.py"

RULE_LINE = re.compile(r"^\S+:\d+  (\S+)  \(", re.MULTILINE)
SPLIT_MARK = "== READ AND JUDGE =="

# A sentence of 30 words with no other rule to break, as an explanation and as an instruction.
LONG_EXPLANATION = (
    "The scheduler stores every pending record in a shared table, and the table grows slowly over time"
    " because each record keeps a copy of its payload for the audit trail."
)
LONG_INSTRUCTION = (
    "Run the migration script on the staging host, then copy the resulting file to the shared drive,"
    " and send the team a short note that lists every table the script changed."
)
# The docstring opens with an imperative and holds 22 words in one sentence.
LONG_DOCSTRING = '"""Return the parsed value and then store the same value in the shared cache so that every later reader can find it."""'


@dataclass
class Case:
    name: str
    text: str
    exit_code: int
    hard: set[str] = field(default_factory=set)
    soft: set[str] = field(default_factory=set)
    absent: set[str] = field(default_factory=set)


CASES = [
    # The text holds a structural defect. Only ste_structural.py reports it.
    Case(
        "structural defect reported from lib/",
        "Each hook must run on the server, not only on the laptop.\n",
        1,
        hard={"NOT-JUST"},
    ),
    Case("long explanation is advisory", LONG_EXPLANATION + "\n", 0, soft={"LENGTH-READ"}, absent={"LENGTH"}),
    Case("long imperative is a violation", LONG_INSTRUCTION + "\n", 1, hard={"LENGTH"}, absent={"LENGTH-READ"}),
    Case("long sentence under a procedure heading", f"## Setup\n\n{LONG_EXPLANATION}\n", 1, hard={"LENGTH"}),
    Case("soft modal in an explanation is advisory", "A default would carry a credential.\n", 0, soft={"MODAL-READ"}, absent={"MODAL"}),
    Case("firm modal in an explanation is a violation", "You should restart the worker.\n", 1, hard={"MODAL"}),
    Case("soft modal in an instruction is a violation", "Run it and it would recover.\n", 1, hard={"MODAL"}, absent={"MODAL-READ"}),
    Case(
        "em dash in an explanation is advisory",
        "The cache — which holds every entry — expires after an hour.\n",
        0,
        soft={"EM-DASH-READ"},
        absent={"EM-DASH"},
    ),
    Case(
        "em dash in an instruction is a violation", "Run the build — then check the output.\n", 1, hard={"EM-DASH"}, absent={"EM-DASH-READ"}
    ),
    Case("semicolon in an explanation is a violation", "The cache expires; the queue drains.\n", 1, hard={"SEMICOLON"}),
    Case("pending is not a verb", "The commit runs even if there are pending reads.\n", 0, absent={"ING-VERB"}),
    Case(
        "-ing modifier after be is advisory",
        "The design and the plan are working documents.\n",
        0,
        soft={"ING-READ"},
        absent={"ING-VERB"},
    ),
    Case("progressive verb is a violation", "The worker is failing.\n", 1, hard={"ING-VERB"}, absent={"ING-READ"}),
    Case("progressive verb before a quote mark", 'The log says "the worker is failing" again.\n', 1, hard={"ING-VERB"}),
    Case("progressive verb with an object is a violation", "The hook is checking the queue.\n", 1, hard={"ING-VERB"}),
    Case("trailing -ing clause is a violation", "The hook runs first, ensuring the data stays valid.\n", 1, hard={"ING-VERB"}),
    Case("trailing -ing clause with a bare noun", "The worker retries, ensuring consistency.\n", 1, hard={"ING-VERB"}, absent={"ING-READ"}),
    Case("trailing -ing clause with a pronoun", "The worker retries, ensuring nothing breaks.\n", 1, hard={"ING-VERB"}),
    Case("progressive verb before code", "The loop is running `make`.\n", 1, hard={"ING-VERB"}, absent={"ING-READ"}),
    Case(
        "a parenthetical counts its words",
        "Run the job (on the staging host after the nightly backup finishes and the cache is cold) before noon today for the team.\n",
        1,
        hard={"LENGTH"},
    ),
    Case(
        "a fence nested in a list is code",
        "- a\n  - b\n    ```sh\n\n    The cache should be warm; it is simply robust.\n\n    ```\n",
        0,
        absent={"MODAL", "SEMICOLON", "SLOP"},
    ),
    Case(
        "a tab-indented fence is code",
        "- a\n\t```sh\n\tThe cache should be warm; it is simply robust.\n\t```\n",
        0,
        absent={"MODAL", "SEMICOLON", "SLOP"},
    ),
    Case(
        "a long fence holds a short fence",
        "The cache is per user.\n\n````markdown\n```suggestion\nx = 1; y = 2 should fail\n```\n````\n",
        0,
        absent={"MODAL", "SEMICOLON"},
    ),
    Case("noun opener is an explanation", "Name collisions would break the registry.\n", 0, soft={"MODAL-READ"}, absent={"MODAL"}),
    Case(
        "frontmatter is not prose",
        "---\nname: demo\ndescription: you should run it\n---\n\nThe cache is per user.\n",
        0,
        absent={"MODAL"},
    ),
    Case(
        "warning callout is a procedure",
        "> [!WARNING]\n> The command deletes the branch and every tag in the remote repository,"
        " so a mistake here can cost a full day of work to recover.\n",
        1,
        hard={"LENGTH"},
    ),
    Case(
        "a callout ends with the quote", "> [!WARNING]\n> Run it.\n" + LONG_EXPLANATION + "\n", 0, soft={"LENGTH-READ"}, absent={"LENGTH"}
    ),
    Case(
        "callout text on the opening line is a procedure",
        "> [!WARNING] Run the cleanup script, then remove every branch and tag that the migration created"
        " in the remote repository of the project today.\n",
        1,
        hard={"LENGTH"},
    ),
    Case(
        "a procedure reports a double modal once",
        "Run it, you should wait, and it would recover.\n",
        1,
        hard={"MODAL"},
    ),
    Case("a bold line does not set the register", f"**Setup**\n\n{LONG_EXPLANATION}\n", 0, soft={"LENGTH-READ"}, absent={"LENGTH"}),
]


def run(args: list[str], text: str = "") -> tuple[str, int]:
    with tempfile.TemporaryDirectory() as home:
        env = dict(os.environ, HOME=home)
        proc = subprocess.run(
            [sys.executable, str(CHECKER), *args],
            input=text,
            capture_output=True,
            text=True,
            env=env,
        )
    return proc.stdout + proc.stderr, proc.returncode


def rules_of(output: str) -> tuple[set[str], set[str]]:
    """Return the rules under VIOLATIONS and the rules under READ AND JUDGE."""
    hard_part, _, soft_part = output.partition(SPLIT_MARK)
    return set(RULE_LINE.findall(hard_part)), set(RULE_LINE.findall(soft_part))


def verdict(name: str, ok: bool, output: str) -> bool:
    print(f"{'ok ' if ok else 'FAIL'} {name}")
    if not ok:
        print(output)
    return ok


def main() -> None:
    results: list[bool] = []
    for case in CASES:
        output, code = run(["--stdin"], case.text)
        hard, soft = rules_of(output)
        ok = code == case.exit_code and case.hard <= hard and case.soft <= soft and not (case.absent & (hard | soft))
        results.append(verdict(case.name, ok, output))

    with tempfile.TemporaryDirectory() as folder:
        source = Path(folder) / "sample.py"
        source.write_text(f"def f() -> None:\n    {LONG_DOCSTRING}\n", encoding="utf-8")
        output, code = run(["--files", str(source)])
    hard, _ = rules_of(output)
    results.append(verdict("long docstring imperative is a violation", code == 1 and "LENGTH" in hard, output))

    failures = results.count(False)
    print("ALL PASS" if not failures else f"FAILURES: {failures}")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
