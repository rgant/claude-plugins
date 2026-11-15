---
name: gemini-review
description: Use when the user asks for a Gemini review or a second opinion from Gemini, or a review "with agy" or "with Antigravity". It reviews uncommitted changes, files, folders, or a design or plan document. Read-only. Never use it on your own initiative, because each run spends the user's small Gemini quota.
---

# Gemini review

Get a read-only review from Gemini through the Antigravity CLI (`agy`). Then
check every finding against the real code before you report it. The user wants
findings the code supports, not a relay of model output.

## Run the review

Run the script from inside the repo to review. Run it in the background, because
a review takes minutes.

```bash
${CLAUDE_PLUGIN_ROOT}/skills/gemini-review/scripts/agy-review.sh --uncommitted src/retry.py tests/test_retry.py
${CLAUDE_PLUGIN_ROOT}/skills/gemini-review/scripts/agy-review.sh path/to/file.py path/to/folder
${CLAUDE_PLUGIN_ROOT}/skills/gemini-review/scripts/agy-review.sh --focus "check the retry bounds" docs/x-design.md
```

- Name the paths of the change under review. Review all uncommitted changes only
  when the user asks for it, because the working tree can hold large work in
  progress.
- Give `--focus` when the user named a concern.
- Give `--effort low` or `--effort medium` unless the user asks for a deep
  review. Thinking tokens are most of the quota cost.
- The last stdout line is the run folder. Read `review.md` in it.
- If the script exits 2, the review is incomplete. Tell the user and quote the
  stderr line. Do not run it again without the user's approval.
- If the script reports denied reads, the reviewer wanted a file it did not get.
  Tell the user which review areas lack context.
- If the input is over `--max-bytes`, tell the user the size and ask for a
  smaller target. Do not raise the limit on your own.

## Check each finding

The reviewer saw copies in a throwaway folder. Its paths are relative to that
folder, which matches the repo root. For each finding:

1. Read the cited lines in the real repo.
2. Confirm the quoted code exists there.
3. Trace the failure it claims. If code or a test can settle it, run it.
4. Classify it: **confirmed**, **rejected** (give the reason in one sentence),
   or **unverified** (name the check that can settle it).

Do not fix anything. The user decides what to change.

## Report

Lead with the count of confirmed findings. List the confirmed findings, ranked
by severity, with `file:line` and the fix. Then list the rejected and unverified
findings in one line each. Name the run folder, so the user can read the raw
review.
