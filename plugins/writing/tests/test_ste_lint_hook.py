#!/usr/bin/env python3
"""Regression harness for ste-lint-hook.py."""

import json
import subprocess
import sys
from pathlib import Path

HOOK = Path(__file__).resolve().parent.parent / "hooks" / "ste-lint-hook.py"

DIRTY_PY = '''"""Return a robust handle to the store.

The caller should close the handle when it's done, e.g. inside a context
manager, because we leverage a pooled connection underneath.
"""


def open_store(name: str) -> Store:
    # The pool may return a stale socket, so it's crucial to ping first.
    return _POOL.acquire(name)
'''

CLEAN_PY = '''"""Return a handle to the store.

The caller must close the handle. The pool keeps the connection open until
then, and a leaked handle blocks the next writer.
"""


def open_store(name: str) -> Store:
    # A pooled socket can go stale, so ping before the first write.
    return _POOL.acquire(name)
'''

PRAGMA_ONLY_PY = """from foo import bar  # noqa: F401
x = 1  # type: ignore[assignment]
y = 2  # pyright: ignore[reportAny]
z = 3  # TODO: should probably rewrite this whole robust module, e.g. later on
w = 4  # eslint-disable-next-line no-console it's fine
"""

DIRTY_TS = """/**
 * Builds a robust client. The caller should await it, e.g. at startup.
 * It's a thin wrapper that leverages the shared pool underneath here.
 */
export function makeClient(url: string) {
  // See https://example.com/docs//pooling for why this is crucial.
  return new Client(url);
}
"""

CODE_NO_PROSE = """export function add(a: number, b: number): number {
  const shouldBeIgnored = a + b;
  const robustValue = shouldBeIgnored * 2;
  return robustValue;
}
"""

DIRTY_MD = """The retry mechanism is robust; it should handle a network blip seamlessly.
We have leveraged the existing pool, e.g. for the upload path, and it's fine.
"""

# A docstring with no banned word. It breaks the length and tense rules only, so
# it stays quiet under the restricted comment check set.
LONG_DOCSTRING_PY = '''"""Return the handle.

The pool has opened a connection for the caller and has kept that connection
alive across every retry the writer makes, which means the caller carries the
duty to close the handle before the next writer asks the pool for one.
"""


def open_store(name: str) -> Store:
    return _POOL.acquire(name)
'''

# Comment prose with no banned word and no length problem. The defect is shape.
SHAPE_PY = """def parse(raw: str) -> Node:
    # This is not a bug, not a typo, not a parser fault. Here is the reason.
    # The grammar generally accepts it, and the result is actually fine.
    return _parse(raw)
"""

SHAPE_MD = """It is not a bug, not a typo, not a syntax error. Here is the reason.
The formatter generally strips them, and the result is actually correct.
"""


# Hedge and intensifier words only, above the minimum word count. Both counts are advisory.
HEDGE_MD = (
    "The cache generally expires at night. The worker actually owns the queue. "
    "The log holds one line per job. The pool keeps one handle for each caller.\n"
)

# One explanation sentence of 30 words with a soft modal. Both counts are advisory.
EXPLANATION_MD = (
    "The cache would hold each result for a full day because the upstream service limits "
    "the request rate, and a slower refresh keeps the quota free for the jobs that need it.\n"
)

# A 22-word imperative is a procedure sentence, so the 20-word limit is hard.
LONG_IMPERATIVE_MD = (
    "Run the build script on the server and then copy the output files into the shared "
    "release directory before you close the terminal window.\n"
    "The cache holds the last result. The worker reads it at start. The queue stays small.\n"
)

COULD_PY = """def parse(raw: str) -> Node:
    # The parser could return a stale node here. The cache holds the last result.
    # The worker reads it at start. The queue stays small. The pool keeps one handle.
    return _parse(raw)
"""

SHOULD_PY = COULD_PY.replace("could", "should")

# Padding keeps each fixture above the hook's minimum word count.
PAD_PY = """    # The cache holds the last result. The worker reads it at start.
    # The queue stays small. The pool keeps one handle for each caller.
"""

# A descriptive comment line keeps a soft modal as advisory.
DESCRIPTIVE_COULD_PY = "def run(call: Call) -> None:\n    # Retry the call because it could time out.\n" + PAD_PY + "    call()\n"

# An instruction comment line is a procedure, so the soft modal stays banned.
IMPERATIVE_COULD_PY = "def run(call: Call) -> None:\n    # Run the retry, it could time out.\n" + PAD_PY + "    call()\n"


def run(path: str, content: str, tool: str = "Write") -> str:
    key = "content" if tool == "Write" else "new_string"
    event = {"tool_name": tool, "tool_input": {"file_path": path, key: content}}
    proc = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(event),
        capture_output=True,
        text=True,
    )
    if proc.stderr.strip():
        return "STDERR: " + proc.stderr.strip()
    out = proc.stdout.strip()
    if not out:
        return "quiet"
    return json.loads(out)["hookSpecificOutput"]["additionalContext"]


# (name, path, content, expected, names the report must carry, names it must not carry)
CASES = [
    ("dirty python docstring", "a.py", DIRTY_PY, "report", []),
    (
        "long docstring",
        "a.py",
        LONG_DOCSTRING_PY,
        "report",
        ["length_read", "perfect_tense"],
        ["sentence_over_limit"],
    ),
    (
        "explanation advisory only",
        "a.md",
        EXPLANATION_MD,
        "report",
        ["length_read", "modal_read", "Read again"],
        ["sentence_over_limit", "banned_modal"],
    ),
    ("long imperative", "a.md", LONG_IMPERATIVE_MD, "report", ["sentence_over_limit"], ["length_read"]),
    (
        "could in comment",
        "a.py",
        COULD_PY,
        "report",
        ["modal_read", "In an instruction, the approved modals"],
        ["banned_modal", "Approved modals are"],
    ),
    ("should in comment", "a.py", SHOULD_PY, "report", ["banned_modal"], ["modal_read"]),
    ("could in descriptive line", "a.py", DESCRIPTIVE_COULD_PY, "report", ["modal_read"], ["banned_modal"]),
    ("could in imperative line", "a.py", IMPERATIVE_COULD_PY, "report", ["banned_modal"], ["modal_read"]),
    (
        "shape defect in comment",
        "a.py",
        SHAPE_PY,
        "report",
        ["triple", "announce", "hedge", "intensifier"],
    ),
    (
        "shape defect in markdown",
        "a.md",
        SHAPE_MD,
        "report",
        ["triple", "announce", "hedge", "intensifier"],
    ),
    ("hedge is advisory", "a.md", HEDGE_MD, "report", ["Read again: hedge 1, intensifier 1"], ["Violations", "Shape defects"]),
    ("clean python", "a.py", CLEAN_PY, "quiet", []),
    ("pragmas only", "a.py", PRAGMA_ONLY_PY, "quiet", []),
    ("dirty typescript", "a.ts", DIRTY_TS, "report", []),
    ("code with no prose", "a.ts", CODE_NO_PROSE, "quiet", []),
    ("dirty markdown", "a.md", DIRTY_MD, "report", []),
    ("unhandled suffix", "a.json", DIRTY_MD, "quiet", []),
    ("agent instruction file", "CLAUDE.md", DIRTY_MD, "quiet", []),
    ("nested agent instruction file", "projects/x/AGENTS.md", DIRTY_MD, "quiet", []),
]


def main() -> None:
    failures = 0
    for name, path, content, expected, wanted, *rest in CASES:
        forbidden = rest[0] if rest else []
        got = run(path, content)
        kind = "quiet" if got == "quiet" else "report"
        missing = [w for w in wanted if w not in got]
        present = [f for f in forbidden if f in got]
        ok = kind == expected and not missing and not present
        mark = "ok " if ok else "FAIL"
        if not ok:
            failures += 1
        detail = "" if got == "quiet" else f"\n     {got}"
        if missing:
            detail = f"\n     MISSING {missing}{detail}"
        if present:
            detail = f"\n     FORBIDDEN {present}{detail}"
        print(f"{mark} {name:28s} expected={expected:6s} got={kind}{detail}")
    print("FAILURES:" if failures else "ALL PASS", failures or "")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
