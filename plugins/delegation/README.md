# delegation

The `delegation` plugin holds rules for when Claude gives work to a fork and
when it gives work to a fresh subagent. The ideas come from the sources below.

- [guides/delegation-core.md](guides/delegation-core.md) holds the rules.

## Use it

Install it with `/plugin install delegation --marketplace rgant/claude-plugins`,
on Claude Code 2.1.275 or later.

An install alone loads nothing, because a plugin cannot load a `CLAUDE.md`.
Import the core from a `CLAUDE.md` with an `@` line. The shared
[claude-md/CLAUDE.md](../../claude-md/CLAUDE.md) of this repo does that.

## Decisions

**A plugin of its own.** The routing of work is not a writing rule, so it stays
out of the `writing` standards. The rule that a subagent's number or quote must
be found in the source before it is published stays in the Assertions section of
[standards.md](../writing/standards.md), because it governs what a claim rests
on.

**One short core.** The article reports that a pile of small directives, each
added for one bad case, contradicted itself, so the agent could quote whichever
directive fit the choice it wanted. Each rule here covers a different decision,
and a new case changes a rule instead of adding a directive beside it.

**Rule 1 accepts the cost of a fork.** A fork reads its whole inherited context
on every turn, so a fork in a long session costs more than a brief. Rule 1
still sends a single plan to a fork, even when its decisions seem to fit in a
brief. A brief looks complete to its writer, and rule 3 exists because that
judgment fails. Competing plans are the one exception. Each goes to a fresh
`Plan` agent, so each plan starts independently, and the Measurement section
says how to check that choice.

**Rule 5 is not from the article.** It comes from rule 9 of the
[debugging core](../debugging/guides/debugging-core.md): a reviewer must look
for a fact that contradicts the hypothesis, and a fork starts out agreeing with
the hypothesis.

**Rule 6 is not from the article.** The Assertions section of
[standards.md](../writing/standards.md) requires a check in the source of each
number or quote from a subagent. For a small source, the check in the source
costs about as much as a read of the source, so the subagent saves nothing.

**No rule for a fork that misreads its start.** The article reports a fork that
took the fork request as an instruction to itself. Claude Code tells each fork
that it is the fork and must not delegate again, so the harness covers that
case.

**No smart forks.** The article proposes a fork that keeps only the relevant
history, chosen by a separate selection model. The author's tool is unreleased
and untested. Oskar Austegard's delegating-with-context skill sends parts of
the transcript to a selection model, and nobody checked where that model runs.
A run on client work could send client content to an outside service.

**Ideas only.** The guide copies no text from the article. The article states
no license that permits a copy.

## Sources

Each source is a work in progress. Before you change a rule or accept a
rejected idea, read the source again at its current version. Compare it with
the version below.

- Nik van der Ploeg,
  [Subagents considered harmful?](https://nikvdp.com/notes/subagents-considered-harmful/).
  The page shows no date and no version. It was read on 2026-11-27. Rules 1 to
  4 come from it. The author calls his smart-fork tool untested.
- Oskar Austegard,
  [subagent-context-filter](https://github.com/oaustegard/experiments/tree/f10229611f338265b7b6445158c6ac7bc2eca959/subagent-context-filter),
  MIT, at commit `f10229611f338265b7b6445158c6ac7bc2eca959` of 2026-11-02. Its
  `RESULTS.md` is the source of the lookup sentence in rule 3. A brief found 82
  of 105 facts against 102 for the full transcript. Five briefs that sent the
  worker to a lookup account for the whole gap of 20 facts. Its own limits: 32 tasks, one model
  family, and executors with no tools. A worker with tools can find a fact in a
  file or in git, so rule 3 covers only a fact that exists in the conversation.
- Simon Willison,
  [Jev introduces a new shape of LLM](https://simonwillison.net/2026/Sep/21/jev/),
  2026-09-21. The post shows that Jev is a hosted API, which is the reason for
  "No smart forks".

## Measurement

The `delegation` check in
[tools/audit_sessions.py](../../tools/audit_sessions.py) counts these events in
each session:

- `fork`: an Agent call that starts a fork
- `fresh`: an Agent call that starts any other subagent
- `fresh_judgment`: a fresh call whose brief opens a sentence with a judgment
  verb and its object, such as "Decide whether" or "Recommend the"
- `plan_agent`: a call that starts the `Plan` agent

A session with a `fresh_judgment` count is a reason to read it against rule 1.
The read-only agents `web-fetch`, `Explore` and `claude-code-guide` never count
as judgment, because a judgment word in their brief names what to report, not
what to decide. A review brief can also ask for a recommendation. A
`fresh_judgment` count on a review is not a fault, because rule 5 gives a
review to a fresh subagent.

A session with a `plan_agent` count is a reason to read it too. Rule 1 gives
each competing plan to a fresh `Plan` agent, and nothing yet shows that the
agent works well or that a fork would do better. Read each plan for a decision
that the session settled and the plan missed or contradicted. If that happens
in more than one session, a brief does not carry the settled decisions well
enough. Then give competing plans to forks, and change rule 1.

The pattern counts only a verb with an object, because a bare judgment word
would match document labels such as "Design:" in briefs that only implement.
It misses a judgment brief phrased as a question, so the count is a lower
bound.

Rule 4 has no count. A fork that a fresh subagent starts shows as an ordinary
`fork`, so the audit cannot tell it from a fork of the main session.

A run of the audit appends to the totals file in `~/.claude/session-audit/`.
To try a change to the check without a record there, set
`SESSION_AUDIT_TOTALS` to a scratch file.

The counts show whether the routing changes. They cannot show whether a worker
had the context it needed. If the routing changes and the results do not, the
next step is an evaluation like the one in `RESULTS.md` above. That evaluation
costs API calls, so it waits for the audit result.
