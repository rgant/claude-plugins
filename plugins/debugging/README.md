# debugging

The `debugging` plugin holds a debugging method for Claude. Each gathered fact
is a constraint, and a hypothesis survives only if it fits every constraint.
The method comes from Cindy Sridharan,
[How to effectively debug when you no longer understand the code](https://copyconstruct.medium.com/how-to-effectively-debug-when-you-no-longer-understand-the-code-bd3dcb2c5f7b),
October 2026.

- [guides/debugging-core.md](guides/debugging-core.md) holds the rules, one or
  two sentences each.
- [guides/debugging.md](guides/debugging.md) gives the reason and an example
  for each rule.

## Use it

Install it with `/plugin install debugging --marketplace rgant/claude-plugins`,
on Claude Code 2.1.275 or later.

An install alone loads nothing, because a plugin cannot load a `CLAUDE.md`.
Import the core from a `CLAUDE.md` with an `@` line. The shared
[claude-md/CLAUDE.md](../../claude-md/CLAUDE.md) of this repo does that. A
hook could load the core for a user who only installs the plugin, but that hook
is not worth new code while one person uses the plugin.

## Decisions

**A core file that every session loads.** A skill loads only when its
description matches the task, and few sessions called the superpowers
`systematic-debugging` skill by name. A pointer line in a `CLAUDE.md` is often
not followed, as [claude-md/README.md](../../claude-md/README.md) records. So
the core is short, and it points at the full guide for the reasons.

**It adds to `systematic-debugging`.** The core keeps that skill's phases and
names the steps it overrides. Where the two differ, the core wins.

**The table is in the reply.** The user sees each hypothesis and the facts
against it. The first header cell is `Hypothesis`, so the session audit can
find the table.

**Ideas only.** The guides copy no text from the article or from
[daneel](https://github.com/Gunther-Schulz/daneel), the source of rules 4 and
7. Neither states a license that permits a copy.

## Measurement

The `debugging` check in
[tools/audit_sessions.py](../../tools/audit_sessions.py) counts these events in
each session:

- a run of `systematic-debugging`
- a `Read` of a guide file
- a reply with the table
- a user prompt with a word that suggests a bug

A session with bug words and no table is a reason to read that session. The
flag reads only the replies of that session, so a table that a subagent wrote
does not clear it. An `@` import loads the core with no tool call, so the
`Read` count shows only reads of the files, such as the full guide behind the
pointer.

If replies still have no table after the import, the next step is an evaluation
that runs a model with and without the guide. That evaluation costs API calls,
so it waits for the audit result.
