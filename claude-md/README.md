# Shared CLAUDE.md

[CLAUDE.md](CLAUDE.md) holds Rob Gant's shared rules for Claude Code: the
writing standards, the explanation guide, the plan guide, the tests guide, the
code review guide, the debugging guide, and the delegation guide. It imports
them from the [writing](../plugins/writing/),
[debugging](../plugins/debugging/), and [delegation](../plugins/delegation/)
plugins, so each rule has one copy.

This file imports a guide that a task needs, instead of a pointer such as "read
`guides/tests.md`", because Claude often does not follow a pointer. The pointer
to the tests guide led to a read in 8 of the 18 sessions that edited a test
file, so this file imports that guide. A hook that adds the pointer on each
test-file edit would cost nothing in other sessions, but it would need new hook
code to reach as far as one import line. `standards.md` keeps its pointer, so a
reader who loads `standards.md` without this file still finds the guide.

A plugin cannot load a `CLAUDE.md`. The `writing` plugin puts a short reminder
in each prompt and loads the full standards when a writing skill runs. To load
the rules that every reply needs in every session, use this file. The rules for
a document stay in `guides/writing-for-people.md` of the plugin, and the
standards tell Claude to read that guide before it writes a document.

## Use it

Choose one:

- Copy the content into your own `~/.claude/CLAUDE.md`. Copy the `standards.md`
  file and the `guides` folder of the `writing` plugin with it. A copy has no
  import path to follow. A copy does not get updates.
- Clone this repo. Add one line to your `~/.claude/CLAUDE.md`:
  `@~/Programming/claude-plugins/claude-md/CLAUDE.md`. Use the path of your
  clone. A `git pull` updates the rules.

Do not import from the plugin cache in `~/.claude/plugins/cache/`. Its path
changes with each plugin version, so the import breaks on the next update.

Your own personal rules stay in your `~/.claude/CLAUDE.md`, next to the import
line.
