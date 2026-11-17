---
name: commit-message
description: >-
  Draft a git commit message from the staged diff, conforming to the "Writing for people" standards of
  the writing plugin. Use whenever the user asks for a commit message, a commit body, a subject line, "write
  up the commit", "message for the staged changes", or asks you to follow their standards / instructions for
  a commit. Use it again when revising one they rejected. Never draft a commit message the user did not ask
  for.
  Also covers PR titles and descriptions. They follow the same rules against the base branch, but a
  description carries its acceptance evidence.
---

# Commit message

Draft the message. Never stage, commit, or amend. The user signs their own
commits and curates the index by hand.

## Why this skill exists

The rules live in `${CLAUDE_PLUGIN_ROOT}/standards.md` and
`${CLAUDE_PLUGIN_ROOT}/guides/writing-for-people.md`, and the first is often already in
context. They still get missed, because a commit message is written at the end
of a long session and an abstract rule loses to a concrete example sitting
closer in context. The near miss is a read of `git log` "to match the repo's
style". The writer then imitates a message that breaks the rules, and uses that
message to argue past the rule. Older commits predate the rules or were written
before they were enforced.

So: read the rules fresh, read the diff, and check the draft against each rule
before showing it.

## Step 1 — read the rules fresh

Read `${CLAUDE_PLUGIN_ROOT}/guides/writing-for-people.md`.
Then read `${CLAUDE_PLUGIN_ROOT}/guides/commit-messages.md` and
`${CLAUDE_PLUGIN_ROOT}/guides/explanations.md`. Together they are the authority. The checklist
in step 4 comes from them and can lag an edit. If the checklist and the files
disagree, the files win.

Look for a project `CLAUDE.md` too. It can add scope conventions or a PR-base
rule.

## Step 2 — read the diff, not the history

```
git diff --cached --stat     # what moved
git diff --cached            # what it now says
```

If nothing is staged, say so and ask whether to draft against the working tree
instead. Do not guess.

If the prefix convention of the repo (`fix(scope):`, `docs:`) is unknown, run
`git log --format=%s -20`. **Read the subject lines only, as a factual
lookup.** Do not read commit bodies. Body prose is exactly the thing that
overrides the rules in your head.

The baseline is `HEAD`. If a defect in the baseline is the reason for the
change, name the defect. Read the baseline's _code_, not its message. If the
message of `HEAD` asserts something that the diff now disproves, correct the
claim. Do not quote it.

## Step 3 — draft

**Subject.** The subject keeps strict STE: imperative, "if applied, this commit
will ___". Name the change one level above the file list, not the files that
carry it. Aim under ~72 characters.

**Body.** The body is an explanation, so it follows the explanation guide. Name
the relation between facts, and state the scope of each claim. Use `would` for
a case that is not real. Use a list for separate facts. Say what the code does
now, and why it does it that way.

Wrap the body at 72 columns. `git log` indents the body by four spaces, and git
does not wrap it. Indent a wrapped list line by two spaces. A PR body stays
unwrapped, because GitHub wraps it.

Useful shapes, not a mandatory template:

- A one-line lead stating the point, then lists.
- `Baseline defects:` when the commit is corrective. Each bullet: what was
  wrong, what it does now.
- A section for genuinely new surface (new endpoints, new keys on a response,
  moved modules) — anything a reader has to change their own code for.
- A closing line for things a reader would otherwise wonder about: what was
  deliberately left alone, where the reason for that lives.

Point at files, functions, and docs instead of restating what they say. If you
wrote a comment explaining something in this diff, the message names the file
and moves on.

**Prior state is allowed here.** CLAUDE.md's "never say what an earlier version
did" governs code comments and docs. Commit messages and PR descriptions are
where prior state belongs. Do not over-correct into vagueness.

## Step 4 — check the draft by eye

Answer each of these against the text you just wrote. Revise, then run step 5.

- How many paragraphs are in the body? Prose blocks are the most common failure.
  Lists.
- Does any sentence explain something a file, comment, or doc in this diff
  already explains? Point at it instead.
- Does anything describe a review finding, a discussion, or a decision process
  rather than the code that resulted? Cut to the resulting code.
- Does anything describe code that was written and then reworked before this
  commit? It is not in the diff. Cut it.
- In a commit body, does anything say how it was verified: tests run, gates
  green, what you checked? Cut it. A PR description keeps its acceptance
  evidence.
- Any em dash in the subject? Rewrite the subject. In the body, does an em dash
  join separate facts? Split the sentence.
- Does each `would` or `could` in the body mark a case that is not real?
- Any flourishes, hedges, or scene-setting? Cut.
- Is the subject imperative, and above the file list?
- Would a developer skimming for one detail find it?

## Step 5 — run the gate

No hook checks a commit message. `ste-lint-hook.py` matches `Write` and `Edit`,
so it sees files only. `ste-gh-body-hook.py` matches a Bash `gh` command, so it
sees a PR, issue, or review body only. A message drafted in the reply and copied
out reaches neither. Step 4 is your own eye, and `prose-gate` exists because an
eye passes prose a checker fails.

Write the draft to a scratch file and pipe it in:

```
uv run --no-project --quiet --python ">=3.14" "${CLAUDE_PLUGIN_ROOT}/skills/prose-gate/check_prose.py" --stdin < <draft-file>
```

Exit 1 means a hard rule broke. Fix every finding and run it again. A
`READ AND JUDGE` finding needs your eyes, because a trailing `when` clause can
be correct English. Report a finding you keep, and say why.

Run it on a PR title and body too. The `gh` hook denies a bad body at the call,
which costs a rewrite and a second approval. This catches the same text before
the user reads it.

## Step 6 — output

One fenced code block containing the whole message and nothing else, so it can
be copied straight out. Commentary goes after the block, not inside it. Limit
commentary to the user's decisions, such as an unsure scope or a claim that
contradicts an earlier commit. Do not summarize what you wrote.

## PR titles and descriptions

Same rules, with these differences:

- The baseline is the base branch, not `HEAD` (`git diff <base>...HEAD`).
- PR bodies are never hard-wrapped.
- A PR description is the author's case that the work is complete. If the repo
  has a PR template, fill in each section. List each acceptance criterion. If a
  Jira item covers the PR, take the criteria from it. After each one, give
  evidence that a reviewer can check, and mark it met, partly met, or deferred
  to a ticket key.

## Worked example

The same change, drafted badly and then correctly.

**Bad** — paragraphs, restates a comment that is in the diff, narrates the
review and the verification, one em dash:

```
fix: fixed the cache key bug found in review

During review it was noticed that CacheKey.for_request was hashing the
temperature as a raw float, which meant that 0 and 0.0 and -0.0 each produced a
different digest — three fixture files for what is really one request. We
discussed a few options and settled on normalizing in the constructor. There is
now a _normalized_temperature helper which coerces to float and collapses
negative zero, with a comment explaining that PEP 484's numeric tower lets an
int sit in a float slot. All fixture tests pass and workspace:check is green.
```

**Good** — imperative subject, lists, names the baseline defect as the reason,
points at the code:

```
fix(llm-engine): key one temperature on one digest

CacheKey.for_request hashed temperature as given, so 0, 0.0 and -0.0 named three
entries for one request. PEP 484's numeric tower makes all three type-check.

- _normalized_temperature coerces to float and collapses negative zero.
- Recorded fixtures are unaffected. Every committed entry was written from 0.0.
```
