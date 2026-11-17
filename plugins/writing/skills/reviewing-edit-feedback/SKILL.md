---
name: reviewing-edit-feedback
description: Use when the user asks for a writing review, a feedback review, or a review of their edits to Claude's drafts, or when the session-start reminder says that a writing review is due.
---

# Reviewing Edit Feedback

## Overview

The store holds pairs of a draft that Claude wrote and the text that the user sent. A pair comes
from a Slack or Teams message, a PR description, or a ticket description. This skill turns the
corrections that repeat into proposed changes to the writing rules.

**Core principle: one edit is a data point, and a repeated correction is a rule.**

## The Rule

```
PROPOSE. CHANGE A RULE ONLY AFTER THE USER APPROVES IT.
NEVER COPY STORED TEXT INTO THE REPOSITORY.
```

The store holds messages to coworkers and text from client repositories. An example in a guide or
a test is a rewrite, with each name and each domain changed.

## The command

Each step runs the extractor with one subcommand:

```sh
uv run --no-project --quiet --python ">=3.14" "${CLAUDE_SKILL_DIR}/extract_feedback.py" --store "${CLAUDE_PLUGIN_DATA}/feedback" <subcommand>
```

## Steps

Run each step as its own command, in order. While a record is pending, `done` refuses to run.

1. Run `extract --fetch`. It adds the new pairs and fetches the finals of merged PRs and of
   tickets older than 7 days. Report each `skipped`, `unreadable`, and `fetch failed` line to the
   user. If no such line appears, say so in one line.
2. Read all of `${CLAUDE_PLUGIN_ROOT}/standards.md`,
   `${CLAUDE_PLUGIN_ROOT}/guides/writing-for-people.md` and
   `${CLAUDE_PLUGIN_ROOT}/guides/explanations.md`. You classify against these rules, so read them
   before the first record.
3. Run `labels`. It lists each correction label with the count of each cause.
4. Run `pending`. Each line is one record as JSON, and the list includes records from earlier
   extractions. Compare the `draft` of each record with its `final`, and read its `requests`.
5. For each record, choose one cause from the table below and one label. If an existing label fits,
   use it, whatever its cause. Run `classify <id> <cause> <label>`.
6. Run `labels` again. Find each label that has more than one record with the cause `wrong-rule`
   or `broken-rule`, counted together.
7. Write one proposal for each label from step 6. Present all proposals to the user in one message.
8. Make each change that the user approves. Run the prose gate and the plugin tests after the
   changes.
9. Run `done`. It records the time of this review, so the session-start reminder stops.

## Causes

| Cause | The edit | Result |
| --- | --- | --- |
| `wrong-rule` | The draft followed the guides, and the user still changed it. | A guide changes. |
| `broken-rule` | The draft broke a rule that the checks did not catch. | A check changes. |
| `wrong-fact` | The user corrected the content. | Nothing changes. |
| `final-error` | The edit added a spelling, grammar, or punctuation error. | Nothing changes. |
| `taste` | The edit matches no rule. | Nothing changes now. The record stays as a sample. |

A label is a short kebab-case name for the correction, such as `drop-hedge-words` or
`lead-with-the-ask`. Name what the user did, not the record.

## A proposal

Each proposal holds these parts, in this order:

1. The label, and the count of `wrong-rule` and `broken-rule` records.
2. The file that changes: a guide, `standards.md`, `lib/ste_lint.py`,
   `lib/ste_structural.py`, or `skills/prose-gate/check_prose.py`. To find the file that holds a
   check, search `${CLAUDE_PLUGIN_ROOT}` for the check name, such as `HEDGE`.
3. The change, in one or two sentences.
4. One rewritten example in the "Rewritten from corpus" form of `guides/explanations.md`.
5. For `broken-rule`: the test case that the new check must pass.

## Common mistakes

- **A proposal from one record.** One edit can be taste or a slip. Wait for a second record.
- **A new label for each record.** Run `labels` first. Labels with one record each never reach a
  proposal.
- **A typo that becomes a rule.** If the edit added an error, the cause is `final-error`.
- **Stored text in an example.** Rewrite each example. Change each name and each domain.
- **`done` before the user answers.** Run `done` last, after the approved changes.
