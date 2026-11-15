---
name: setup
description: Install the status line from the statusline plugin into the user's own Claude Code settings. Use when the user runs /statusline:setup, asks to turn on this status line, or updates the statusline plugin.
disable-model-invocation: true
---

# Status line setup

A plugin cannot set the main status line. This skill copies the script out of
the plugin and points the user settings at the copy. The plugin cache path
changes with each plugin version, so a setting that points into the cache breaks
on the next update.

## Steps

1. Check that `jq`, `tput`, and `git` are on `PATH`. Run
   `command -v jq tput git`. If one is absent, stop. Tell the user to install
   it, for example `brew install jq` on macOS or `sudo apt-get install jq` on
   Debian or Ubuntu.
2. Read `~/.claude/settings.json`. If the file is absent, start from an empty
   JSON object.
3. If the file has a `statusLine` entry, show the entry to the user. Ask before
   you replace it. If the user says no, stop.
4. Copy `${CLAUDE_PLUGIN_ROOT}/scripts/statusline-command.sh` to
   `~/.claude/statusline-command.sh`. If that file exists and differs from the
   plugin copy, show the difference and ask before you overwrite it.
5. Set `statusLine` in `~/.claude/settings.json` to
   `{"type": "command", "command": "bash ~/.claude/statusline-command.sh"}`.
   Keep every other key unchanged. Write valid JSON.
6. Tell the user that the status line shows on the next prompt. Tell them to run
   `/statusline:setup` again after each update of the `statusline` plugin.
