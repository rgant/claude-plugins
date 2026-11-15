#!/usr/bin/env python3
"""UserPromptSubmit hook. Restates the writing standards at the end of context.

The full standards are in `standards.md` of this plugin. The explanation rules are in
`guides/explanations-core.md`, and `guides/explanations.md` adds examples for a larger task. A
writing skill loads them, and the reminder points at each one. Claude
Opus 5 follows a short restatement near the end of a long prompt better than an early statement
alone. See the Opus 5 prompting guide, section "Response length and verbosity".

Keep this text short. It costs tokens on every turn.
"""

import json
import os

REMINDER = (
    "<writing_standards>\n"
    "Each sentence is a procedure or an explanation. A procedure (an instruction, a step, a warning) keeps strict "
    "ASD-STE100: imperative, at most 20 words, modals `can`, `will`, and `must` only, condition before command. An "
    "explanation (what a system does and why) names how facts relate, uses `would` for an unreal case, and follows "
    '{core}. In both: simple tenses, no semicolons, no `should` or `may`, no trailing ", -ing" clause. Messages '
    "between people can use contractions, `should`, progressive, and present perfect.\n"
    "Match the length of a document to the task. Do not pad.\n"
    "Lead the final message with the outcome.\n"
    "Read {standards} before you write a document, a plan, or a PR description. "
    "For a larger explanation, read {full}.\n"
    "</writing_standards>"
)

PLUGIN_ROOT = os.environ.get("CLAUDE_PLUGIN_ROOT", "")
STANDARDS = os.path.join(PLUGIN_ROOT, "standards.md")
CORE = os.path.join(PLUGIN_ROOT, "guides", "explanations-core.md")
FULL = os.path.join(PLUGIN_ROOT, "guides", "explanations.md")


def main() -> None:
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "UserPromptSubmit",
                    "additionalContext": REMINDER.format(standards=STANDARDS, core=CORE, full=FULL),
                },
            }
        )
    )


if __name__ == "__main__":
    main()
