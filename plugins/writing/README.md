# writing

The `writing` plugin holds Rob's writing standards, the skills that apply them,
and hooks that check prose as Claude writes it. [standards.md](standards.md) is
the entry point. The guides in [guides/](guides/) hold the rules for each kind
of work.

## Decisions

**Two registers.** Each sentence is a procedure or an explanation. A procedure
keeps strict ASD-STE100, because STE was built for steps and warnings. An
explanation follows [guides/explanations-core.md](guides/explanations-core.md),
because it needs words that STE bans or discourages, such as "would" and
"because". Under the STE ban on "would", an author wrote "A deployment that
forgets the variable then connects to a sandbox" about a default that does not
exist. The sentence states a hypothetical as a present fact, so the sentence is
false.

**Positive guidance first, and the checks last.** Each rule says what to write,
with its reason and a good passage. Anthropic's prompting guide says "Tell
Claude what to do instead of what not to do". The positive-instruction spec of
the superpowers plugin for Claude Code measured a prohibition against a positive
recipe, and the prohibition did worse than no guidance. The core file holds no
before-and-after pair, because every session loads it, and a bad passage there
would be one more example for Claude to imitate. The full guide,
[guides/explanations.md](guides/explanations.md), holds the pairs.

**The checks keep their ban form.** A ban works well at review time. What the
register changes is how hard each check bites:

- `should` and `may` are hard in both registers. A requirement becomes `must`,
  and a recommendation becomes an action and its condition.
- The semicolon is hard in both registers, because a semicolon chain is one of
  the faults that the standards exist to stop.
- In an explanation, `would`, `could`, and `might`, the length limit, and the
  em dash are advisory. `might` is advisory because two approved public quotes
  use it correctly.
- An "-ing" word after a form of "be" and before a noun is the advisory
  `ING-READ`. The "-ing" word can be a modifier of that noun, as in "are
  working documents". After a comma, an "-ing" word opens a trailing clause, so
  `ING-VERB` is always hard there.

**The gh hook denies only on a rule that is hard in both registers.** A PR or
issue body is mostly explanation, so a length or soft-modal count never denies
there, whatever register the classifier gives.

**The classifier errs toward a command.** `lib/register.py` is a regex
heuristic, so it misreads some sentences. Some imperatives are also nouns, such
as "set" and "read". A sentence that opens with one of these words is a fact
only when the next two words pass two tests. The second word is not an article,
a pronoun, a preposition, or a question word. The third word is a form of "be",
"have", or "do", or a modal. "Name collisions would break the registry" is an
example. Every other sentence that opens with one of these words stays a
command. A command read as a fact would lose the strict limits, so the
classifier accepts the opposite error: "Read access stops" gets the procedure
rules.

**The guide is its own test set.** `tests/test_explanation_guide.py` reads the
quoted passages in `guides/explanations.md`, so no second copy of the examples
can go stale.

**The cold-reader check is advisory.** The `writing:prose-gate` skill runs it
for a long document. It never runs for a commit message or a code comment,
because a subagent call costs too much there.

**The model evaluation runs by hand.** Each run of
[evals/explanation_eval.py](evals/explanation_eval.py) costs tokens, so the
evaluation is not in CI. It shows each pair of rewrites in a random order, with
the labels in a separate key file, so the reader judges the rewrites before the
reader knows their source. In Claude Code 2.1.325, `--bare` skips hooks and
CLAUDE.md files, but it still lists the installed plugins. So the harness turns
off tools and slash commands, and a leak probe stops the run if the standards
reach the context.

**An external skill is not the base.** `jlreyes/agent-writing-skills` comes
closest to a positive explanation standard. It has no examples, and it does not
fit the hooks or the prose gate.

**The feedback loop learns from edits, not from the user's own messages.** The
`writing:reviewing-edit-feedback` skill compares each draft that Claude wrote
with the text that the user sent. The user's own quick messages can carry
spelling and punctuation errors that Claude must not copy, so they are not a
source.

**The feedback loop covers messages, PR descriptions, and ticket
descriptions.** A commit message is out, because its main reader is a model. A
PR comment, a review, and a ticket comment are out too. Docs and code comments
wait for a later build, because an `Edit` holds only a fragment of a file, and
that source carries the fewest edits.

**The transcripts are the source, so no hook captures a draft.** A Claude Code
transcript holds each reply and each tool call with its full input. Claude Code
deletes a transcript after 30 days by default
([claude-directory](https://code.claude.com/docs/en/claude-directory.md)). So
the `SessionStart` hook starts the extraction once a day, and the pairs reach
the store even if the user skips reviews. The hook runs on startup and on resume
only, because a reminder after `/clear` or a compaction would interrupt work in
progress.

**A PR or a ticket keeps its first draft.** The user asks Claude for each later
edit, so the requests between the first draft and the last edit are the
feedback. A PR final waits until the PR is merged or closed, because the user
can still edit an open PR. A ticket final waits 7 days, because a ticket has no
state that marks the end of its edits.

**A rule change needs more than one record with the same correction label.**
One edit can be taste or a slip, and a rule for each edit would make the guides
grow and conflict. The labels persist across reviews, because a weekly batch is
small, and a correction often reaches a second record only in a later week.

## Learning from edits

The `writing:reviewing-edit-feedback` skill turns the user's edits to Claude's
drafts into proposed rule changes.

1. When Claude drafts a Slack or Teams message, paste the version you send back
   into the session after `SENT>`.
2. When the session-start reminder says a review is due, run
   `/writing:reviewing-edit-feedback`.
3. Approve or decline each proposal that the review shows.

The store is `${CLAUDE_PLUGIN_DATA}/feedback`. It holds messages to coworkers
and text from client repositories, so it never enters a repository.

A ticket script belongs to its project, so the store holds a `tickets.json`
that describes each one. `TicketTool` in
[skills/reviewing-edit-feedback/extract_feedback.py](skills/reviewing-edit-feedback/extract_feedback.py)
names the fields of each entry. If `tickets.json` is absent, the review skips
tickets.

Warning: copy the store before you uninstall the plugin. By default, an
uninstall deletes the plugin data, and the store goes with it
([plugins-reference](https://code.claude.com/docs/en/plugins-reference.md)).

## Adding an example

An example in `guides/explanations.md` is public, so it must carry no private
detail.

1. Remove from the example each name that `tests/private-names.txt` lists.
   Remove each person, ID, and cloud resource name too.
2. Move a client domain to a neutral domain with the same logic. For example, a
   contract expiry check becomes a subscription expiry check.
3. Quote a public passage verbatim. Give its source and its license in the
   "Sources quoted" section of the guide.
4. If a verbatim quote breaks a hard rule, add it to `ALLOWED` in
   `tests/test_explanation_guide.py`.
5. From the repo root, run these two tests with
   `uv run --no-project --python ">=3.14"`:
   `plugins/writing/tests/test_explanation_guide.py` and
   `tests/test_no_private_paths.py`.
