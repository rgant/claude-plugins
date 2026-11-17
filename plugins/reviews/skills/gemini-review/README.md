# gemini-review

This is an unofficial community skill. Google does not make or support it.

Claude Code starts a read-only Gemini review, then checks each finding against
the code before it reports. [SKILL.md](SKILL.md) holds the steps for Claude.
[scripts/agy-review.sh](scripts/agy-review.sh) runs the review, and `--help`
lists its options.

## Why

A second model catches defects that Claude misses. Past reviews from other tools
had two faults: claims the code did not support, and no knowledge of the repo
rules. This skill fixes both:

- The reviewer gets the repo rules and the review guide with the code.
- Claude checks every finding against the real code. A finding the code does not
  support goes to the "rejected" list.

## How it works

1. The script copies the review inputs into a throwaway folder under `$TMPDIR`.
   For `--uncommitted`, the inputs are the diff against `HEAD` and full copies
   of each changed or untracked file. Paths after `--uncommitted` limit the
   inputs to the changes under those paths.
2. It writes the repo's `CLAUDE.md`, `AGENTS.md` and `GEMINI.md` into one
   `AGENTS.md` in that folder, because agy loads `AGENTS.md` and not
   `CLAUDE.md`. If `AGY_REVIEW_STANDARDS` names a file, its text goes first in
   that `AGENTS.md`. agy does not follow a Claude `@` import, so the script adds
   the text in whole.
3. If `AGY_REVIEW_GUIDE` names a file, the script copies it in as
   `REVIEW-GUIDE.md`. The `writing` plugin has a review guide at
   `plugins/writing/guides/code-review.md` in this repo.
4. It runs `agy --sandbox --output-format json -p` in that folder, with the
   Google key variables removed from the environment.
5. It keeps `result.json`, `review.md` and the workspace in the run folder.

agy also loads `~/.gemini/config/AGENTS.md`. Keep that file free of rules for
an agent that writes or starts subagents. agy cannot read a file outside the
review folder, and a rule that names one can stop the review. A link to
`plugins/writing/standards.md` in a clone of this repo is safe.

A review is complete when `review.md` holds findings or a "No findings" line.
If it holds neither, the script exits 2.

## Decisions

**Antigravity CLI, not Gemini CLI.** Gemini CLI stopped serving personal Google
accounts on 2026-06-18. A login now fails with
`IneligibleTierError: This client is no longer supported for Gemini Code Assist for individuals`.
Antigravity CLI (`agy`) is Google's replacement
([gemini-cli issue #28229](https://github.com/google-gemini/gemini-cli/issues/28229)).

**Subscription login, not an API key.** An account login uses the flat-fee plan
allowance. An API key bills per token. The script removes `GEMINI_API_KEY`,
`GOOGLE_API_KEY` and the other Google variables, so agy can only use the login.

**A throwaway folder, not a read-only flag.** agy has no headless read-only
mode. Tests on agy 1.2.11 showed these results:

- Default mode wrote a file inside the workspace when asked. It soft-denied a
  shell command.
- Plan mode (`--mode plan`) ran to the print timeout with no review, because it
  waits for a plan approval.
- Reads outside the workspace are denied.

So the real repo is never in the agy workspace. A write can only land in the
copy.

**Terms of use.** The Antigravity FAQ says: "Wrapping agy inside third-party
coding agents or applications ... is not supported under consumer plans." Rob
reads "wrapping" as building agy into another product. This skill runs the
official `agy` with documented flags, the same as a person at a terminal. A
community reply on the Google AI forum agrees, but no Google staff answered
([forum thread](https://discuss.ai.google.dev/t/clarification-on-codex-claude-skill-invoking-the-official-agy-cli-through-a-local-powershell-wrapper/185949)).
This skill meets the conditions in that reply:

- Send agy a real task.
- Use documented flags only.
- Never bundle agy or credentials.
- Label the skill as unofficial. The top of this README does that.

**Quota.** Thinking tokens are most of the cost of a review. `--effort low` or
`--effort medium` lowers it. `--max-bytes` refuses a large input before agy
starts.

## Limits

- The reviewer sees only the copied files. It cannot follow an import to a file
  outside the target. It names a file it needed under "Missing context".
- A review of 230,572 bytes at `--effort medium` ran to the print timeout and
  returned no text. The input was under `--max-bytes`.
- Each run uses the agy model and effort in
  `~/.gemini/antigravity-cli/settings.json`, unless you give `--model` or
  `--effort`.

## Setup on a new machine

1. Install agy: `brew install --cask antigravity-cli`.
2. Run `agy` once and log in with the Google account.
3. In the Antigravity settings, turn off telemetry and data collection.
4. Give agy the shared standards. Set `AGY_REVIEW_STANDARDS` to
   `plugins/writing/standards.md` in a clone of this repo. The script also adds
   `guides/writing-for-people.md` from the same folder. A link from
   `~/.gemini/config/AGENTS.md` to `standards.md` gives agy that file only.
5. Install this plugin. See the [repo README](../../../../README.md).
