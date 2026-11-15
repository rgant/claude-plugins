# Use cases beyond documentation

STE was built for aircraft maintenance manuals. The same properties — one
meaning per word, short sentences, condition-first commands — transfer to any
text where misreading has a cost. By the end of Issue 8, 64% of registered STE
users were outside aerospace and defense.

Each case below names the mode and the adaptations.

## Error messages and CLI output

Mode: procedural. This is the highest-value target: an error message is a 2 a.m.
instruction to a stressed reader.

Pattern: state what happened (past simple), state the cause if known, give the
command or condition to fix it.

> **Before:** Oops! Something went wrong while attempting to establish a
> connection. Please ensure your credentials are properly configured and try
> again. **After:** Connection to the database failed. The password for user
> `app` was not correct. Set `DB_PASSWORD` and connect again.

## Runbooks and standard operating procedures

Mode: strict-leaning procedural. This is STE's home turf — an on-call runbook is
a maintenance manual.

- Every step imperative, one instruction per step, conditions first.
- Warnings before the step, command first, risk second.
- 20-word limit enforced hard: an operator under pager stress reads each
  sentence once.

## Incident reports and postmortems

Mode: descriptive. Simple past only. A timeline in the present perfect, such as
`we have identified`, hides when things happened.

> **Before:**
> `We have identified an issue that may have impacted some users' ability to access the service`.
> **After:** Between 14:02 and 14:31 UTC, 12% of requests failed. A deploy at 14:00 removed the cache warmup step.

STE bans hedges such as `may have impacted`. The report states what is known,
and it says "unknown" for the rest. This reads more honest because it is.

## Commit messages and PR descriptions

Mode: imperative subject, explanation body. The subject keeps strict STE: one
imperative line. The body is an explanation, so it follows
`guides/explanations.md` of the writing plugin, not the STE word limit. Apply
the substitution table to the body too. Delete "this PR aims to".

## API changelogs and release notes

Mode: descriptive. One entry, one change, one sentence where possible.
"Breaking:" entries follow the warning pattern — command first: "Update your
calls to `v2/users`. The `name` field split into `first_name` and `last_name`."

## Instructions for AI agents (prompts, AGENTS.md, skills)

Mode: procedural. A system prompt is a procedure executed by a reader with no
ability to ask questions — the exact reader STE was designed for.

- One instruction per sentence keeps rules independently quotable and hard to
  half-follow.
- One word, one meaning prevents the model from treating "check", "verify", and
  "validate" as three different operations.
- Condition-first ("If the build fails, stop") beats trailing conditions, which
  models drop.
- No `should`, because a model reads `should` as optional. Write `must`, or
  state the action and the condition that calls for it.

## Support macros and status-page updates

Mode: descriptive. In an explanation, a sentence over 25 words gets a second
read. It stays whole if it carries one line of reasoning. Non-native readers are
the majority of many user bases. Do not write
`we sincerely apologize for any inconvenience this may have caused`. State the
facts: "The API was down for 18 minutes. Uploads made during this time were
saved and will process today."

## Translation and localization prep

Mode: strict. STE's original purpose was to make English readable for non-native
maintenance crews, and it doubles as pre-editing for machine translation. One
meaning per word plus complete grammar (articles, "that") removes most
translation ambiguity. If your docs get localized, STE cuts the error rate and
the cost.

## UI copy and empty states

Mode: procedural, hard length limits. Buttons and labels are technical names
(exempt). Body copy follows the rules: "No projects yet. Create a project to
start." Nothing else survives at this length anyway.

## Where STE does not fit

Marketing pages, launch posts, blog voice, brand writing. STE deletes persuasion
on purpose. Write those in your own voice. Then use STE for the docs that
the landing page links to.
