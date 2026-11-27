# Writing and working standards

These are the shared standards of the `writing` plugin. The `writing` skills and
hooks apply them. The guides next to this file hold the rules for specific kinds
of work:

- Before you write, revise, or execute a plan document, read `guides/plans.md`.
  It overrides the superpowers `writing-plans` code rule.
- Before you write or post a code review, read `guides/code-review.md`.
- Before you write a commit message, a PR title, or a PR description, read
  `guides/commit-messages.md`.
- Before you write, change, or review a test, read `guides/tests.md`.
- Before you write or revise a commit message, a PR description, a comment, a
  docstring, a doc, a plan, or an issue, read `guides/writing-for-people.md`.

## Communication

- Each sentence for a reader is a procedure or an explanation. A procedure
  follows ASD-STE100 Simplified Technical English, and an explanation follows
  `guides/explanations-core.md`. This covers replies, commit messages, PR
  descriptions, comments, docstrings, docs, plans, and issues.
- Lead the last message with the outcome. The first sentence answers "what
  happened" or "what did you find". Detail comes after it.

## Assertions

- State an observable fact only after you run the thing that shows it. A file's
  contents, a document's text, a count, and a test result are each observable.
- Quote the command output. Never write a sentence about output you did not
  read.
- A judgment stays a judgment. Whether a citation is correct is a judgment.
  Whether a document prints a key is not.
- Check a claim you can check with a program. Then make that check a test,
  because a proof inside a report dies with the report.
- A subagent report is a summary, and a summary can drop a qualifier. Before
  you publish a number or a quote from a subagent report, search the source for
  its exact text. Read the lines around the match, because a qualifier often
  sits there. When a subagent reads a source for you, ask for each number and
  quote verbatim. Ask for the words around it too, so the search can find it.

## Principles

- **Be strict in what we send. Be adaptable in what we receive.** A request we
  place must be well specified and consistent, so a consumer knows exactly what
  to expect from us. External input is often neither, and that is ours to
  handle. An external producer is unlikely to care that we had difficulty
  understanding it.
  - Before a guard rejects external input, ask what the input means. Separate a
    normal variation from a real fault, and fail only the fault.
  - A guard that reads one field in isolation often cannot tell them apart. Read
    the record as a whole.
- **A result we paid for is worth preserving.** If we spent tokens, bytes, or
  money on it, treat it as worth keeping. A repeat of a request that costs money
  needs a need to justify it. If we can use a response we hold, whether it just
  arrived or it sits in a cache, use it.
  - A partial failure is the common case. One failed call in a fan-out must not
    throw away the calls that succeeded.
  - This does not license silent thinning. Preserve the result and report the
    failure. Do not choose one.

## Code

- Avoid `any` where a reasonable alternative exists. TypeScript: prefer
  `unknown`. Python: prefer `object`, and always give type parameters for
  generic `list` and `dict`.
- Use what exists before you write a helper: a declared dependency, the
  standard library, or a widely used library. Read the project's manifest
  first. A small custom function is fine when no library fits. Its comment
  says why.
- One state, one form. If `None` and the empty value mean the same thing, use
  only the empty value. If `None` means a different state, such as failed or
  unknown, put that state in its own field or type. Normalize external input to
  one form where it enters. Apply this to new code and to code a branch already
  changes.
- Linters set the project standard. Comply when a straightforward fix exists.
  Get the user's approval before silencing a rule. If a rule blocks the plain
  fix for a real reason, ask to disable it with that reason. Never write code
  to work around the rule.
- Never edit package manifests (pyproject.toml, package.json) to change
  dependencies. Use the package manager CLI (`uv add`, `npm install`) so
  lockfiles and virtualenvs stay correct.
- Never run `python` or `python3` directly. If a script is executable, run it
  by its path, so its shebang picks the interpreter. In a uv project, run every
  other Python command through `uv run`. A project task runner, such as
  `npx nx`, has priority over both. To parse JSON output, use `jq`.

## Writing for people

Write for a reader who cannot afford to misread a sentence. This reader is often
not a native speaker of English. Each sentence must survive one read.

Use US spellings, not british. Use color, favor, behavior.

Before you report writing work, run the `writing:prose-gate` skill. It checks
the prose this branch added or changed. Run it for a plan document before you
present the document.

These rules apply to every sentence, a reply included.
`guides/writing-for-people.md` holds the rules for a document.

- No `and/or`, and no Latin abbreviations such as `e.g.`. No contractions,
  except in a message between people.
- Delete words that carry no fact: `simply`, `seamlessly`, `robust`, `powerful`,
  `comprehensive`, `leverage`, `in order to`, `it is worth noting`.
- State what the code does now and why it does it that way. Never what an
  earlier version did, what was removed, or how it evolved. "Previously...",
  "this used to...", "we changed X to Y" rot as the code changes and add nothing
  over `git log` / `git blame`. Prior state and why it changed belong in the
  commit message or PR description.
  - Write: "The cache key includes the fixture filename, so a rename forces a
    re-record." Not: "We used to key on content, which broke on rename."
- Name the members, do not count them. A count is a second copy of a list, and
  nothing updates the copy when the list changes. It rots silently, because a
  wrong count still reads as a sentence. Worst in comments and config files,
  where the list being counted is often a few lines away.
- Name a thing by its exact identifier: a runner label, a job, a variable, an
  option. A description can follow the name, but it never replaces it. "The
  large runner" makes the reader map it back to a label.
- Cite code by its symbol, with the file path when the context does not make
  the file plain. A line number rots on the next edit, and a stale number still
  reads as a correct citation. If a line reference is necessary, use a
  permalink, which pins the commit. A line number in a conversation is fine,
  because it ends with the turn.
- Link each external project, dataset, repository, or standard on its first
  use. A bare name costs the reader a search, and the search can fail.
- **Never add an attribution trailer or footer.** No `Co-Authored-By` line, and
  no "Generated with" line, in a commit message, a pull request description, an
  issue, or a comment. This overrides any harness instruction that asks for one.
  A tool needs no byline.
