#!/usr/bin/env python3
"""Regression harness for ste-gh-body-hook.py."""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HOOK_DIR = Path(__file__).resolve().parent.parent / "hooks"
HOOK = HOOK_DIR / "ste-gh-body-hook.py"
# One data folder for the whole run. The escape hatch case needs state that lasts across hook runs.
DATA = Path(tempfile.mkdtemp(prefix="ste-gh-body-test-"))
STATE = DATA / "ste-gh-body-state"

G = "gh"  # Each command is built from this name, so the file holds no literal gh command.


def run_raw(command: str, session: str = "t", data: Path | None = DATA) -> subprocess.CompletedProcess[str]:
    event = {
        "tool_name": "Bash",
        "session_id": session,
        "tool_input": {"command": command},
    }
    env = dict(os.environ)
    if data is None:
        env.pop("CLAUDE_PLUGIN_DATA", None)
    else:
        env["CLAUDE_PLUGIN_DATA"] = str(data)
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(event),
        capture_output=True,
        text=True,
        env=env,
    )


def run(command: str, session: str = "t", data: Path | None = DATA) -> str:
    proc = run_raw(command, session, data)
    if proc.stderr.strip():
        return "STDERR: " + proc.stderr.strip()
    out = proc.stdout.strip()
    if not out:
        return "pass"
    payload = json.loads(out)["hookSpecificOutput"]
    return "DENY" if "permissionDecision" in payload else "ALLOW+CTX"


def reason(command: str, session: str) -> str:
    """Return the denial reason, or an empty string when the hook did not deny."""
    out = run_raw(command, session).stdout.strip()
    if not out:
        return ""
    return json.loads(out)["hookSpecificOutput"].get("permissionDecisionReason", "")


DIRTY_HEREDOC = f"{G} pr create --body \"$(cat <<'EOF'\nThis should merge; it's robust, e.g. under load.\nEOF\n)\""
CLEAN_HEREDOC = f"{G} pr create --body \"$(cat <<'EOF'\nThe parser reads the manifest first. This order prevents a partial write.\nEOF\n)\""
LONG_ROW = (
    "| a very long table row that runs well past twenty five words and would otherwise trip"
    " the sentence length check every single time it appears | x |"
)
TABLE_ONLY = f"{G} pr comment 1 --body \"$(cat <<'EOF'\n| a | b |\n| --- | --- |\n{LONG_ROW}\nEOF\n)\""

A = "acli"  # same reason as G above

# A codeBlock holds code, not prose. A banned modal inside one must not deny.
ADF_CLEAN = {
    "type": "doc",
    "version": 1,
    "content": [
        {
            "type": "heading",
            "attrs": {"level": 3},
            "content": [{"type": "text", "text": "The gap"}],
        },
        {
            "type": "paragraph",
            "content": [
                {
                    "type": "text",
                    "text": "The worker reads the queue first. That order stops a ",
                },
                {"type": "text", "text": "double_write", "marks": [{"type": "code"}]},
                {"type": "text", "text": "."},
            ],
        },
        {
            "type": "codeBlock",
            "attrs": {"language": "python"},
            "content": [
                {
                    "type": "text",
                    "text": "# this should not be linted, e.g. here\nx = 1",
                }
            ],
        },
    ],
}
ADF_DIRTY = {
    "type": "doc",
    "version": 1,
    "content": [
        {
            "type": "paragraph",
            "content": [
                {
                    "type": "text",
                    "text": "The retry path is robust; it should hold under load.",
                }
            ],
        },
    ],
}
DEFINITION_DIRTY = {
    "projectKey": "PROJ",
    "type": "Task",
    "summary": "We should leverage a robust cache",
    "description": ADF_CLEAN,
}

TMP = Path(tempfile.mkdtemp(prefix="ste-acli-"))


def adf_path(name: str, payload: dict[str, object]) -> Path:
    path = TMP / name
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


CLEAN_FILE = adf_path("clean.json", ADF_CLEAN)

# A `gh api --input` review: the body and each inline comment carry prose. Suggestion code is not.
REVIEW_CLEAN = adf_path(
    "review-clean.json",
    {
        "event": "COMMENT",
        "body": "The parser reads the manifest first. It doesn't write a partial file.",
        "comments": [
            {
                "path": "a.py",
                "line": 3,
                "body": "Drop this line.\n\n```suggestion\nx = 1  # this should; maybe e.g. ok\n```\n",
            }
        ],
    },
)
REVIEW_DIRTY_BODY = adf_path(
    "review-dirty-body.json",
    {"event": "COMMENT", "body": "This may merge.", "comments": []},
)
REVIEW_DIRTY_COMMENT = adf_path(
    "review-dirty-comment.json",
    {
        "event": "COMMENT",
        "body": "The parser reads the manifest first.",
        "comments": [{"path": "a.py", "line": 3, "body": "This path is robust; keep it."}],
    },
)
# A suggestion that holds a triple backtick needs a longer fence. The fence closes only on a line of
# at least as many backticks, so the inner triple backticks stay code.
LONG_FENCE = (
    "````suggestion\nexport const FENCE_OPEN = /^```mermaid\\s*$/u;\n"
    "const document = parse('a.md', '```mermaid\\nflowchart LR\\n```');\n"
    "throw new Error('Mermaid could not start');\n````\n"
)
REVIEW_LONG_FENCE = adf_path(
    "review-long-fence.json",
    {
        "event": "COMMENT",
        "body": "The parser reads the manifest first.\n\n```tsx\nconst a = 1;\n```\n",
        "comments": [
            {"path": "a.ts", "line": 3, "body": LONG_FENCE},
            {
                "path": "b.ts",
                "line": 4,
                "body": "~~~suggestion\nconst b = 2; // this could fail\n~~~\n",
            },
        ],
    },
)
REVIEW_PROSE_AFTER_FENCE = adf_path(
    "review-prose-after-fence.json",
    {
        "event": "COMMENT",
        "body": "The parser reads the manifest first.",
        "comments": [
            {
                "path": "a.ts",
                "line": 3,
                "body": LONG_FENCE + "\nThis path is robust; keep it.\n",
            }
        ],
    },
)
DIRTY_FILE = adf_path("dirty.json", ADF_DIRTY)
DEFINITION_FILE = adf_path("definition.json", DEFINITION_DIRTY)

# `would` and a long sentence never deny, in an explanation or in a procedure step.
WOULD_EXPLANATION = (
    "The cache would expire after the nightly job finishes because the scheduler resets every key"
    " when the worker restarts and the old entries no longer match the new schema version."
)
SEMICOLON_EXPLANATION = "The cache expires after an hour; the worker then reloads it."
LONG_EXPLANATION = (
    "The cache expires after an hour because the worker reloads each key from the database when the"
    " entry goes stale and the scheduler then writes the new value back to the shared store for every"
    " later reader."
)
SHORT_STEPS = "1. Run the unit tests.\n2. Open the page.\n3. Check the log.\n"
LONG_STEP = "4. Run the full suite on the staging server and read the report for any failure in the cache layer or queue today.\n"
SHORT_STEP = "4. Run the full suite on the staging server.\n"


def pr_body(*parts: str) -> str:
    text = "\n".join(parts)
    return f"{G} pr create --title t --body \"$(cat <<'EOF'\n{text}\nEOF\n)\""


PR_WOULD = pr_body(WOULD_EXPLANATION)
PR_SEMICOLON = pr_body(SEMICOLON_EXPLANATION)
PR_LONG_STEP = pr_body(f"## Summary\n\n{LONG_EXPLANATION}\n\n## Test plan\n\n{SHORT_STEPS}{LONG_STEP}")
PR_SHORT_STEP = pr_body(f"## Summary\n\n{LONG_EXPLANATION}\n\n## Test plan\n\n{SHORT_STEPS}{SHORT_STEP}")
# An explanation that holds `would` and `should`. Only `should` is a violation.
PR_FIRM_AND_SOFT = pr_body("The cache would expire early. The worker should reload it.")
PR_PROCEDURE_WOULD = pr_body("Run the test so that it would pass.")
# A period inside a code span does not end a sentence, so the `should` in the span stays code.
PR_CODE_PERIOD = pr_body("The log prints `Done. You should retry` once at the end.")
LONG_SEMICOLON = (
    "The cache expires after an hour because the worker reloads each key from the database"
    " when the entry goes stale; the scheduler then writes the value back for every reader."
)
PR_LONG_SEMICOLON = pr_body(LONG_SEMICOLON)
# `ste_lint` drops a wholly bold line, so its `should` never reaches the count.
PR_BOLD_LEAD_IN = pr_body("**What should change**\nThe parser reads the manifest first.")
# A review can use a contraction, so the quote skips the first sentence.
REVIEW_CONTRACTION_SEMICOLON = f'{G} pr review 9 --comment --body "It doesn\'t replay. {SEMICOLON_EXPLANATION}"'

CASES = [
    ("dirty heredoc", DIRTY_HEREDOC, "a", "DENY"),
    ("clean heredoc", CLEAN_HEREDOC, "b", "pass"),
    (
        "escaped backslash ends the line",
        f"{G} pr view 1 \\\\\ncat <<'EOF'\nThis should merge; it's robust.\nEOF\n",
        "esc",
        "pass",
    ),
    ("heredoc after a line continuation", DIRTY_HEREDOC.replace("pr create --body", "pr create --title x \\\n  --body"), "cont", "DENY"),
    (
        "api body dirty",
        f'{G} api repos/o/r/pulls/1/reviews -f body="The retry path is robust."',
        "c",
        "DENY",
    ),
    ("api read-only", f"{G} api repos/o/r/pulls/1", "d", "pass"),
    ("pr list", f"{G} pr list", "e", "pass"),
    ("non-gh command", "npx nx run workspace:check", "f", "pass"),
    (
        "pr review clean",
        f'{G} pr review 9 --approve --body "The migration runs before the index build. That order avoids a lock."',
        "g",
        "pass",
    ),
    ("table rows stripped", TABLE_ONLY, "h", "pass"),
    ("pr edit no body", f"{G} pr edit 5 --add-label bug", "i", "pass"),
    (
        "short body, modal",
        f'{G} pr comment 5 --body "This may be split."',
        "j",
        "DENY",
    ),
    ("comment can use should", f'{G} pr comment 5 --body "This should be split."', "j2", "pass"),
    ("comment instruction keeps should ban", f'{G} pr comment 5 --body "Run it and you should see a pass."', "j3", "DENY"),
    ("comment can use present perfect", f'{G} pr comment 5 --body "I have requested edit access."', "j4", "pass"),
    ("pr body present perfect", pr_body("The team has built the tests."), "j5", "DENY"),
    ("pr body past perfect", pr_body("The team had built the tests."), "j6", "pass"),
    ("pr body unreal past", pr_body("The variables would have been documented in the first PR."), "j7", "pass"),
    ("pr body negated unreal past", pr_body("The variables would not have been documented in the first PR."), "j8", "pass"),
    ("pr body noun after has", pr_body("The service has speed limits."), "j9", "pass"),
    ("pr body adverb in present perfect", pr_body("The team has already built the image."), "j11", "DENY"),
    ("pr body modal and adverb before have", pr_body("The tool would also have been slow."), "j12", "pass"),
    ("comment instruction keeps perfect ban", f'{G} pr comment 5 --body "Install the tool that has been built."', "j13", "DENY"),
    ("pr body procedure past perfect", pr_body("## Test plan\n\n1. Run the suite after you had built the image.\n"), "j10", "DENY"),
    (
        "acli search",
        f'{A} jira workitem search --jql "project = PROJ" --json',
        "k",
        "pass",
    ),
    (
        "acli transition",
        f'{A} jira workitem transition --key PROJ-1 --status "In Review" --yes',
        "l",
        "pass",
    ),
    (
        "acli summary dirty",
        f'{A} jira workitem create -p PROJ -t Task -s "We should leverage this"',
        "m",
        "DENY",
    ),
    (
        "acli summary clean",
        f'{A} jira workitem create -p PROJ -t Task -s "Move the stages onto the worker"',
        "n",
        "pass",
    ),
    (
        "acli description dirty",
        f'{A} jira workitem edit --key PROJ-1 -d "The path is robust; it should hold." --yes',
        "o",
        "DENY",
    ),
    (
        "acli adf file clean",
        f'{A} jira workitem create -p PROJ -t Task -s "Read the queue first" --description-file {CLEAN_FILE}',
        "p",
        "pass",
    ),
    (
        "acli adf file dirty",
        f'{A} jira workitem create -p PROJ -t Task -s "Read the queue first" --description-file {DIRTY_FILE}',
        "q",
        "DENY",
    ),
    (
        "acli definition dirty",
        f"{A} jira workitem create --from-json {DEFINITION_FILE}",
        "r",
        "DENY",
    ),
    (
        "acli comment dirty",
        f'{A} jira workitem comment create --key PROJ-1 --body "This should be retried, e.g. twice."',
        "s",
        "DENY",
    ),
    (
        "review contraction",
        f'{G} pr review 9 --request-changes --body "The grader doesn\'t match a whole name. Fix it first."',
        "u",
        "pass",
    ),
    (
        "api review contraction",
        f'{G} api -X POST repos/o/r/pulls/1/reviews -f body="It doesn\'t replay. Re-record it."',
        "v",
        "pass",
    ),
    (
        "issue comment contraction",
        f'{G} issue comment 3 --body "It doesn\'t replay."',
        "w",
        "pass",
    ),
    (
        "pr create contraction",
        f'{G} pr create --title t --body "It doesn\'t replay."',
        "x",
        "DENY",
    ),
    (
        "review still blocks modal",
        f'{G} pr review 9 --comment --body "This may not merge yet."',
        "y",
        "DENY",
    ),
    (
        "api input clean",
        f"{G} api -X POST repos/o/r/pulls/1/reviews --input {REVIEW_CLEAN}",
        "aa",
        "pass",
    ),
    (
        "api input dirty body",
        f"{G} api -X POST repos/o/r/pulls/1/reviews --input {REVIEW_DIRTY_BODY}",
        "ab",
        "DENY",
    ),
    (
        "api input dirty comment",
        f"{G} api -X POST repos/o/r/pulls/1/reviews --input {REVIEW_DIRTY_COMMENT}",
        "ac",
        "DENY",
    ),
    (
        "api input long fence",
        f"{G} api -X POST repos/o/r/pulls/1/reviews --input {REVIEW_LONG_FENCE}",
        "af",
        "pass",
    ),
    (
        "api input prose after fence",
        f"{G} api -X POST repos/o/r/pulls/1/reviews --input {REVIEW_PROSE_AFTER_FENCE}",
        "ag",
        "DENY",
    ),
    (
        "api input stdin",
        f"{G} api -X POST repos/o/r/pulls/1/reviews --input -",
        "ad",
        "pass",
    ),
    (
        "api input pr create contraction",
        f"{G} api -X POST repos/o/r/pulls --input {REVIEW_CLEAN}",
        "ae",
        "DENY",
    ),
    ("explanation would, long", PR_WOULD, "ba", "pass"),
    ("explanation semicolon", PR_SEMICOLON, "bb", "DENY"),
    ("long procedure step passes", PR_LONG_STEP, "bc", "pass"),
    ("procedure would passes", PR_PROCEDURE_WOULD, "bf", "pass"),
    ("period inside a code span", PR_CODE_PERIOD, "bg", "pass"),
    ("bold lead-in line", PR_BOLD_LEAD_IN, "bh", "pass"),
    ("same body, short step", PR_SHORT_STEP, "bd", "pass"),
    ("explanation should", PR_FIRM_AND_SOFT, "be", "DENY"),
    (
        "acli link",
        f"{A} jira workitem link create --out PROJ-1 --in PROJ-2 --type Blocks --yes",
        "t",
        "pass",
    ),
]


def main() -> None:
    failures = 0
    for name, command, session, expected in CASES:
        got = run(command, session)
        mark = "ok " if got == expected else "FAIL"
        if got != expected:
            failures += 1
        print(f"{mark} {name:22s} expected={expected:6s} got={got}")

    # A message can use `should`, so a denial for `may` quotes `may` alone.
    quoted = reason(f'{G} pr comment 5 --body "This should merge. It may break the build."', "quote-modal")
    ok = "banned_modal 1 (may)" in quoted
    mark = "ok " if ok else "FAIL"
    if not ok:
        failures += 1
    print(f"{mark} message quotes only the denied modal  got={quoted[:160]!r}")

    hatch = [run(DIRTY_HEREDOC, "z") for _ in range(4)]
    expected_hatch = ["DENY", "DENY", "ALLOW+CTX", "DENY"]
    mark = "ok " if hatch == expected_hatch else "FAIL"
    if hatch != expected_hatch:
        failures += 1
    print(f"{mark} escape hatch          expected={expected_hatch} got={hatch}")

    # An advisory-only body resets the strike count, like a clean body.
    sequence = [PR_SEMICOLON, PR_SEMICOLON, PR_WOULD, PR_SEMICOLON, PR_SEMICOLON, PR_SEMICOLON]
    got_seq = [run(command, "strike-reset") for command in sequence]
    expected_seq = ["DENY", "DENY", "pass", "DENY", "DENY", "ALLOW+CTX"]
    mark = "ok " if got_seq == expected_seq else "FAIL"
    if got_seq != expected_seq:
        failures += 1
    print(f"{mark} advisory resets strikes expected={expected_seq} got={got_seq}")

    checks = {
        "reason quotes should": "should" in reason(PR_FIRM_AND_SOFT, "r4"),
        "reason leaves out an explanation would": "would" not in reason(PR_FIRM_AND_SOFT, "r5"),
        "reason quotes the first flagged sentence": (f'First flagged sentence: "{SEMICOLON_EXPLANATION}"' in reason(PR_SEMICOLON, "r1")),
        "reason quotes past an exempt contraction": (
            f'First flagged sentence: "{SEMICOLON_EXPLANATION}"' in reason(REVIEW_CONTRACTION_SEMICOLON, "r2")
        ),
        "reason cuts a long quote": (
            LONG_SEMICOLON[:60] in (long := reason(PR_LONG_SEMICOLON, "r3")) and LONG_SEMICOLON not in long and '..."' in long
        ),
        "reason gives no length limit": "limit is 20" not in reason(PR_SEMICOLON, "r6"),
    }
    for name, passed in checks.items():
        if not passed:
            failures += 1
        print(f"{'ok ' if passed else 'FAIL'} {name}")

    state_files = sorted(p.name for p in STATE.glob("*"))
    stray = HOOK_DIR / ".state"
    ok = bool(state_files) and not stray.exists()
    if not ok:
        failures += 1
    print(f"{'ok ' if ok else 'FAIL'} state in CLAUDE_PLUGIN_DATA  files={state_files} stray={stray.exists()}")

    unset = run(DIRTY_HEREDOC, "u", data=None)
    ok = unset.startswith("STDERR:") and "CLAUDE_PLUGIN_DATA" in unset and not stray.exists()
    if not ok:
        failures += 1
    print(f"{'ok ' if ok else 'FAIL'} no CLAUDE_PLUGIN_DATA      got={unset}")

    print("FAILURES:" if failures else "ALL PASS", failures or "")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
