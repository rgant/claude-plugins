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
