# Writing for people

These rules add to "Writing for people" in `../standards.md`. They cover commit
messages, PR descriptions, comments, docstrings, docs, plans, and issues.

## The two registers

Each sentence is in one of two registers, and each register has its own rules.
A document often holds both, so the register belongs to the sentence or the
section, not to the whole file.

- A **procedure** tells the reader what to do: an instruction, a step, a
  warning, or a safety note. It follows ASD-STE100 Simplified Technical English.
- An **explanation** says what a system does and why: a design rationale, the
  descriptive part of a README, a docstring, a commit body, a PR description,
  or an issue body. It follows `explanations-core.md`.

## The procedure register

The `writing:simple-english` skill holds all 53 STE rules and is the authority
on the procedure register. Invoke it for a long procedure, a public procedure,
or a rewrite of someone else's procedure. Apply the rules below from memory in
every other case:

- Use the imperative mood. Write one instruction per sentence, in at most 20
  words.
- Put the condition or the command first (Rules 5.4 and 7.2). Write "If the
  build fails, read the log", never the reverse. A warning names the action
  before it names the risk.
- Do not use an em dash.

## The explanation register

`explanations-core.md` holds the rules for an explanation. Before a
larger writing task, read `explanations.md` too. A larger task is a PR
description, an issue or a ticket, a README, a design document, or a plan.

- An explanation has no fixed word limit. If a sentence runs past 25 words,
  read it again. If it carries one line of reasoning, keep it whole. If it
  holds separate facts, give each fact its own sentence.
- An em dash is a reason to read the sentence again. If the sentence needs the
  dash to hold together, split it.

## Modals

- A procedure uses only `can`, `will`, and `must`.
- An explanation can also use `would` and `could` for a case that is not real,
  and `might` for an outcome that is not certain. `can` states what is
  possible.
- Neither register uses `should` or `may`, except that an explanation in a
  message between people can use `should`. A requirement becomes `must`. A
  recommendation becomes an action and the condition that calls for it.
  - Requirement: "The worker must acknowledge the task." Not
    `the worker should acknowledge the task`.
  - Recommendation: "If the queue backs up, shorten the timeout." Not
    `you may want a shorter timeout`.
  - Possibility: "A restart can drop the task."
  - A case that is not real: "A default would carry a credential, so a
    deployment without the variable would connect to a sandbox."

## Both registers

- Simple tenses in docs, comments, plans, and commit messages. No present
  perfect. An explanation can use the past perfect for an event before another
  past event. A procedure uses only the simple tenses.
- An "-ing" word can be a noun or a modifier: "Retrying costs a call", "the
  failing test", "caching". This is a house exception to STE Rule 3.5.
- Never start a trailing clause with an "-ing" verb, as in
  `, ensuring the data stays valid`. It hides its subject. Write a second
  sentence with a real subject.
- No semicolons. Write two sentences, or join the two clauses with a word that
  names their relation, such as `because` or `so`.
- A message between people is a review body, a PR or issue comment, or a chat
  message. It can use the progressive ("I'm requesting changes") and
  contractions. An explanation in it can also use the present perfect
  (`I've requested access`) and `should` (`you should flag it`), because a soft
  recommendation between peers is what the writer means. An instruction in it
  uses neither. Keep short sentences and plain words. Docs, code comments, and
  PR descriptions use none of these forms.
- One word, one meaning, for the whole document. Pick one of `check`, `verify`,
  or `confirm`. Then use no other word for it.
- Code, identifiers, commands, file paths, and quoted errors stay exact. In a
  procedure, each one counts as one word toward the limit.

STE does not cover the rules below. They stay.

- Keep what the reader will act on. Cut the rest. Link the issue, file, or doc
  instead of explaining it inline.
- Do not document the obvious. If a flag name, a recipe name, or the tool's own
  docs already say it, do not repeat it. A comment explains a choice that a
  reader would not guess.
- Never copy code or config into a doc. Point at the file that holds it. A copy
  goes stale when the file changes, and nothing updates the copy.
- Match the length of a document to the task. Cover the substance. Do not pad
  with a filler section, a redundant summary, or boilerplate. A document that
  answers the question beats a document that surveys the topic.
- Prefer a vertical list to a paragraph (Rule 4.3).

## Markdown and GitHub text

- Write "about", not `~`, for an approximate number. GitHub Markdown reads a
  single `~` as a strikethrough mark when punctuation sits on both sides of it.
  So `(~$7/mo) and (~$36/mo)` renders the text between the two marks struck
  through. Formatters such as dprint then rewrite the pair to `~~`.
- In a Markdown file, escape an issue reference as `\#274` only when the `#` is
  the first character on its line. At line start, markdownlint rule MD018 reads
  `#274` as a heading with no space, and `--fix` adds the space, which makes a
  real heading. Everywhere else, write a bare
  `#274`. A backslash in a code comment is literal text, and in a GitHub body
  it stops the auto-link.
- Write each paragraph of a GitHub body as one line. This covers a PR
  description, a review, a comment, and an issue. GitHub wraps the text, so a
  hard break gives ragged lines. Files in a repository keep the wrap that their
  formatter sets.
