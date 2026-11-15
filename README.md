# claude-plugins

Rob Gant's Claude Code plugins, shared as the `rgant` plugin marketplace.
Install only the plugins you want. Each plugin works on its own.

## Plugins

- [writing](plugins/writing/) holds the writing standards: ASD-STE100
  Simplified Technical English for procedures, and a guide for explanations. It
  also holds the skills that apply them, and hooks that check prose as Claude
  writes it.
- [reviews](plugins/reviews/) gets second-opinion code reviews from other
  models. See [gemini-review](plugins/reviews/skills/gemini-review/README.md).
- [statusline](plugins/statusline/) is a status line with the folder, git state,
  model, context use, and session tokens. Run `/statusline:setup` after you
  install it.

A plugin skill runs as `/<plugin>:<skill>`, for example `/writing:prose-gate`.

## Install

The `writing` plugin runs its Python scripts through [uv](https://docs.astral.sh/uv/), with Python 3.14 or later. Install uv first. uv finds an installed Python 3.14 or later, or downloads one. The `statusline` plugin needs `jq`.

The `reviews` plugin needs `jq` and the agy (Antigravity) CLI, signed in to a
Google account. A review sends the files under review to Google.
[Setup on a new machine](plugins/reviews/skills/gemini-review/README.md#setup-on-a-new-machine)
gives the steps.

Install one plugin in one step, on Claude Code 2.1.275 or later:

- `/plugin install writing --marketplace rgant/claude-plugins`

Or add the marketplace, then install each plugin you want:

- `claude plugin marketplace add rgant/claude-plugins`
- `claude plugin install writing@rgant`

To work on the plugins, add a local clone as the marketplace:
`claude plugin marketplace add ~/Programming/claude-plugins`. A local-path
marketplace reads the files live from the clone. An edit takes effect at the
next session start, or after `/reload-plugins` in a session
([plugin marketplaces](https://code.claude.com/docs/en/plugin-marketplaces.md)).

## Rob's CLAUDE.md

A plugin cannot load a `CLAUDE.md`. Rob's shared rules are in
[claude-md/](claude-md/README.md), to copy or to import.

## Layout

- [.claude-plugin/marketplace.json](.claude-plugin/marketplace.json) lists the
  plugins.
- Each plugin is a folder in `plugins/`. The marketplace entry name and the
  `name` in the plugin's `plugin.json` must be the same.
- Each plugin stands alone. A plugin never adds a hook or context for a
  concern of a different plugin.
- A plugin update replaces the plugin folder. Keep plugin state in
  `${CLAUDE_PLUGIN_DATA}`.
- `tests/` holds checks for the whole repo. Each plugin keeps its own tests in
  its own `tests/` folder.

## Checks

CI runs these checks on each push. Run them locally before a pull request:

- `claude plugin validate .`
- `uvx ruff check .` and `uvx ruff format --check .`
- `shellcheck` on each `.sh` file, and `actionlint`
- `uv run --no-project --python ">=3.14" tests/test_no_private_paths.py`
- Each `test_*.py` script in a plugin `tests/` folder, run the same way

## License

[MIT](LICENSE). A file copied from another project keeps its own attribution.
