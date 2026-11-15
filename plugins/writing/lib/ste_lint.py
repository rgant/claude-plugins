#!/usr/bin/env python3
"""Deterministic ASD-STE100 violation counter for benchmark runs.

Vendored from github.com/AminBlg/SimpleEnglish, file evals/ste_lint.py, MIT
license. Copyright (c) 2026 AminBlg. The full notice is in
`plugins/writing/LICENSE-SimpleEnglish`.

The `writing` plugin keeps it in `lib/`, so the hooks and `check_prose.py`
share one copy. Refresh it from that repository.

Local change on top of the vendored file: strip_code exempts a bold-only line
the same way it exempts an ATX heading. BANNED_MODALS also matches the negative
contraction ("shouldn't"), because a message may keep its contractions.
strip_fences reads a fenced block line by line, so a long fence that holds a
triple backtick stays code. Re-apply all three after a refresh.

Counts mechanical violations that a regex can catch: sentence length,
contractions, banned modals, perfect tenses, "-ing" clauses, semicolons,
Latin abbreviations, slop words, trailing conditions, synonym rotation.

Known ceiling: this is a regex pass, not a grammar parser. It undercounts
(no passive-voice detection, no part-of-speech checks) and it can miscount
sentence bounds in unusual markdown. Numbers from this tool are comparable
between two texts run through the same version; they are not a compliance
verdict. No tool can guarantee STE compliance.

Usage:
  python3 ste_lint.py --type procedural file.md
  cat text.md | python3 ste_lint.py --type descriptive -
  python3 ste_lint.py --self-test
"""

import json
import re
import sys

BANNED_MODALS = re.compile(r"\b(should|would|may|might|could)(?:n't)?\b", re.IGNORECASE)
PERFECT = re.compile(r"\b(has|have|had)\s+been\b|\b(has|have)\s+\w+ed\b", re.IGNORECASE)
CONTRACTION = re.compile(r"\b\w+(n't|'ll|'re|'ve|'d)\b|\bit's\b|\byou're\b", re.IGNORECASE)
ING_CLAUSE = re.compile(
    r",\s*(mak|allow|enabl|ensur|highlight|creat|provid|offer|help|reduc|improv|lead|caus|result)ing\b",
    re.IGNORECASE,
)
LATIN = re.compile(r"\b(e\.g\.|i\.e\.|etc\.?)(?=[\s,)]|$)", re.IGNORECASE)
SLOP = re.compile(
    r"\b(simply|seamlessly|effortlessly|robust|leverag\w*|utiliz\w*|"
    r"comprehensive|powerful|blazingly|streamlin\w*|facilitat\w*|"
    r"performant|plethora|myriad|delve|crucial|pivotal)\b",
    re.IGNORECASE,
)
TRAILING_COND = re.compile(r"\w[^.!?\n]{3,}\s\b(if|when)\b\s", re.IGNORECASE)
ROTATION_SETS = [
    (
        "check-verify",
        re.compile(r"\b(check|verify|confirm|validate|ensure)\w*\b", re.IGNORECASE),
    ),
    (
        "config-settings",
        re.compile(r"\b(config|configuration|settings)\b", re.IGNORECASE),
    ),
]
LIMITS = {"procedural": 20, "descriptive": 25}


# A fence nested in a list item sits at any indent, so the indent is not limited.
FENCE_OPEN = re.compile(r"^[ \t]*(`{3,}|~{3,})")


def fence_mask(lines):
    """Return one flag per line: True for a line inside a fenced code block, fences included.

    A fence closes only on a line of the same character, at least as long as the opener. A
    four-backtick suggestion can hold a triple backtick, and a pairing regex ends the block there.
    An unclosed fence runs to the end of the text.
    """
    mask = []
    fence = None
    for line in lines:
        if fence is None:
            match = FENCE_OPEN.match(line)
            if match:
                fence = match.group(1)
            mask.append(bool(match))
            continue
        marker = line.strip()
        if len(marker) >= len(fence) and set(marker) == {fence[0]}:
            fence = None
        mask.append(True)
    return mask


def strip_fences(text):
    """Blank each fenced code block, as CommonMark reads it. See `fence_mask`."""
    lines = text.split("\n")
    return "\n".join("" if fenced else line for line, fenced in zip(lines, fence_mask(lines), strict=True))


def strip_code(text):
    text = strip_fences(text)
    text = re.sub(r"(`{2,})[^\n]*?\1", " CODESPAN ", text)  # a span that holds a backtick
    text = re.sub(r"`[^`\n]+`", " CODESPAN ", text)  # one word per Rule 8.6
    text = re.sub(r"^#+\s.*$", " ", text, flags=re.MULTILINE)  # headings exempt (titles, 8.6)
    # A line that is entirely bold is a heading too. Markdown carries no other way to write one
    # inside a numbered list. Without this the heading's final "." sits before "**", which the
    # sentence split does not read as an end, so the heading joins the paragraph under it.
    text = re.sub(r"^\s*\*\*[^\n]+\*\*\s*$", " ", text, flags=re.MULTILINE)
    text = re.sub(r"https?://\S+", " URL ", text)
    return text


def sentences(text):
    text = re.sub(r"^\s*([-*]|\d+\.)\s+", "", text, flags=re.MULTILINE)  # list markers
    # A closing marker can sit between the terminator and the space, as in "the proof.** After".
    # Without those markers here, an inline bold sentence joins the sentence after it and the
    # pair counts as one long sentence.
    parts = re.split(r"(?<=[.!?:])[*_`'\")\]]*\s+", text)
    return [p.strip() for p in parts if len(p.strip().split()) >= 2]


def lint(text, text_type):
    body = strip_code(text)
    sents = sentences(body)
    limit = LIMITS[text_type]
    counts = {}
    lengths = [len(s.split()) for s in sents]
    counts["sentence_over_limit"] = sum(1 for n in lengths if n > limit)
    counts["contraction"] = len(CONTRACTION.findall(body))
    counts["banned_modal"] = len(BANNED_MODALS.findall(body))
    counts["perfect_tense"] = len([m for m in PERFECT.finditer(body)])
    counts["ing_clause"] = len(ING_CLAUSE.findall(body))
    counts["semicolon"] = body.count(";")
    counts["latin_abbrev"] = len(LATIN.findall(body))
    counts["slop_word"] = len(SLOP.findall(body))
    counts["trailing_condition"] = sum(1 for s in sents if TRAILING_COND.search(s) and not re.match(r"^(if|when)\b", s, re.IGNORECASE))
    rotation = 0
    for _, rx in ROTATION_SETS:
        stems = {m.group(1).lower().rstrip("s") for m in rx.finditer(body)}
        if len(stems) > 1:
            rotation += len(stems) - 1
    counts["synonym_rotation"] = rotation
    words = max(1, len(body.split()))
    total = sum(counts.values())
    return {
        "type": text_type,
        "words": words,
        "sentences": len(sents),
        "mean_sentence_words": round(sum(lengths) / max(1, len(lengths)), 1),
        "longest_sentence_words": max(lengths, default=0),
        "violations": counts,
        "violations_total": total,
        "violations_per_100w": round(100.0 * total / words, 2),
    }


SLOP_FIXTURE = """Leveraging our robust retry mechanism, failed uploads are automatically
reattempted, ensuring data integrity is maintained throughout the entire process which has
been designed from the ground up to gracefully handle even the most challenging network
interruptions. You should verify your credentials; it's also worth checking the settings,
e.g. the timeout config. Contact support if the problem persists."""

CLEAN_FIXTURE = """The system retries a failed upload automatically. This process keeps the data correct.

If failures continue, make sure that your credentials are correct. If the problem continues, contact support."""


# An inline bold sentence sits inside a paragraph, and its terminator sits inside the markers.
INLINE_BOLD_FIXTURE = """The prefix is empty, so the plan adds every resource and the job passes.
**That green is the failure signal, not the proof.** After the state moves, the plan reports one
change and leaves the rest alone."""


def self_test():
    bold = lint(INLINE_BOLD_FIXTURE, "procedural")
    assert bold["sentences"] == 3, bold
    assert bold["violations"]["sentence_over_limit"] == 0, bold
    slop = lint(SLOP_FIXTURE, "procedural")
    clean = lint(CLEAN_FIXTURE, "procedural")
    assert slop["violations"]["sentence_over_limit"] >= 1, slop
    assert slop["violations"]["banned_modal"] >= 1, slop
    assert slop["violations"]["contraction"] >= 1, slop
    assert slop["violations"]["perfect_tense"] >= 1, slop
    assert slop["violations"]["ing_clause"] >= 1, slop
    assert slop["violations"]["semicolon"] == 1, slop
    assert slop["violations"]["latin_abbrev"] >= 1, slop
    assert slop["violations"]["slop_word"] >= 2, slop
    assert slop["violations"]["trailing_condition"] >= 1, slop
    assert slop["violations"]["synonym_rotation"] >= 1, slop
    assert clean["violations_total"] == 0, clean
    print(
        "self-test OK:",
        slop["violations_total"],
        "violations in slop fixture, 0 in clean",
    )


def main():
    args = sys.argv[1:]
    if "--self-test" in args:
        self_test()
        return
    text_type = "descriptive"
    if "--type" in args:
        text_type = args[args.index("--type") + 1]
    src = args[-1]
    text = sys.stdin.read() if src == "-" else open(src).read()
    print(json.dumps(lint(text, text_type), indent=2))


if __name__ == "__main__":
    main()
