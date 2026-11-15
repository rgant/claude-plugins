#!/usr/bin/env python3
"""Check that the prose gate and `register.classify` give each sentence the same register.

The gate shows a register only through a rule name. Each fixture sentence holds the soft modal
`would`, so the gate reports MODAL for a procedure and MODAL-READ for an explanation.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "lib"))
sys.path.insert(0, str(ROOT / "skills" / "prose-gate"))
import check_prose  # noqa: E402
import register  # noqa: E402

PROBE_RULES = {"MODAL": True, "MODAL-READ": False}

# Each fixture gives the markdown and the register of each sentence, in order.
FIXTURES = [
    (
        "colon inside a sentence",
        "The fix has one part: use a lock, which would block the writer until the reader ends.\n",
        [False],
    ),
    ("bold warning label", "**Warning:** the job would delete the branch.\n", [True]),
    ("warning label", "Warning: the job would delete the branch.\n", [True]),
    ("caution label", "Caution: the job would delete the branch.\n", [True]),
    ("danger label", "Danger: the job would delete the branch.\n", [True]),
    (
        "label marks its own sentence only",
        "Warning: the job would delete the branch. The branch would then be gone.\n",
        [True, False],
    ),
    (
        "heading in the middle of a paragraph",
        "The cache would expire at night.\n## Steps\nThe script would need uv.\n",
        [False, True],
    ),
    (
        "callout with text on the opening line",
        "> [!WARNING] The command would delete the branch.\n\nThe command would delete the branch.\n",
        [True, False],
    ),
    ("open task item", "- [ ] Run the job so that it would pass.\n", [True]),
    ("done task item", "- [x] Run the job so that it would pass.\n", [True]),
    (
        "parenthesis list items",
        "1) The cache would expire\n2) Run the job so that it would pass\n",
        [False, True],
    ),
    (
        "two registers in one paragraph",
        "Run the job so that it would pass. The cache would expire at night.\n",
        [True, False],
    ),
    (
        "bold line is its own unit",
        "**Run the job so that it would pass**\nThe script would need uv.\n",
        [True, False],
    ),
    (
        "frontmatter",
        "---\nname: demo\ndescription: a demo\n---\n\nThe cache would expire at night.\n",
        [False],
    ),
    (
        "sub-heading under a procedure heading",
        "## Setup\n\n### macOS\n\nThe script would need uv.\n",
        [True],
    ),
    ("noun opener", "Name collisions would break the registry.\n", [False]),
    (
        "thematic break before text",
        "---\nThe cache would expire at night.\n\n***\n\nThe script would need uv.\n",
        [False, False],
    ),
    (
        "long fence holds a short fence",
        "The cache would expire.\n\n````markdown\n```\nRun it; you should.\n```\n````\n",
        [False],
    ),
    (
        "period inside a code span",
        "The log prints `Done. Run it` and would stop.\n",
        [False],
    ),
]

failures = 0


def case(name: str, got: object, want: object) -> None:
    global failures
    passed = got == want
    failures += not passed
    print(f"{'ok ' if passed else 'FAIL'} {name}")
    if not passed:
        print(f"     got {got!r}, want {want!r}")


def main() -> None:
    for name, markdown, want in FIXTURES:
        gate = [
            (finding.text, PROBE_RULES[finding.rule])
            for finding in check_prose.check("fixture.md", markdown, None)
            if finding.rule in PROBE_RULES
        ]
        units = register.classify(markdown)
        case(f"{name}: every unit holds the probe", all("would" in unit.text for unit in units), True)
        classified = [(unit.text, unit.procedural) for unit in units]
        case(f"{name}: gate and classify agree", gate, classified)
        case(f"{name}: register", [procedural for _, procedural in classified], want)

    print("ALL PASS" if not failures else f"FAILURES: {failures}")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
