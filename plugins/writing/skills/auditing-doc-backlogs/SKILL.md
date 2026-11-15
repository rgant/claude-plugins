---
name: auditing-doc-backlogs
description: Use when finished implementation plans or design specs have accumulated anywhere in the tree, when a reader cannot tell which documents describe the built system, or when generated planning documents have piled up over months.
---

# Auditing Doc Backlogs

## Overview

A planning document is a tool for building. When the work ships, the code
becomes the authority and the document becomes a second, wrong copy of it.

**Core principle: keep only what the code cannot say.**

A shipped plan in the tree is worse than no document. It reads as current, it
names functions that never existed, and a superpowers plan carries
`REQUIRED SUB-SKILL: use
subagent-driven-development to implement this plan`.
That line tells a future agent to rebuild shipped work.

## The Rule

```
PROPOSE EVERY DELETE. DELETE ONLY AFTER THE USER CONFIRMS.
```

You never stage and never commit. The user reviews the working tree and signs
the commit.

## Step 0 — Learn the layout and the conventions

The repository decides where a document lives and what a living document is
called. Learn that before you touch anything.

1. Find the documents. `git ls-files '*.md'` gives the true set. A doc directory
   sits at the root, next to each project, or next to each library. Do not
   assume one root `docs/`.
2. Read the repository's own instruction file (`CLAUDE.md`, `AGENTS.md`,
   `CONTRIBUTING.md`) for a rule about where a document goes.
3. Name the living documents each project already uses. One repository uses
   `README.md` alone. Another adds an architecture document, a status document,
   or an operator runbook.
4. Note which of them carry a date in the filename. A date claims the document
   records one moment. A document that must stay true needs a name without one.

Every later step sends harvested content to a destination this step found.
**Never introduce a document type the repository does not already use.** A
convention from a neighboring project is not evidence for this one.

## Step 1 — Triage without reading

Do this before you open one document body. It costs a few commands and it
decides how much reading the rest of the audit needs.

```sh
git ls-files '*.md'                                # the true document set
git log --oneline --name-status -- <doc-dir>       # which change shipped each document
git log --format='%ad %h' --date=short -- <file>   # every touch, newest first
git show --name-only --format= <commit> | wc -l    # >15 files means a sweep
git log --oneline -- <file> | wc -l                # how many times touched
wc -l <file>
```

The paths come from Step 0. Never hardcode `docs/`.

**A commit that touches more than 15 files is a sweep. Ignore its date.** A
dependency bump, a format run, or a rename drags every document along and resets
the modification date of the whole backlog. Walk the log newest first. The true
last touch is the first commit that touched 15 files or fewer.

Read the signals this way:

| Signal                                                   | What it means                                                                                         |
| -------------------------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| One commit ever, no edit since                           | Written once, never revisited. Inert.                                                                 |
| Many commits across months                               | Read the commits before you call it living.                                                           |
| Untouched for more than 3 months                         | Assume the work shipped or never started. Confirm in the code.                                        |
| Checked or unchecked boxes                               | **Not evidence.** Older documents predate the box rule.                                               |
| One change that touches many documents at once           | Not maintenance. A repository-wide format or rename drags every file along. Open the diff.            |
| A design document with a "Documentation Updates" section | Read that section first. It names where the harvest went. If the work happened, the harvest is empty. |

A commit count is a weak signal on its own. Open the commits. Call a document
living only when someone edits it on purpose, to keep it true. A code commit
that drags a document along is not maintenance. A spec revised during its own
implementation is not maintenance either.

**Never classify a plan from its checkboxes.** Name one function, route, table,
or flag the plan introduces. Then grep the source for it. That answers "did this
ship" in one command.

## Step 2 — Assign a disposition

| Document                                      | State                                                | Disposition                                                                                      |
| --------------------------------------------- | ---------------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| Implementation plan                           | Work shipped                                         | Harvest, then delete                                                                             |
| Implementation plan                           | Work not started                                     | Keep. Ask the user if it is still relevant.                                                      |
| Implementation plan or design spec            | Work never shipped, and the direction is now dead    | Harvest the rejection, then delete. Name what was rejected and why.                              |
| Implementation plan                           | Work in progress                                     | **Skip it.** Report it loudly in the proposal.                                                   |
| Implementation plan                           | Code complete, operation blocked by an outside party | Harvest, then delete. The block is a live fact. Carry it to the status document and the runbook. |
| README, design notes, architecture            | It holds a plan or a status section                  | Move that section where the repository keeps status. Keep the document.                          |
| Status document or priority list              | An item whose work is finished                       | Harvest, then delete the item. Never check it off, date it, or move it to a "Completed" section. |
| Status document or priority list              | A "Completed" or "Done" section                      | Harvest, then delete the section.                                                                |
| Status document or priority list              | An item that mixes finished and open work            | Harvest the finished part, then delete it. Keep the open work.                                   |
| Design spec                                   | Work shipped                                         | Harvest, then delete                                                                             |
| Plan or design spec                           | Shipped, but users have not evaluated it, or it changes often | Keep. Feedback still needs its context. Revisit later. |
| Design spec                                   | Superseded by a later spec                           | Harvest both, delete both, write one successor                                                   |
| README, design notes, architecture            | Any                                                  | Update in place. Never delete.                                                                   |
| Measured external fact (hardware, vendor API) | Any                                                  | Keep. Correct it if the code disproves it.                                                       |
| Any document                                  | It stays true, and its filename carries a date       | Rename it without the date, then repair the references. A date claims a point in time.           |

If a document does not fit a row, stop and ask. Do not invent a new disposition.

**This table beats Step 1.** Triage narrows the reading. It never overrules a
disposition. A shipped spec is harvested and deleted whatever its commit count
says.

## Step 3 — Verify claims only in survivors

You read every document. You audit only the ones that stay.

| Disposition          | How to read it                                                          |
| -------------------- | ----------------------------------------------------------------------- |
| Keep or update       | Check every claim against the code. A reader will act on this document. |
| Harvest, then delete | One pass, for the harvest in Step 4. Do not audit claim by claim.       |

An audit of a document you then delete buys nothing. This is the difference
between an affordable audit and an expensive one.

Give each document its own subagent when the harness allows one. If the user's
own instructions name a preamble for subagent prompts, prepend it to every
subagent prompt.

## Step 4 — Harvest

Ask one question of each document you will delete:

**What does this say that the code cannot say?**

These answers survive. Everything else is a slower copy of the code.

| What survives                                                 | Where it goes                                                                              |
| ------------------------------------------------------------- | ------------------------------------------------------------------------------------------ |
| A decision and the reason for it, including what was rejected | The design or architecture document Step 0 found                                           |
| A measured external fact no vendor doc carries                | The document Step 0 found for that subject                                                 |
| A trap a reader will fall into at one site                    | A comment at that site, in the code or in the configuration file                           |
| An instruction an operator acts on                            | The operator-facing file: a README, an `.env.example`, a script usage header, or a runbook |

Rules for the destinations:

- Send content only to a destination Step 0 found. If none fits, create a
  document of a type the repository already uses.
- A document with a date in its filename is never a destination. It records one
  moment, so a harvest never edits it. Its own fate is a disposition: delete it,
  keep it unchanged, or rename it.
- Several successor documents are fine. Organize by subject, not by source
  document.
- Write what is true now. Never describe how the code got there.
- A `file.py:42` anchor rots. Name the symbol instead.
- Reference another file with a relative markdown link, never a bare path.

A measured fact earns its own document when a reader will go looking for it by
subject. One sentence that exists only to support a decision stays with that
decision. If you cannot name the subject a reader will search for, it is not a
resource.

## Step 5 — Propose

Give the user the table, the two counts below it, and nothing else:

| Document | Lines | State and the evidence for it | Disposition | What
survives, and where it goes |

List every in-progress plan you skipped, at the top, alone.

Grep the whole repository for the name of each document you propose to delete.
Source comments, docstrings, READMEs, and other documents all point at these
files. Those references break on the day you delete the document.

**Then grep for the citation style as its own command.** A citation such as
`Task 7` or `spec §2f` names no file. A grep for the filename never finds it. A
sweep that searched the filenames alone reports a clean result, and it leaves
every task number dangling. Search the source tree, not only the documents.

**A rename or a rewrite breaks a reference into a document you keep.** The file
still exists, so a link check passes it. Grep for every heading you rename or
drop. A comment that names a section by its title, and a markdown anchor such as
`#phase-1-intake`, both break in silence.

Report two counts under the table: the total line reduction, and the number of
references you will repair. Group the references by citation style, one line
each. The user needs the blast radius, not the list.

**A surviving document can rest on a document you delete.** A reference is not
always a pointer. It can be a premise: the survivor states a conclusion, and it
cites the source for the evidence. Move that evidence into the survivor before
you delete the source. A repaired link does not help a document that lost its
footing.

Then audit the files a reader acts on, whatever the repository calls them: a
project `README`, an `.env.example`, a script usage header, a runbook. A stale
claim and a wrong instruction name no document, so the reference grep is blind
to both. The document you propose to delete is often the only place the correct
instruction lives.

**A link gate that enumerates with `git ls-files` cannot see an untracked
file.** An untracked survivor holding a dead link passes every run. Check each
untracked document by hand, and never read a clean gate as proof.

Then stop. Wait for the answer.

## Step 6 — Apply

After the user confirms, work in this order:

1. Write the successor content.
2. Delete the sources.
3. Repair the references you counted in Step 5. A reference to a harvested
   reason points at its new home. A reference to a deleted section names the
   symbol instead. A premise moves into the document that rests on it. A
   reference to a heading you renamed takes the new heading.
4. Run the `writing:prose-gate` skill on every document you wrote.

**A move commits you to a rewrite.** A diff shows moved prose as a delete and an
add. The prose checker therefore reads every moved line as new, and it reports
each violation the source already carried. Count that cost before you propose a
move or a split. The user must hear the number, not learn it after the move.

Leave the working tree updated. Do not offer a commit message. Several review
rounds come before a commit, and the user asks for a message when the reviews
end.

## Scoping a large backlog

Start with the oldest documents, whatever the size of the backlog. Age
correlates with rot and with a settled answer about what shipped. A recent
project is often still in active change, and the documents that built it still
help.

For more than about 15 documents, propose a batch. Batch by project or by
feature, not by document age. A plan, a design, and a spec for one feature
harvest into one destination, and the reference repair stays inside that
project. Take the oldest project first. Report the remainder and let the user
decide whether to continue.

## Rationalization table

| Excuse                                                                       | Reality                                                                                           |
| ---------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------- |
| "The repo keeps every completed plan, so deleting one breaks the convention" | An accumulated backlog is not a convention. It is the problem you were asked to fix.              |
| "A status header at the top makes the stale document safe"                   | A reader who trusts the header still reads the wrong body below it. Delete it.                    |
| "Correcting the body is safer than deleting it"                              | Now you maintain two authorities. The code is the authority.                                      |
| "It is a point-in-time record, so freezing it preserves history"             | `git log` preserves history. The working tree is for what is true now.                            |
| "The boxes are all checked, so it shipped"                                   | Grep the source. Boxes record intent, not outcome.                                                |
| "The boxes are unchecked, so it did not ship"                                | Five plans in one audit left 246 boxes unticked for code in production.                           |
| "I should verify every claim before deleting"                                | Verify only what survives. Auditing a document you delete buys nothing.                           |
| "This document has no home to move to, so I will keep it"                    | Create the home, in a form the repository already uses. That is the deliverable.                  |
| "The dated design doc is the natural home for this fact"                     | A dated document records one moment. Put the fact in a document without a date, or create one.    |
| "A checked box with a date shows what shipped"                               | `git log` shows what shipped. A status document holds current and planned work only.              |
| "The neighboring project keeps a status document, so this one gets one"      | Step 0 says what this project uses. A neighbor's convention is not this project's.                |
| "The reference grep found nothing, so nothing breaks"                        | A wrong instruction in a README or an `.env.example` names no file. Read them.                    |
| "Renaming breaks every link, so the date stays"                              | Repair the links. A dated name claims the document is a record, and a living document is not one. |
| "The survivor only links the document, so a link repair is enough"           | Read what the link carries. If it carries a premise, move the premise first.                      |
| "The filename grep came back clean, so the references are clean"             | A pathless citation names no file. Grep the citation style as its own command.                    |
| "The document survives, so its references survive"                           | A dropped or renamed heading breaks an anchor. The file still exists, so the link check passes.   |
| "The link gate passed, so every link resolves"                               | The gate enumerates tracked files. An untracked document gets zero coverage. Check it by hand.    |
| "A move costs nothing, the words do not change"                              | The prose checker reads every moved line as new, and reports what the source already carried.     |

## Red flags

- You wrote a status header instead of proposing a delete.
- You justified keeping a document from what the other documents do.
- You read a plan body before triage assigned it a disposition.
- You corrected a spec you also plan to delete.
- You named a destination directory the repository does not already use.
- You deleted the only place that held a correct operator instruction.
- You deleted a document that a survivor cites for its evidence.
- A document that must stay true still carries a date in its filename.
- You grepped the deleted filenames, and you called the reference sweep done.
- You renamed or dropped a heading, and you did not grep for it.
- You read a clean link gate as proof, and an untracked document holds a dead
  link.
- You proposed a move without naming the prose rewrite it forces.
- Your proposal grew the documentation.
