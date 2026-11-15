#!/usr/bin/env python3
"""Detect structural slop that the word-level ASD-STE100 checks do not reach.

`ste_lint.py` and `check_prose.py` ban a list of single words. A sentence can
break none of those rules and still read as machine prose, because the defect
is a shape, not a word. This module holds the shape patterns.

Both checkers import this file, so a pattern is defined once. `ste_lint.py`
stays a clean copy of its upstream source and gains nothing from this module
directly. The hook merges the two results.

Groups:
    triple      A run of three negations.
    not_just    A dismissal of the plain reading, and the reversal after it.
    reversal    A denial followed by the restated claim.
    announce    A sentence that announces the next sentence.
    filler      A phrase that carries no fact.
    hedge       A qualifier that dodges the ban on `should` and `might`.
    intensifier Empty emphasis.

The DIRTY fixture at the end of this file breaks every group once. Read it for
an example of each.

Every pattern is a regex, so every hit needs a human read. Report, never block.

Usage:
    python3 ste_structural.py --self-test
    cat draft.md | python3 ste_structural.py -
"""

import json
import re
import sys

TRIPLE = re.compile(r"\bnot\b[^.!?\n]{1,60}?,\s*not\b[^.!?\n]{1,60}?,\s*not\b", re.IGNORECASE)

NOT_JUST = re.compile(r"\bnot\s+(just|only|merely|simply)\b", re.IGNORECASE)

REVERSAL = re.compile(
    r"\b(is|was|are|were)\s+not\b[^.!?\n]{1,60},\s*(it|this|that|they)\s+"
    r"(is|was|are|were)\b"
    r"|\bless\s+about\b[^.!?\n]{1,50}\bthan\b",
    re.IGNORECASE,
)

# A phrase that announces or pads. Safe to search anywhere in a sentence.
FILLER = re.compile(
    r"\b(the bottom line|in short|in summary|to summarize|to sum up|"
    r"that being said|with that said|it turns out|"
    r"the good news is|the bad news is|what this means is|"
    r"put simply|simply put|at a high level|at the end of the day|"
    r"needless to say|goes without saying|first and foremost|"
    r"last but not least|rest assured|when it comes to|the fact that|"
    r"it is important to note|it'?s important to note|"
    r"it is worth mentioning|as we all know|"
    r"the key (insight|point|takeaway|thing)|the main (point|takeaway))\b",
    re.IGNORECASE,
)

# A word that only pads when it opens a sentence. Anchored, so a mid-sentence
# use of the same word does not report.
ANNOUNCE = re.compile(
    r"^\W*(here (is|are)|here'?s|that said|importantly|notably|interestingly|"
    r"crucially|ultimately|fundamentally|to be clear|to be fair)\b",
    re.IGNORECASE,
)

HEDGE = re.compile(
    r"\b(likely|generally|typically|usually|tends?\s+to|in practice|"
    r"arguably|essentially|effectively|potentially|presumably|somewhat|"
    r"relatively|fairly|virtually|largely|broadly|more or less|"
    r"for the most part|in general)\b",
    re.IGNORECASE,
)

INTENSIFIER = re.compile(
    r"\b(really|truly|genuinely|actually|very|extremely|incredibly|"
    r"absolutely|obviously|clearly|of course|significantly|substantially|"
    r"dramatically|massively|hugely|enormously|remarkably)\b",
    re.IGNORECASE,
)

# (count key, report name, pattern, anchored to the start of a sentence)
PATTERNS = (
    ("triple", "TRIPLE", TRIPLE, False),
    ("not_just", "NOT-JUST", NOT_JUST, False),
    ("reversal", "REVERSAL", REVERSAL, False),
    ("filler_phrase", "FILLER", FILLER, False),
    ("announce", "ANNOUNCE", ANNOUNCE, True),
    ("hedge", "HEDGE", HEDGE, False),
    ("intensifier", "INTENSIFIER", INTENSIFIER, False),
)

# The keys this module adds, for a caller that filters a report by name.
KEYS = tuple(key for key, _, _, _ in PATTERNS)
# A hedge or an intensifier can carry a fact, as in "usually 5432", so these keys are advisory.
# The prose gate reports them in its READ AND JUDGE group, and the lint hook under "Read again".
ADVISORY_KEYS = frozenset({"hedge", "intensifier"})


SENTENCE_SPLIT = re.compile(r"(?<=[.!?:])\s+")
PARAGRAPH_SPLIT = re.compile(r"\n\s*\n")
WRAP = re.compile(r"[ \t]*\n[ \t]*")


def normalize(text: str) -> str:
    """Join the wrapped lines of each paragraph, so a pattern spans a line break.

    A source file wraps prose at 80 columns. A pattern that bans a newline then
    misses every sentence the wrap cuts in half.
    """
    body = re.sub(r"^\s*([-*+]|\d+\.)\s+", "", text, flags=re.MULTILINE)
    paragraphs = [WRAP.sub(" ", part) for part in PARAGRAPH_SPLIT.split(body)]
    return "\n\n".join(paragraphs)


def sentences(text: str) -> list[str]:
    """Return the sentences of *text*."""
    parts: list[str] = []
    for paragraph in PARAGRAPH_SPLIT.split(normalize(text)):
        parts += SENTENCE_SPLIT.split(paragraph)
    return [part.strip() for part in parts if part.strip()]


def count(text: str) -> dict[str, int]:
    """Return a hit count per group for a whole document.

    An anchored group runs against the start of each sentence. Every other
    group runs against the whole text.
    """
    hits: dict[str, int] = {}
    body = normalize(text)
    sents = sentences(text)
    for key, _, pattern, anchored in PATTERNS:
        if anchored:
            hits[key] = sum(1 for s in sents if pattern.match(s))
        else:
            hits[key] = len(pattern.findall(body))
    return hits


def find(sentence: str) -> list[tuple[str, str]]:
    """Return every group *sentence* breaks, as (report name, matched text)."""
    found: list[tuple[str, str]] = []
    for _, name, pattern, anchored in PATTERNS:
        match = pattern.match(sentence) if anchored else pattern.search(sentence)
        if match:
            found.append((name, match.group(0).strip()))
    return found


DIRTY = """It is not a bug, not a typo, not a syntax error. The fix is not just
a rename, it is a redesign. Here is the reason: the cache key is essentially
arbitrary, and the daemon generally reloads it. That said, it is actually
relatively safe. The bottom line is that when it comes to the fact that the
pool tends to stall, you clearly need a longer timeout."""

CLEAN = """The parser rejects an empty key. The cache key includes the fixture
filename, so a rename forces a re-record. If the pool stalls, raise the
timeout. The daemon reloads the file on the next run."""


def self_test() -> None:
    dirty = count(DIRTY)
    clean = count(CLEAN)
    for key in KEYS:
        assert dirty[key] >= 1, (key, dirty)
    assert sum(clean.values()) == 0, clean

    assert find("Here is the plan.")[0][0] == "ANNOUNCE"
    assert not find("The log says the daemon is here.")
    assert find("It is not a bug, not a typo, not Python 2.")[0][0] == "TRIPLE"
    assert not find("The daemon reloads the file.")
    print("self-test OK:", sum(dirty.values()), "hits in dirty, 0 in clean")


def main() -> None:
    args = sys.argv[1:]
    if "--self-test" in args:
        self_test()
        return
    src = args[-1] if args else "-"
    text = sys.stdin.read() if src == "-" else open(src).read()
    print(json.dumps(count(text), indent=2))


if __name__ == "__main__":
    main()
