# Shared CLAUDE.md

[CLAUDE.md](CLAUDE.md) holds Rob Gant's shared rules for Claude Code: the
writing standards, the explanation guide, the plan guide, and the code
review guide. It imports them
from the [writing](../plugins/writing/) plugin, so each rule has one copy.

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
