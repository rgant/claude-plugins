#!/usr/bin/env python3
"""Compare rewrites made under the old and the new writing standards. Rob runs this by hand.

For each case, the harness calls `claude -p --bare` twice. One call gets the old standards as the
system prompt, and the other gets the new standards. `side-by-side.md` shows the two rewrites as A
and B, in a random order per case. `key.md` says which standards made A and B. Read the rewrites
first, then open the key.

The harness also sends each good passage from the explanation guide through the new call. The
output shows each passage next to its rewrite, so a reader can see whether the meaning held.

`--bare` reads no credential except `ANTHROPIC_API_KEY`. If that variable is not set, the harness
stops before the first call. `--bare` skips hooks and CLAUDE.md files, but it still lists the
installed plugins, so `--tools ""` and `--disable-slash-commands` keep their skills out of reach.
The first call of a real run is a leak probe. It asks the model whether any text in its context
holds a marker of the writing standards: the `writing_standards` reminder tag or "ASD-STE100". A
hook or a CLAUDE.md import would carry one. If the reply is not "CLEAN", the harness stops before
any case runs.

A failed call does not stop the run. The harness keeps every other result and lists each failure.
It rewrites both output files after each call, so a stopped run keeps its results.

`--dry-run` makes no call and needs no key. It writes the same files with placeholder rewrites.

The harness has no flag that limits the number of cases. For a smoke run, pass a `--cases` file
with a few cases and a `--guide` file with one section of the guide.

Run: ANTHROPIC_API_KEY=<key> uv run --no-project --python ">=3.14" plugins/writing/evals/explanation_eval.py
     --cases PATH --old PATH --out DIR [--new PATH ...] [--guide PATH] [--model NAME] [--seed N]
"""

import argparse
import json
import os
import random
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

WRITING = Path(__file__).resolve().parent.parent
DEFAULT_GUIDE = WRITING / "guides" / "explanations.md"
DEFAULT_NEW = [WRITING / "standards.md", DEFAULT_GUIDE]
KEY_VARIABLE = "ANTHROPIC_API_KEY"
PROBE_PROMPT = (
    "Look at everything in your context besides this system prompt. If any text contains the tag "
    "writing_standards or the phrase ASD-STE100, reply LEAK followed by the first 15 words of that "
    "text. Otherwise reply CLEAN."
)
PROBE_USER = "Go."
PROBE_REPLY = "CLEAN"
CALL_TIMEOUT_SECONDS = 300

REWRITE_REQUEST = (
    "Rewrite the text below. Keep its facts and its meaning. Apply your writing standards. "
    "Reply with the rewritten text only.\n\nContext: {context}\n\nText:\n{text}\n"
)
PASSAGE_CONTEXT = "A passage from a style guide."

EXAMPLE_ID = re.compile(r"^\*\*(R\d-[A-Z0-9]+)\.\*\*")
GOOD_ID = re.compile(r"^R\d-(?:C|P\d+)$")
BEFORE_AFTER_ID = re.compile(r"^R\d-B\d+$")


@dataclass
class Item:
    """One text to rewrite. A case gets two rewrites. A good passage gets one, from the new call."""

    id: str
    kind: str  # "case" or "passage"
    context: str
    text: str
    old: str | None = None
    new: str | None = None


def read_blockquote(lines: list[str], start: int) -> str | None:
    """Return the first blockquote at or after `start`, joined into one line. Stop at a heading."""
    quote: list[str] = []
    for line in lines[start:]:
        if line.startswith(">"):
            quote.append(line[1:].strip())
        elif quote:
            break
        elif line.startswith("#"):
            break
    return " ".join(quote) if quote else None


def good_passages(guide: Path) -> list[Item]:
    """Collect each core quote, each `-P` quote, and each "After" quote of the guide."""
    lines = guide.read_text(encoding="utf-8").splitlines()
    items: list[Item] = []
    for index, line in enumerate(lines):
        match = EXAMPLE_ID.match(line)
        if not match:
            continue
        example = match.group(1)
        start = index + 1
        if BEFORE_AFTER_ID.match(example):
            after = next((i for i in range(start, len(lines)) if lines[i] == "After:" or EXAMPLE_ID.match(lines[i])), None)
            if after is None or lines[after] != "After:":
                continue
            start = after + 1
        elif not GOOD_ID.match(example):
            continue
        quote = read_blockquote(lines, start)
        if quote:
            items.append(Item(example, "passage", PASSAGE_CONTEXT, quote))
    return items


def load_cases(path: Path) -> list[Item]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [Item(case["id"], "case", case["context"], case["sentence"]) for case in raw]


def build_command(model: str, system_prompt: str) -> list[str]:
    """Build the `claude` command. The user prompt goes in on stdin, because `--tools` takes many values."""
    return [
        "claude",
        "-p",
        "--bare",
        "--model",
        model,
        "--system-prompt",
        system_prompt,
        "--tools",
        "",
        "--disable-slash-commands",
        "--no-session-persistence",
        "--output-format",
        "json",
    ]


def call_claude(model: str, system_prompt: str, user_prompt: str) -> str:
    """Run one call and return the reply text. Raise RuntimeError on any failure."""
    try:
        done = subprocess.run(
            build_command(model, system_prompt),
            input=user_prompt,
            capture_output=True,
            text=True,
            timeout=CALL_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise RuntimeError(f"could not run claude: {error}") from error
    try:
        output = json.loads(done.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError(f"exit {done.returncode}, output is not JSON: {done.stderr.strip()[:300]}") from error
    # One CLI version prints one result object. Another prints a list of events, and the result is
    # the event of type "result".
    if isinstance(output, list):
        reply = next((event for event in reversed(output) if isinstance(event, dict) and event.get("type") == "result"), None)
    else:
        reply = output
    if not isinstance(reply, dict) or reply.get("is_error") or not isinstance(reply.get("result"), str):
        raise RuntimeError(f"exit {done.returncode}, error reply: {str(reply)[:300]}")
    return reply["result"].strip()


def run_probe(model: str) -> None:
    """Stop the run if a call fails or its context holds the writing standards."""
    try:
        reply = call_claude(model, PROBE_PROMPT, PROBE_USER)
    except RuntimeError as error:
        sys.exit(f"Probe call failed: {error}. No case ran.")
    if reply.strip(" \t\n.!\"'`*") != PROBE_REPLY:
        sys.exit(f"Probe failed. Expected {PROBE_REPLY!r}, got {reply[:200]!r}. No case ran.")


def render(items: list[Item], rng_orders: dict[str, bool]) -> tuple[str, str]:
    """Return the text of side-by-side.md and key.md. `rng_orders[id]` is True when A is the old rewrite."""
    side = ["# Side by side", "", "Read each pair, then open `key.md` to see which standards made A and B.", ""]
    key = ["# Key", "", "| Case | A | B |", "| --- | --- | --- |"]
    passages = [item for item in items if item.kind == "passage"]
    for item in (i for i in items if i.kind == "case"):
        old_first = rng_orders[item.id]
        old, new = item.old or "(no rewrite)", item.new or "(no rewrite)"
        a, b = (old, new) if old_first else (new, old)
        side += [
            f"## {item.id}",
            "",
            f"Context: {item.context}",
            "",
            "Original:",
            "",
            quote(item.text),
            "",
            "A:",
            "",
            quote(a),
            "",
            "B:",
            "",
            quote(b),
            "",
        ]
        key.append(f"| {item.id} | {'old' if old_first else 'new'} | {'new' if old_first else 'old'} |")
    side += ["# Good passages, rewritten under the new standards", ""]
    for item in passages:
        side += [f"## {item.id}", "", "Original:", "", quote(item.text), "", "Rewrite:", "", quote(item.new or "(no rewrite)"), ""]
    return "\n".join(side), "\n".join(key) + "\n"


def quote(text: str) -> str:
    return "\n".join(f"> {line}" if line else ">" for line in text.splitlines()) or ">"


def write_outputs(out: Path, items: list[Item], orders: dict[str, bool]) -> None:
    side, key = render(items, orders)
    (out / "side-by-side.md").write_text(side, encoding="utf-8")
    (out / "key.md").write_text(key, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--cases", type=Path, required=True, help="JSON list of {id, context, sentence}")
    parser.add_argument("--old", type=Path, required=True, help="the old standards file")
    parser.add_argument("--new", type=Path, nargs="+", default=DEFAULT_NEW, help="files joined into the new system prompt")
    parser.add_argument("--guide", type=Path, default=DEFAULT_GUIDE, help="the guide that holds the good passages")
    parser.add_argument("--out", type=Path, required=True, help="output folder")
    parser.add_argument("--model", default="sonnet")
    parser.add_argument("--seed", type=int, default=None, help="seed for the A/B order")
    parser.add_argument("--dry-run", action="store_true", help="make no call and write placeholder rewrites")
    args = parser.parse_args()

    if not args.dry_run:
        if not os.environ.get(KEY_VARIABLE):
            print(f"{KEY_VARIABLE} is not set. `--bare` reads no other credential. The run stops before the first call.", file=sys.stderr)
            return 2
        if shutil.which("claude") is None:
            print("The `claude` command is not on PATH.", file=sys.stderr)
            return 2

    old_prompt = args.old.read_text(encoding="utf-8")
    new_prompt = "\n\n".join(path.read_text(encoding="utf-8") for path in args.new)
    items = load_cases(args.cases) + good_passages(args.guide)
    rng = random.Random(args.seed)
    orders = {item.id: rng.random() < 0.5 for item in items if item.kind == "case"}
    args.out.mkdir(parents=True, exist_ok=True)

    if args.dry_run:
        print("Command shape:", [part if len(part) < 40 else f"<{len(part)} characters>" for part in build_command(args.model, new_prompt)])
    else:
        run_probe(args.model)
        print("Probe passed.", file=sys.stderr)

    failures: list[str] = []
    for position, item in enumerate(items, start=1):
        request = REWRITE_REQUEST.format(context=item.context, text=item.text)
        calls = [("new", new_prompt)] if item.kind == "passage" else [("old", old_prompt), ("new", new_prompt)]
        for label, prompt in calls:
            if args.dry_run:
                reply = f"[dry-run placeholder, {label} standards]"
            else:
                try:
                    reply = call_claude(args.model, prompt, request)
                except RuntimeError as error:
                    failures.append(f"{item.id} ({label}): {error}")
                    reply = f"(call failed: {error})"
            setattr(item, label, reply)
        write_outputs(args.out, items, orders)
        print(f"[{position}/{len(items)}] {item.id}", file=sys.stderr)

    cases = sum(item.kind == "case" for item in items)
    print(f"Wrote {args.out / 'side-by-side.md'} and {args.out / 'key.md'}: {cases} cases, {len(items) - cases} passages.")
    if failures:
        print(f"{len(failures)} call(s) failed:", file=sys.stderr)
        for failure in failures:
            print(f"  {failure}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
