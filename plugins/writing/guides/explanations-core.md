# Explanation guide: core

This guide covers the explanation register: the prose that says what a system does and why.

## The goal

Write so that the reader gets the point on the first read and can act on it.
The reader can be a person or a model. A person skims, and stops reading text
that sounds generic. A model reads every word, and takes each sentence as a
true statement about the system. Both readers need the same three things: the
facts, how the facts relate, and what to do about them.

## R1. Name the relation

Join related facts with the word that names how they relate: because, so, but,
although, unless, if. Without that word, the reader must guess whether the
second fact is a cause, a result, or an exception.

**R1-C.**

> Each question also asks whether the rule changes an outcome. A person can
> skip a rule that looks unimportant, but the model applies every rule, so even
> a small rule can change a result.

Why it works: "but" marks the contrast between the person and the model, and
"so" gives the result: even a small rule can change a result.

## R2. Mark a case that is not real

A passage can describe a case that is not real, such as a rejected design or a
default that does not exist. Write that case with `if` and `would`, as in
`if X were the case, Y would happen`. In the present tense, the reader takes the
case as a fact about the system.

**R2-C.**

> The connection helpers refuse an unset `DATABASE_URL`, and they have no
> default on purpose. A default would carry a host and a credential, so a
> deployment that forgot the variable would connect to a sandbox database
> instead of failing.

Why it works: "would" tells the reader that the default is imaginary. The
reader learns why the code has no default, and does not go looking for one.

## R3. State the scope of each claim

Words such as "even if", "only when", "at least", and "never" set the limits of
a claim. Write them in, even when the sentence gets longer. Without them, a
claim can mean its opposite.

**R3-C.**

> Each formatter runs even if an earlier one fails, so a ruff error does not
> hide the eslint errors.

Why it works: "even if" says that a failure does not stop the next formatter.
A version that drops "even", such as "runs after an earlier one fails", says
the reverse.

## R4. Give the advice and its reason

When the text implies an action, state the action and the condition that calls
for it. A bare fact leaves the reader to work out what to do, and a reader in a
hurry does not.

**R4-C.**

> The read blocks, so an async caller must run it in a thread.

Why it works: "must" tells an async caller what to do. "An async
caller runs it in a thread" would read as a description of code that already
exists.

## R5. Use a verb in its common meaning, and define a house term

Use each verb in the sense that a dictionary gives first. If a house term is
necessary, define it where it first appears. A private sense forces the reader
to decode the sentence, and a reader who decodes it wrong does not know that
the decoding went wrong.

**R5-C.** The Rust Programming Language, chapter 4.1,
<https://doc.rust-lang.org/book/ch04-01-what-is-ownership.html>, MIT or
Apache-2.0, copyright 2010 The Rust Project Developers. Cut at both ends.

> ... When s2 and s1 go out of scope, they will both try to free the same memory.
> This is known as a double free error ...

Why it works: the term arrives after the reader understands the thing it names.
The reader learns the term and the fault in one step.

## R6. Start with what the reader knows

Open a sentence with something the reader already met, often the subject of the
sentence before. End it with the new fact. A sentence that starts with a new
thing makes the reader hold it until they learn why it matters.

**R6-C.**

> The tag `api-1.1.0` points at the same commit as `webapp-1.1.0`. Without the
> API tag, `nx release` finds no previous release for the API project and
> refuses to run.

Why it works: the second sentence opens with "the API tag", the subject of the
sentence before. The name also keeps the reader from attaching it to the
webapp tag. The new fact, that the release tool refuses to run, comes
last.

## R7. Point each pronoun at one noun

Each "it", "this", "that", and "which" must point at one noun that the reader
just read. If no noun fits, or if two nouns fit, write the noun: "that filter",
not "that". A model takes the nearest noun that fits, and a person stops to
search.

**R7-C.**

> The warehouse setting can be empty. An empty setting gives a writer that does
> nothing, and that empty writer lets the app deploy before the warehouse
> exists.

Why it works: "that empty writer" names its noun. A bare "that" could point at
the setting, the writer, or the whole sentence.

## R8. Let a sentence run as long as one line of reasoning

A sentence can run past 25 words when each clause depends on the clause before
it. After you write a long sentence, read it again. If it carries one line of
reasoning, keep it whole. If it holds separate facts, give each fact its own
sentence.

**R8-C.**

> The `order_lines` table has one row per line, and an order can have several
> lines, so an ungrouped join would fan the view out and inflate every
> downstream `SUM`.

Why it works: the sentence is about 30 words, and it is one chain: a fact, a
second fact, and the result of the two. A split would put the "so" in a second
sentence, and the reader would have to carry both facts across the break.

## The checks

The prose gate and the lint hooks read each sentence as an instruction or an explanation. An
instruction starts with an imperative verb, or with a condition and then an imperative. A sentence
under a procedure heading, or in a warning, is an instruction too. An instruction keeps every
strict STE limit.

In an explanation, these checks are hard. Each one fails the prose gate run.

- `MODAL`: `should` or `may`. A requirement becomes `must`. A recommendation becomes an action and
  the condition that calls for it.
- `SEMICOLON`: write two sentences, or join the clauses with a word that names their relation.
- `CONTRACTION`, `PRESENT-PERFECT`, `ING-VERB` for a progressive verb or a trailing "-ing" clause,
  `AND-OR`, `LATIN`, and `SLOP`.
- The structural checks `TRIPLE`, `NOT-JUST`, `REVERSAL`, `FILLER`, and `ANNOUNCE`.

In an explanation, these checks are advisory. Each one asks a person to read the sentence again,
and none of them blocks.

- `MODAL-READ`: `would`, `could`, or `might`. `can` states what is possible. `would` and `could`
  state a case that is not real. `might` states an uncertain outcome.
- `LENGTH-READ`: a sentence over 25 words. If it carries one line of reasoning, keep it whole.
- `EM-DASH-READ`: an em dash.
- `ING-READ`: an "-ing" word that can be a modifier, as in "are working documents".
- `COUNT`, `PRIOR-STATE`, `HEDGE`, and `INTENSIFIER`.

Read the full guide, `explanations.md` next to this file, before a larger writing task. A larger
task is a PR description, an issue or a ticket, a README, a design document, or a plan.
