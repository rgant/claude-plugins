#!/usr/bin/env python3
"""PreToolUse hook. Blocks a `gh` or `acli` command whose body breaks ASD-STE100.

`ste-lint-hook.py` covers markdown that Write and Edit produce. It cannot see a
PR body, an issue body, a review body, or a Jira description, because those
travel through Bash to `gh` and to `acli`. This hook closes that gap.

A Jira body travels as Atlassian Document Format. `lib/bodies.py` reads the text
nodes out of the ADF tree, so the linter never sees the JSON scaffolding.

The hook denies instead of reporting. A posted body is public and costs more to
correct than a retry. ste_lint.py is a regex pass, so the hook strips tables and
code first. A PR body or an issue body is mostly explanation. The hook denies only on a rule that
is hard in both registers. `would`, `could`, `might`, and a long sentence never deny, whatever
the register of the sentence. A body that has advisory counts only passes in silence, because a
note cannot change a body that is posted.

Escape hatch: after MAX_STRIKES consecutive denials in one session, the hook
lets the command through and says so. A clean check resets the count.
"""

import json
import os
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
from bodies import ACLI_WRITE, GH_WRITE, MESSAGE_WRITE, collect_bodies, collect_jira_bodies, prepare
from register import classify, firm_modals
from ste_lint import (
    CONTRACTION,
    ING_CLAUSE,
    LATIN,
    PERFECT,
    PERFECT_ANY,
    SLOP,
    lint,
    strip_code,
)

# The checks that deny. Each one is hard in both registers. `banned_modal` counts `should` and
# `may` only. `synonym_rotation` fires on correct English, so it never denies.
BLOCKING = (
    "banned_modal",
    "semicolon",
    "contraction",
    "latin_abbrev",
    "slop_word",
    "ing_clause",
    "perfect_tense",
)

# The longest part of the first flagged sentence that a denial quotes.
QUOTE_LIMIT = 120

# The patterns that find the words a denial quotes. `blocking_hits` adds the modal and perfect
# patterns for each sentence, because those depend on the register of the sentence.
EXAMPLE_PATTERNS = {
    "contraction": CONTRACTION,
    "latin_abbrev": LATIN,
    "slop_word": SLOP,
    "ing_clause": ING_CLAUSE,
}

# A plugin update replaces the plugin folder, so the strike state lives in the plugin data folder.
_DATA = os.environ.get("CLAUDE_PLUGIN_DATA", "")
STATE_DIR = Path(_DATA) / "ste-gh-body-state" if _DATA else None
MAX_STRIKES = 2
STANDARDS = Path(__file__).resolve().parent.parent / "standards.md"


@dataclass
class Hits:
    """The denying checks that a body breaks."""

    counts: dict[str, int] = field(default_factory=dict)
    # The words that broke each check, in order, as the denial quotes them.
    words: dict[str, list[str]] = field(default_factory=dict)
    first: str = ""


def blocking_hits(text: str, *, message: bool) -> Hits:
    """Count the denying checks in *text*, with the words and the first sentence that break them.

    A *message* between people can use contractions, so they do not count in one. An explanation in
    a message can also use the present perfect and `should`. Each word comes from a sentence that
    the check counts, so a denial never quotes a word that the rules allow.
    """
    hits = Hits()
    seen: dict[str, set[str]] = {}
    for sentence in classify(text):
        stripped = strip_code(sentence.text)
        register = "procedural" if sentence.procedural else "descriptive"
        violations = lint(sentence.text, register)["violations"]
        found = {name: violations.get(name, 0) for name in BLOCKING}
        modals = firm_modals(message=message, procedural=sentence.procedural)
        patterns = {
            **EXAMPLE_PATTERNS,
            "banned_modal": modals,
            "perfect_tense": PERFECT_ANY if sentence.procedural else PERFECT,
        }
        found["banned_modal"] = len(modals.findall(stripped))
        if message:
            found["contraction"] = 0
            if not sentence.procedural:
                found["perfect_tense"] = 0
        for name, number in found.items():
            if not number:
                continue
            hits.counts[name] = hits.counts.get(name, 0) + number
            hits.first = hits.first or sentence.text
            if name in patterns:
                words = hits.words.setdefault(name, [])
                lowered = seen.setdefault(name, set())
                for match in patterns[name].finditer(stripped):
                    word = match.group(0).strip()
                    if word and word.lower() not in lowered:
                        lowered.add(word.lower())
                        words.append(word)
    return hits


def examples(words: list[str]) -> str:
    return f" ({', '.join(words[:4])})" if words else ""


def strike_file(session: str, tool: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_-]", "_", session)[:64] or "nosession"
    return STATE_DIR / f"{tool}-{safe}.json"


def read_strikes(path: Path) -> int:
    try:
        return int(json.loads(path.read_text(encoding="utf-8")).get("strikes", 0))
    except OSError, ValueError, TypeError:
        return 0


def prune_state(keep_days: int = 7) -> None:
    """Drop strike files from sessions that ended long ago."""
    cutoff = time.time() - keep_days * 86400
    try:
        for stale in [*STATE_DIR.glob("gh-*.json"), *STATE_DIR.glob("acli-*.json")]:
            if stale.stat().st_mtime < cutoff:
                stale.unlink()
    except OSError:
        pass


def write_strikes(path: Path, count: int) -> None:
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"strikes": count}), encoding="utf-8")
        prune_state()
    except OSError:
        pass


def build_reason(hits: Hits, tool: str) -> str:
    counts = ", ".join(f"{name} {number}{examples(hits.words.get(name, []))}" for name, number in sorted(hits.counts.items()))
    first = hits.first
    quoted = first if len(first) <= QUOTE_LIMIT else first[:QUOTE_LIMIT].rstrip() + "..."
    lines = [
        f"STE check on the body you passed to {tool}. The command did not run.",
        f"Violations: {counts}.",
        f'First flagged sentence: "{quoted}"',
    ]
    lines.append(
        f"Rewrite the body to the standards in {STANDARDS}. "
        f"Show the corrected text to the user and get approval before you call {tool} again."
    )
    return " ".join(lines)


def emit(payload: dict[str, object]) -> None:
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", **payload}}))


def main() -> None:
    try:
        event = json.load(sys.stdin)
    except json.JSONDecodeError, UnicodeDecodeError:
        return
    if not isinstance(event, dict) or event.get("tool_name") != "Bash":
        return

    tool_input = event.get("tool_input")
    if not isinstance(tool_input, dict):
        return
    command = tool_input.get("command")
    if not isinstance(command, str):
        return
    if GH_WRITE.search(command):
        tool, bodies = "gh", collect_bodies(command)
    elif ACLI_WRITE.search(command):
        tool, bodies = "acli", collect_jira_bodies(command)
    else:
        return
    if not bodies:
        return
    if STATE_DIR is None:
        print(
            "ste-gh-body-hook: CLAUDE_PLUGIN_DATA is not set, so the body check did not run.",
            file=sys.stderr,
        )
        return

    text = prepare("\n\n".join(bodies))
    hits = blocking_hits(text, message=bool(MESSAGE_WRITE.search(command)))

    path = strike_file(str(event.get("session_id", "")), tool)
    if not hits.counts:
        write_strikes(path, 0)
        return

    strikes = read_strikes(path) + 1
    if strikes > MAX_STRIKES:
        write_strikes(path, 0)
        emit(
            {
                "additionalContext": (
                    f"STE check still reports {sum(hits.counts.values())} violations in this {tool} body. "
                    f"The hook allowed the command after {MAX_STRIKES} denials. Tell the user."
                ),
            }
        )
        return

    write_strikes(path, strikes)
    emit(
        {
            "permissionDecision": "deny",
            "permissionDecisionReason": build_reason(hits, tool),
        }
    )


if __name__ == "__main__":
    main()
