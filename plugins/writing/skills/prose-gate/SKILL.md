---
name: prose-gate
description: Use when writing or finishing any comment, docstring, README, design document, implementation plan, GitHub issue, PR body, or commit message, and before reporting that writing work is done. Use it when a task changed prose as a byproduct of changing code, and when a review finding asks for a wording change.
---

# Prose Gate

## Overview

The rules are not the problem. Agents that read the standard write to it. The
failure is that nobody runs a check, so prose ships unread.

**Prose is not done until `check_prose.py` reports it clean.** Run the gate. Do
not judge your own sentences by eye.

**REQUIRED SUB-SKILL:** `writing:simple-english` holds the 53 STE rules. Load it
to fix a finding in a procedure. To fix a finding in an explanation, read
`${CLAUDE_PLUGIN_ROOT}/guides/explanations.md`. For a commit message, a PR title, or a PR
description, load `writing:commit-message` instead.

## The gate

Run this before you report any task that wrote or changed prose:

```sh
uv run --no-project --quiet --python ">=3.14" "${CLAUDE_SKILL_DIR}/check_prose.py"
```

It reads only the lines the branch adds or changes, against the merge-base with
the default branch. Staged, unstaged, and untracked files are all in scope.

- A plan or a draft has no branch diff yet. Use `--files <path>` or pipe the
  draft to `--stdin`.
- A review body, a PR comment, or a chat message is a message between people.
  Add `--message`. It allows contractions and the progressive, and in an
  explanation the present perfect and `should`. Docs, comments,
  and PR descriptions never take it.
- An agent instruction file never appears. `CLAUDE.md`, `AGENTS.md` and
  `GEMINI.md` address a model, not a person, and the style rules they carry are
  the ones inside them. To check one anyway, name it with `--files`.
- A generated file never appears either. `CHANGELOG.md` holds commit subjects,
  and the next release rewrites it. Fix the commit subject, not the changelog.
- Exit 1 means a hard rule broke. Fix every one.
- The `READ AND JUDGE` group needs your eyes. A trailing `when` clause can be
  correct English.

Read every finding against the source. The tool reports a sentence, not a
verdict.

## Findings in each register

The gate reads each sentence as a procedure or an explanation. A procedure
starts with an imperative verb, or with a condition and then an imperative. A
sentence under a procedure heading such as "Steps", "Setup", or "Getting
started", or under a sub-heading of one, is a procedure too. So is a sentence
in a warning. A sub-heading such as "Design" or "How it works" ends the
procedure for its section. Every other sentence is an explanation.

A procedure keeps every strict limit. In an explanation, these rules report in
the `READ AND JUDGE` group and do not fail the run:

- `LENGTH-READ`: a sentence over 25 words. If it carries one line of reasoning,
  keep it whole. If it holds separate facts, split it. In a procedure, `LENGTH`
  fails a sentence over 20 words.
- `MODAL-READ`: `would`, `could`, or `might`. `would` and `could` state a case
  that is not real, and `might` states an uncertain outcome. If the sentence
  states a real case, write the fact, or write `can` for what is possible. In a
  procedure, `MODAL` fails each of these words.
- `EM-DASH-READ`: an em dash. If the dash joins separate facts, split the
  sentence. In a procedure, `EM-DASH` fails it.

These rules fail the run in a procedure and in an explanation:

- `MODAL` for `should` or `may`.
- `SEMICOLON`, `CONTRACTION`, `PRESENT-PERFECT`, `ING-VERB`, `AND-OR`, `LATIN`,
  and `SLOP`.
- The structural checks `TRIPLE`, `NOT-JUST`, `REVERSAL`, `FILLER`, and
  `ANNOUNCE`.

`ING-READ` reports in both registers and does not fail the run. It marks an
"-ing" word after a form of "be", with a bare word after it. The word can be a
modifier, as in "are working documents". If it is a verb, write the simple
tense. With nothing after it, or with an object, a pronoun, a preposition, or
code after it, the word is a verb, and `ING-VERB` fails it. After a comma, an
"-ing" word opens a trailing clause, and `ING-VERB` always fails it.

## The cold-reader check

A regex cannot see lost meaning, but a reader with no context can. This check
is advisory. The gate passes when `check_prose.py` passes.

Run the check for a design document, a plan, a README, or a guide. Never run it
for a commit message or a code comment, because a subagent call costs too much
there.

1. Dispatch a fresh subagent on the Sonnet model. Send it only the document.
2. Ask the subagent for these findings:
   - the claim of each paragraph, in its own words
   - each sentence that it had to read twice, or where it had to guess
   - each pronoun with no single noun to point at
   - the questions that a reader still has after the document
3. Compare each restated claim with what you meant. A difference is a lost
   meaning.
4. Fix each lost meaning, or state why the text is correct.

## Scope: your prose only

The checker reports a sentence when the sentence touches a changed line. A
sentence the base branch already carries can share a line with your edit, so it
can appear.

**Fix what this branch wrote. Report what it did not.** A rewrite of the base
branch's prose grows the diff past the change under review. The reviewer then
reads two changes as one.

## Write it in this shape

The pressure that breaks the rules is "explain it fully so nobody has to ask".
Completeness is not length. Give the reader the same facts in this shape:

- A procedure gives one instruction per sentence.
- In an explanation, join related facts with the word that names their
  relation: because, so, but, unless. A separate fact gets its own sentence.
- A trade-off names the cost and what the cost buys. A "but" or a "so" joins
  them.
- The condition comes first. Write "If the build fails, read the log."
- State what the code does now. Prior state belongs to `git log` and to the
  commit body.

## Rationalization table

| Excuse                                                               | Reality                                                                                                                                                 |
| -------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| "The reviewer will ask why, so I must explain the trade-off in full" | A 40-word sentence is fine in an explanation if it is one line of reasoning. If it holds separate facts, it hides the trade-off. Split it.              |
| "The next reader has none of my context"                             | Give them the reason, not the history. What an earlier version did is in `git log`.                                                                     |
| "This sentence needs the em dash to hold together"                   | Then it holds separate facts. Split it. A procedure never takes an em dash.                                                                             |
| "`would` is the only natural word here"                              | `would` is correct for a case that is not real: "A default would carry a credential." For a real case, state the fact: "A null key moves every digest." |
| "I already know these rules"                                         | You knew them last time. The prose still failed. Run the gate.                                                                                          |
| "It is only a comment"                                               | A comment is writing for a person. Same rules.                                                                                                          |
| "The gate is for the final commit"                                   | You do not stop reliably. Run it at the end of the writing, every time.                                                                                 |

## A comment must add understanding

The goal is code a reader understands. A comment refines that understanding. It
gives the outside context that the code cannot carry: a decision, a constraint,
a failure that shaped the code.

No checker finds this. Apply the test yourself, on every comment, doc line and
config comment you write:

- **Cut it** if the code, a flag name, a recipe name or the tool's own docs
  already say it. "`--write` writes the file" helps nobody.
- **Cut it** if it is true of every tool of its kind. "shfmt formats the script"
  is water that makes things wet.
- **Keep it** only if a reader who has the code in front of them still learns
  something.

A trimmed comment keeps the reason and loses the restatement. If the trim leaves
only a triviality, delete the whole comment.

## Red flags

- You wrote a comment that restates the line under it.
- You report writing work, and the checker did not run.
- You joined two facts with a comma and no word that names their relation.
- You explain what the code did before.
- You counted members instead of a list of their names.
- You wrote a plan document, and the checker did not read it.

**Each one means: run the gate now.**
