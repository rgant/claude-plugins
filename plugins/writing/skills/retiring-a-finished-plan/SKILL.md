---
name: retiring-a-finished-plan
description: Use when the work in an implementation plan or design spec is complete, when a feature ships and its planning document is still in the tree, or after a plan's branch merges.
---

# Retiring a Finished Plan

## Overview

The plan is done. Its job is over.

**Core principle: keep only what the code cannot say.**

Run this at the end of the work, before the plan ages into the backlog. If a
backlog has already built up, use the `writing:auditing-doc-backlogs` skill
instead.

## The Rule

```
PROPOSE THE DELETE. DELETE ONLY AFTER THE USER CONFIRMS.
```

You never stage and never commit. The user reviews the working tree and signs
the commit.

## Why the plan must go, not stay

A shipped plan reads as current. It names functions that never got written under
those names and describes routes the work replaced. A superpowers plan also
carries
`REQUIRED SUB-SKILL:
use subagent-driven-development to implement this plan`.
That line is a standing instruction to a future agent to rebuild work that
already shipped.

`git log` holds the plan. The working tree is for what is true now.

## Step 0 — Learn where a living document lives

Read the repository's own instruction file (`CLAUDE.md`, `AGENTS.md`,
`CONTRIBUTING.md`) for a rule about where a document goes. Name the living
documents this project already uses: a `README.md`, an architecture document, a
status document, an operator runbook.

Every destination below must be one this step found. **Never introduce a
document type the repository does not already use.** A convention from a
neighboring project is not evidence for this one.

## Step 1 — Confirm the work shipped

Name one function, route, table, or flag the plan introduces. Grep the source
for it.

Do not read the checkboxes as evidence. They record intent, not outcome.

If any task is unfinished, **stop**. Say which one, and leave the plan alone.

Abandoned work is the one exception. If the work never shipped and the direction
is now dead, retire the plan. Harvest the rejection: name what was rejected and
why. Then delete the plan. A dead direction that reads as a live plan costs a
future agent a rebuild.

Code complete and operation blocked by an outside party still counts as shipped.
Retire the plan, and carry the block itself to the status document and the
runbook. It is a live fact that the code cannot state.

## Step 2 — Harvest against the code, not against the plan

Ask one question of the plan and its spec:

**What does this say that the code cannot say?**

| What survives                                                 | Where it goes                                                                              |
| ------------------------------------------------------------- | ------------------------------------------------------------------------------------------ |
| A decision and the reason for it, including what was rejected | The design or architecture document Step 0 found                                           |
| A measured external fact no vendor doc carries                | The document Step 0 found for that subject                                                 |
| A trap a reader will fall into at one site                    | A comment at that site, in the code or in the configuration file                           |
| An instruction an operator acts on                            | The operator-facing file: a README, an `.env.example`, a script usage header, or a runbook |

**Verify each claim in the source before you carry it forward.** A plan states
what the author intended to build. The code states what got built. The two
differ more often at the end of the work than at the start, because the plan
stops getting edited once implementation begins. A claim you copy without
checking becomes a fiction with a fresh timestamp.

Everything else is a slower copy of the code. It goes.

Rules for the destinations:

- Send content only to a destination Step 0 found. If none fits, create a
  document of a type the repository already uses.
- A document with a date in its filename is never a destination. It records one
  moment, so a harvest never edits it. Its own fate is a disposition: delete it,
  keep it unchanged, or rename it.
- Write what is true now. Never describe how the code got there.
- A `file.py:42` anchor rots. Name the symbol instead.
- Reference another file with a relative markdown link, never a bare path.

A measured fact earns its own document when a reader will go looking for it by
subject. One sentence that exists only to support a decision stays with that
decision. If you cannot name the subject a reader will search for, it is not a
resource.

## Step 3 — Update the living documents

The distill step lands here. Every living document Step 0 named describes the
system as it now stands. Update each one the work changed. A README claim goes
stale in the same way an architecture document does, and it carries no plan name
for a grep to find.

If a document must stay true and its filename carries a date, rename it without
the date, then repair the references. A date claims the document records one
moment.

Do not add a changelog entry to them. That is the commit message.

A status document and a priority list hold current and planned work only. Delete
the item that tracked this work. Do not check it off, date it, or move it to a
"Completed" section. If the item holds a live fact, harvest that fact first, as
in Step 2.

## Step 4 — Propose

Give the user:

- The evidence that the work shipped.
- What survives, and the document or code site it moves to.
- The files you propose to delete.
- Every reference to those files elsewhere in the repository.

Grep for the document names. Comments and docstrings written during the work
often cite the plan by section. Those references become dangling on the day you
delete it.

**Then grep for the citation style as its own command.** A citation such as
`Task 7` or `spec §2f` names no file. A filename grep never finds it. Search the
source tree.

**A rename or a rewrite breaks a reference into a document you keep.** The file
still exists, so a link check passes it. Grep for every heading you rename or
drop.

**A surviving document can rest on the plan you delete.** A reference is not
always a pointer. It can be a premise: the survivor states a conclusion, and it
cites the plan for the evidence. Move that evidence into the survivor before you
delete the plan.

Then read the files a reader acts on: the project `README`, an `.env.example`, a
script usage header, a runbook. A stale claim and a wrong instruction name no
document, so the grep above is blind to both. The plan you delete is often the
only place the correct instruction lives.

Then stop. Wait for the answer.

## Step 5 — Apply

After the user confirms, work in this order:

1. Write the successor content.
2. Delete the plan and its spec.
3. Repair the references you found. A citation to a deleted section names the
   symbol instead. A reference to a heading you renamed takes the new heading.
4. Run the `writing:prose-gate` skill on every document you wrote.

Leave the working tree updated. Do not offer a commit message. Several review
rounds come before a commit, and the user asks for a message when the reviews
end.

## Rationalization table

| Excuse                                                                  | Reality                                                                                                |
| ----------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------ |
| "The other finished plans are still here, so this one stays"            | An accumulated backlog is not a convention. Retiring this plan is how the backlog stops growing.       |
| "A status header at the top makes it safe to keep"                      | A reader who trusts the header still reads the wrong body below it.                                    |
| "Correcting the plan is safer than deleting it"                         | Now you maintain two authorities. The code is the authority.                                           |
| "It is a point-in-time record of the design"                            | `git log` holds the record. Harvest the reasons and let the file go.                                   |
| "Deleting loses the reasoning"                                          | Only if you skipped step 2. Harvest first, then delete.                                                |
| "The spec is different from the plan, so the spec stays"                | A spec earns its place by explaining a decision. Harvest that, delete the rest.                        |
| "All the boxes are checked"                                             | Grep the source.                                                                                       |
| "The work never shipped, so the plan is still useful"                   | Ask whether the direction is dead. A dead direction is not a plan. Harvest the rejection, then delete. |
| "A checked box with a date shows what shipped"                          | `git log` shows what shipped. A status document holds current and planned work only.                   |
| "The neighboring project keeps a status document, so this one gets one" | Step 0 says what this project uses. A neighbor's convention is not this project's.                     |
| "The reference grep found nothing, so nothing breaks"                   | A wrong instruction in a README or an `.env.example` names no file. Read them.                         |

## Red flags

- You wrote a status header instead of proposing a delete.
- You copied a sentence from the plan without finding it in the code.
- You kept the spec because deleting only the plan felt safer.
- You named a destination directory the repository does not already use.
- You deleted the only place that held a correct operator instruction.
- You deleted a document that a survivor cites for its evidence.
- A document that must stay true still carries a date in its filename.
- You grepped the deleted filenames, and you called the reference sweep done.
- You renamed or dropped a heading, and you did not grep for it.
- Your change grew the documentation.
