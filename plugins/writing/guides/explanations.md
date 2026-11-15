# Explanation guide

This guide covers the explanation register: the prose that says what a system does and why.

`explanations-core.md` holds each rule with one good passage. This file adds more good passages,
and for each rule before-and-after pairs: a real failure and its rewrite.

Each example has an ID, such as `R2-P1`, and an origin. "Rewritten from corpus" marks a passage
from a private repository, with each name and each domain changed. A public quote is verbatim, and
an ellipsis marks each cut. Because it is verbatim, a public quote can use a word that the checks
flag. The table at the end of this file gives the source and the license of each
public quote.

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

### Core example

**R1-C.** Rewritten from corpus.

> Each question also asks whether the rule changes an outcome. A person can
> skip a rule that looks unimportant, but the model applies every rule, so even
> a small rule can change a result.

Why it works: "but" marks the contrast between the person and the model, and
"so" gives the result: even a small rule can change a result.

### More good passages

**R1-P1.** SQLite documentation, <https://www.sqlite.org/wal.html>, public
domain.

> Because writers do nothing that would interfere with the actions of readers,
> writers and readers can run at the same time. However, since there is only
> one WAL file, there can only be one writer at a time.

Why it works: the first sentence gives a cause, and "however" tells the reader
that the second sentence limits the first. The reader does not conclude that
any number of writers can run.

**R1-P2.** SQLite documentation, <https://www.sqlite.org/wal.html>, public
domain. Cut inside.

> WAL does not work over a network filesystem. This is because WAL requires all
> processes to share a small amount of memory and processes on separate host
> machines ... cannot share memory with each other.

Why it works: the limit comes first, and "This is because" tells the reader that
the rest of the passage is the reason. A reader who knows the reason can tell
which other setups fail for the same cause.

**R1-P3.** Rewritten from corpus.

> The host can stop the worker one second after the handler returns. The batch
> log exporter then drops the records that it still holds. One nightly run lost
> its report trace this way, and the alerts depend on that trace.

Why it works: "then" gives the time order. The host stops the worker, and after
that the exporter drops the records. The last clause says why the loss matters.

### Before and after

**R1-B1.** Rewritten from corpus. This is a commit message line.

Before:

> The Brewfile adds jq. The hook, the release script and the dev container use
> it.

After:

> Add jq to the Brewfile, because the hook, the release script and the dev
> container need it.

Why it works: in the "before", the second sentence can read as an unrelated
note. "Because" makes it the reason for the change.

**R1-B2.** Rewritten from corpus.

Before:

> Navigation reads the live tree through `list_entries`, which the scoped
> permission does support. It is also the more authoritative answer. This
> function creates the customer and order folders, so it owns the structure. It
> waits on no search-index latency.

After:

> Navigation reads the live folder tree through `list_entries`, which the
> scoped permission supports. Navigation is also more reliable than search,
> because the sync function creates the folders itself. The live tree is always
> current, but the search index can lag behind the tree.

Why it works: the "before" gives four facts and leaves the reader to find the
comparison. The "after" names the comparison ("more reliable than search") and
joins each reason to it.

## R2. Mark a case that is not real

A passage can describe a case that is not real, such as a rejected design or a
default that does not exist. Write that case with `if` and `would`, as in
`if X were the case, Y would happen`. In the present tense, the reader takes the
case as a fact about the system.

### Core example

**R2-C.** Rewritten from corpus.

> The connection helpers refuse an unset `DATABASE_URL`, and they have no
> default on purpose. A default would carry a host and a credential, so a
> deployment that forgot the variable would connect to a sandbox database
> instead of failing.

Why it works: "would" tells the reader that the default is imaginary. The
reader learns why the code has no default, and does not go looking for one.

### More good passages

**R2-P1.** The Rust Programming Language, chapter 8.1,
<https://doc.rust-lang.org/book/ch08-01-vectors.html>, MIT or Apache-2.0.

> We must also be explicit about what types are allowed in this vector. If Rust
> allowed a vector to hold any type, there would be a chance that one or more of
> the types would cause errors with the operations performed on the elements of
> the vector.

Why it works: "If Rust allowed" opens a case that Rust rejects, and "would"
holds through the whole sentence. The reader learns the reason for the rule
without thinking that Rust allows it.

**R2-P2.** Go FAQ, <https://go.dev/doc/faq>, CC BY 4.0.

> It is practical to create hundreds of thousands of goroutines in the same
> address space. If goroutines were just threads, system resources would run
> out at a much smaller number.

Why it works: "were" and "would" mark the comparison case. The reader knows
that goroutines are not threads, and learns what that difference buys.

**R2-P3.** Rewritten from corpus.

> The LLM client is built per Celery task inside the task's `asyncio.run`
> scope, and it is closed in the same `finally` block as the database engine.
> Its semaphore and HTTP client bind to the event loop that created them, so a
> client that lived as long as the worker would fail only under load, on a
> later job.

Why it works: the passage says what the code does, then what a different design
would do, and "would" keeps the two apart. "Only under load, on a later job"
tells the reader why tests do not catch the fault.

### Before and after

**R2-B1.** Rewritten from corpus.

Before:

> The connection helpers all refuse an unset value. A default carries a host
> and a credential. A deployment that forgets the variable then connects to a
> sandbox instead of failing.

After: see R2-C.

Why it works: the "before" says in the present tense that a default carries a
credential and that a deployment connects to a sandbox. Neither is true,
because no default exists. "Would" makes both sentences true.

**R2-B2.** Rewritten from corpus. The original checked a contract expiry. This
version checks a subscription expiry, with the same logic.

Before:

> The months left on a subscription that expired before the report date. A
> whole-month count gives 0 for a gap of under one month. A 0 reads as a live
> subscription.

After:

> `EXPIRED` marks a subscription that expired before the report date. The
> function returns `EXPIRED` instead of a month count, because a subscription that
> expired less than a month earlier would count as 0 months, and 0 would look
> like a live subscription.

Why it works: the "before" reads as a description of a bug in the current
code. The "after" says what the code does, and then uses "would" for the month
count that the code avoids.

## R3. State the scope of each claim

Words such as "even if", "only when", "at least", and "never" set the limits of
a claim. Write them in, even when the sentence gets longer. Without them, a
claim can mean its opposite.

### Core example

**R3-C.** Rewritten from corpus.

> Each formatter runs even if an earlier one fails, so a ruff error does not
> hide the eslint errors.

Why it works: "even if" says that a failure does not stop the next formatter.
A version that drops "even", such as "runs after an earlier one fails", says
the reverse.

### More good passages

**R3-P1.** Python documentation, tutorial section 4.9.1,
<https://docs.python.org/3/tutorial/controlflow.html>, PSF License Version 2.

> Important warning: The default value is evaluated only once. This makes a
> difference when the default is a mutable object such as a list, dictionary,
> or instances of most classes.

Why it works: "only once" is the whole fact, and "when" says which defaults the
reader must worry about. Without "when", the reader can think every default is
a risk.

**R3-P2.** Rewritten from corpus.

> Each call uses temperature 0 when the model accepts that setting. For a model
> that does not accept it, the call leaves temperature unset, because the API
> would reject a request that set it.

Why it works: "when the model accepts" limits the first claim, and the second
sentence covers the other case. The reader knows that some calls run at the
model's default temperature, and why.

**R3-P3.** SQLite documentation, section 2.3,
<https://www.sqlite.org/lang_transaction.html>, public domain.

> The explicit COMMIT command runs immediately, even if there are pending
> SELECT statements. However, if there are pending write operations, the COMMIT
> command will fail with an error code SQLITE_BUSY.

Why it works: "even if" says that pending reads do not block a commit, and
"However, if" names the one case that does. Without "even if", the first
sentence says the reverse.

**R3-P4.** SQLite documentation, <https://www.sqlite.org/isolation.html>,
public domain.

> The combined use of shared cache mode and the read_uncommitted pragma is the
> only way that one database connection can see uncommitted changes on a
> different database connection. In all other circumstances, separate database
> connections are completely isolated from one another.

Why it works: "the only way" and "In all other circumstances" set the limit
from both sides. The reader knows the one case where a connection sees
uncommitted data, and that no other case exists.

### Before and after

**R3-B1.** Rewritten from corpus.

Before:

> Each formatter runs after an earlier one fails.

After: see R3-C.

Why it works: the "before" lost "even if", so it reads as "a formatter runs
after a failure". That is the reverse of the code, which runs each formatter
whether an earlier one fails or not.

**R3-B2.** Rewritten from corpus. The class names are invented.

Before:

> Now `AnsweredError` requires usage. `EmptyReplyError` and
> `TruncatedReplyError` subclass it. Only `CallError` carries usage.

After:

> `usage` now lives only on `CallError` and its subclasses, not on every
> `ClientError`. It is optional on `CallError`, and `AnsweredError` makes it
> required.

Why it works: in the "before", "only `CallError`" seems to contradict the first
sentence. The reader needs "and its subclasses" to see that `AnsweredError` is
one of them.

## R4. Give the advice and its reason

When the text implies an action, state the action and the condition that calls
for it. A bare fact leaves the reader to work out what to do, and a reader in a
hurry does not.

### Core example

**R4-C.** Rewritten from corpus.

> The read blocks, so an async caller must run it in a thread.

Why it works: "must" tells an async caller what to do. "An async
caller runs it in a thread" would read as a description of code that already
exists.

### More good passages

**R4-P1.** Rewritten from corpus.

> Re-read the description first. Someone can edit it while this runs, and a PUT
> of the stale copy would revert their edit.

Why it works: the action comes first, and the reason follows with a real
consequence. The reader knows what breaks if the step is skipped.

**R4-P2.** Rewritten from corpus.

> Use `-sfn`, not `-s`. The link already exists. Plain `-s` then makes a new
> link inside the existing target directory, reports success, and fixes nothing.

Why it works: the command comes first, then the cause, then the failure the
reader would see.

**R4-P3.** Rewritten from corpus.

> If a value with no quote is still common after this change, a retry that asks
> the model for the missing quote is the next fix.

Why it works: the condition comes first, and the next action follows. A later
reader knows what to measure and what to try.

### Before and after

**R4-B1.** Rewritten from corpus. The original was a legend for a script that
compares model runs.

Before:

> `wall (s)`: It spans every attempt of a call, so an escalated call or a wait
> for a permit can put it above `slowest (s)`.

After:

> `wall (s)`: It spans every attempt of a call, so an escalated call or a wait
> for a concurrency permit can put it above `slowest (s)`. If it is well above
> `slowest (s)` and no call escalated, calls waited for a permit, so a higher
> concurrency limit would bring the stage closer to `slowest (s)`.

Why it works: the "before" explains the number and leaves out what to do about
it. The "after" keeps both causes, says which one calls for the action, and
gives the action. "Would" marks the higher limit as a change the reader can
make, not the current value.

**R4-B2.** Rewritten from corpus.

Before:

> Nx names that database file for the machine id. A fix depends on that
> internal name, and it saves at most about 1 minute of a PR run.

After:

> Nx names that database file after the machine ID. A fix would depend on that
> internal name and save at most about one minute per PR run, so it is not
> worth making.

Why it works: the "before" gives the cost and the benefit and leaves out the
verdict. It also says in the present tense that a fix depends on the name, as
if the fix exists. The "after" states the decision.

## R5. Use a verb in its common meaning, and define a house term

Use each verb in the sense that a dictionary gives first. If a house term is
necessary, define it where it first appears. A private sense forces the reader
to decode the sentence, and a reader who decodes it wrong does not know that
the decoding went wrong.

### Core example

**R5-C.** The Rust Programming Language, chapter 4.1,
<https://doc.rust-lang.org/book/ch04-01-what-is-ownership.html>, MIT or
Apache-2.0. Cut at both ends.

> ... When s2 and s1 go out of scope, they will both try to free the same memory.
> This is known as a double free error ...

Why it works: the term arrives after the reader understands the thing it names.
The reader learns the term and the fault in one step.

### More good passages

**R5-P1.** SQLite documentation, <https://www.sqlite.org/wal.html>, public
domain.

> When a read operation begins on a WAL-mode database, it first remembers the
> location of the last valid commit record in the WAL. Call this point the "end
> mark".

Why it works: the page uses "end mark" many times below. It defines the term
once, in plain words, before the first use.

**R5-P2.** Rewritten from corpus.

> A new correction action, `clear`, records that a file has no value for a
> field.

Why it works: "correction action" tells the reader what kind of thing `clear`
is before they meet the name. Without that phrase, "the new action clear"
reads as a verb, and the reader parses the sentence twice.

**R5-P3.** Rewritten from corpus.

> If a work item only points at a PR without citing a ticket clearly (a weak
> citation), triage adds no comment.

Why it works: the house term "weak citation" appears in parentheses after its
meaning. A reader who meets it later in the file knows what it means.

### Before and after

**R5-B1.** Rewritten from corpus.

Before:

> A fault blocks the write. A finding needs a confirmation.

After:

> A hard error blocks the write. A warning lets the write through after the
> user confirms it.

Why it works: "fault" and "finding" were private names for two levels of
check. The reader of the "before" cannot tell which is worse. "Error" and
"warning" carry that order in their common meaning.

**R5-B2.** Rewritten from corpus. The original described a report that
compares model costs.

Before:

> `_floor` takes a partial flag. The total cell floors on an unrecorded answer.
> The retry cell floors only on its own attempts.

After:

> If any answer has no recorded token usage, the total-cost cell shows `>=`,
> because the real cost is at least that much. The retry cell shows `>=` only
> when one of its own attempts lacks usage data.

Why it works: "floors" was a private verb for "shows a lower bound". The
"after" says what the reader sees in the cell, when, and why.

## R6. Start with what the reader knows

Open a sentence with something the reader already met, often the subject of the
sentence before. End it with the new fact. A sentence that starts with a new
thing makes the reader hold it until they learn why it matters.

### Core example

**R6-C.** Rewritten from corpus.

> The tag `api-1.1.0` points at the same commit as `webapp-1.1.0`. Without the
> API tag, `nx release` finds no previous release for the API project and
> refuses to run.

Why it works: the second sentence opens with "the API tag", the subject of the
sentence before. The name also keeps the reader from attaching it to the
webapp tag. The new fact, that the release tool refuses to run, comes
last.

### More good passages

**R6-P1.** Rewritten from corpus.

> A 3000x40 banner passed the 30-pixel minimum-height filter. The resize step
> then shrank it to 1568x21, and the request sent that thin strip. A strip still
> costs an image part and a slot in the model's image limit. The resize now runs
> first, so the filter and the encoder see the same image.

Why it works: the passage is a chain. Each sentence picks up the last thing the
one before said: the banner, then the strip, then its cost. The numbers carry
the logic: 40 pixels passes a 30-pixel minimum, and 21 does not.

**R6-P2.** Rewritten from corpus.

> Every fault below was silent. The extractor raised no error, and it built a
> plausible result from a wrong read.

Why it works: the first sentence gives the reader the frame for the list below
it. The reader reads each item as a silent fault, and does not wait for an
error message that never comes.

**R6-P3.** The Rust Programming Language, chapter 4.1,
<https://doc.rust-lang.org/book/ch04-01-what-is-ownership.html>, MIT or
Apache-2.0.

> When a variable goes out of scope, Rust calls a special function for us. This
> function is called drop, and it’s where the author of String can put the code
> to return the memory.

Why it works: the first sentence ends on "a special function", and the second
opens with "This function". The new facts, the name and the job, come last.

**R6-P4.** SQLite documentation, section 5.1,
<https://www.sqlite.org/lockingv3.html>, public domain.

> SQLite version 3 seeks to avoid writer starvation through the use of the
> PENDING lock. The PENDING lock allows existing readers to continue but
> prevents new readers from connecting to the database. So when a process wants
> to write a busy database, it can set a PENDING lock which will prevent new
> readers from coming in.

Why it works: the first sentence ends on "the PENDING lock", and the second
opens with it. The third sentence uses what the second taught, and ends on how
a writer gets its turn.

### Before and after

**R6-B1.** Rewritten from corpus. `declaration-strict-value` is a public
stylelint plugin rule.

Before:

> `declaration-strict-value` now covers `font-family` and `line-height`. A line
> height can also be 1.

After:

> `declaration-strict-value` now covers `font-family` and `line-height`. For
> `line-height`, the rule also allows the literal value `1`.

Why it works: "A line height can also be 1" reads as a fact about CSS. The
"after" opens with the property the reader just met, and the new fact is about
the rule.

## R7. Point each pronoun at one noun

Each "it", "this", "that", and "which" must point at one noun that the reader
just read. If no noun fits, or if two nouns fit, write the noun: "that filter",
not "that". A model takes the nearest noun that fits, and a person stops to
search.

### Core example

**R7-C.** Rewritten from corpus.

> The warehouse setting can be empty. An empty setting gives a writer that does
> nothing, and that empty writer lets the app deploy before the warehouse
> exists.

Why it works: "that empty writer" names its noun. A bare "that" could point at
the setting, the writer, or the whole sentence.

### More good passages

**R7-P1.** Rewritten from corpus.

> The team reports each order under its billing state, but the store address
> wins any conflict. The `orders` table holds only the billing state, so that
> override was out of reach from the table alone.

Why it works: "that override" points back at the rule that the store address
wins. The reader does not have to choose between the state, the address, and
the conflict.

**R7-P2.** SQLite documentation, section 5.1,
<https://www.sqlite.org/lockingv3.html>, public domain.

> In SQLite version 2, if many processes are reading from the database, it
> might be the case that there is never a time when there are no active
> readers. And if there is always at least one read lock on the database, no
> process would ever be able to make changes to the database because it would
> be impossible to acquire a write lock. This situation is called writer
> starvation.

Why it works: "This situation" names what it points at. A bare "this" could
attach to the last noun, "a write lock". The middle sentence is 35 words,
and it reads easily because it is one line of reasoning.

**R7-P3.** SQLite documentation, section 7,
<https://www.sqlite.org/wal.html>, public domain.

> If another connection has a read transaction open, then the checkpoint cannot
> reset the WAL file because doing so might delete content out from under the
> reader. The checkpoint will do as much work as it can without upsetting the
> reader, but it cannot run to completion.

Why it works: the second sentence opens with "The checkpoint" again. A bare
"it" there could mean the checkpoint or the other connection.

R6-C ("that tag") and R6-P1 ("that thin strip") also follow this rule.

### Before and after

**R7-B1.** Rewritten from corpus.

Before:

> That filter hides every Blocked item. So the next sentence in each file was
> false. It said a person finds those items among the other Inbox items.

After:

> Each file told a person to filter the list on Inbox alone. That filter hides
> every Blocked item, because Blocked is a separate status. But the next
> sentence in each file said a person finds Blocked items among the Inbox
> items, so that sentence was false.

Why it works: in the "before", "that filter" points at nothing the reader read.
The "after" first says which filter, and each "that" then points at the
sentence just before it.

**R7-B2.** Rewritten from corpus.

Before:

> The gap analysis rated the Summary page a quarter buildable, which the new
> order data superseded; it now rebuilds in full.

After:

> The gap analysis rated the Summary page only a quarter buildable. The new
> order data replaces that rating, and the Summary page now rebuilds in full.

Why it works: in the "before", "which" can point at the page or the rating, and
"it" can point at the page or the analysis. The "after" names each noun.

**R7-B3.** Rewritten from corpus.

Before:

> The keyword is only emitted when `user_id` is set, and that comes from
> `CLIENT_ID`, set on the server and unset on a laptop. Every manual run took
> the branch that never emitted it, so this could only fail in production.

After:

> The builder emits the keyword only when `user_id` is set. `user_id` comes
> from `CLIENT_ID`, which the server sets and a laptop does not. So every
> manual run skipped the keyword, and the bad keyword could fail only in
> production.

Why it works: the "before" has three pronouns with no clear noun: "that",
"it", and "this". The "after" names each one. It also moves "only" next to the
words it limits.

## R8. Let a sentence run as long as one line of reasoning

A sentence can run past 25 words when each clause depends on the clause before
it. After you write a long sentence, read it again. If it carries one line of
reasoning, keep it whole. If it holds separate facts, give each fact its own
sentence.

### Core example

**R8-C.** Rewritten from corpus.

> The `order_lines` table has one row per line, and an order can have several
> lines, so an ungrouped join would fan the view out and inflate every
> downstream `SUM`.

Why it works: the sentence is about 30 words, and it is one chain: a fact, a
second fact, and the result of the two. A split would put the "so" in a second
sentence, and the reader would have to carry both facts across the break.

### More good passages

**R8-P1.** PostgreSQL documentation, section 13.1,
<https://www.postgresql.org/docs/current/mvcc-intro.html>, PostgreSQL License.

> The main advantage of using the MVCC model of concurrency control rather than
> locking is that in MVCC locks acquired for querying (reading) data do not
> conflict with locks acquired for writing data, and so reading never blocks
> writing and writing never blocks reading.

Why it works: the sentence is over 40 words, and it builds to one claim. The
end is short and plain, so the reader leaves with the point: reading and
writing do not block each other.

**R8-P2.** Go FAQ, <https://go.dev/doc/faq>, CC BY 4.0.

> After long discussion it was decided that the typical use of maps did not
> require safe access from multiple goroutines, and in those cases where it
> did, the map was probably part of some larger data structure or computation
> that was already synchronized. Therefore requiring that all map operations
> grab a mutex would slow down most programs and add safety to few.

Why it works: the first sentence is long because it gives the common case and
the exception together. The second is short, and it gives the verdict.
"Therefore" links them, and "would" marks the rejected design.

**R8-P3.** Rewritten from corpus.

> Git scores any two empty files as a 100% content match, so `git log --follow`
> chains these markers back through unrelated empty files, as far as a
> zero-byte README from the first skeleton commit.

Why it works: one cause, one result, and one concrete case that shows how far
the result goes. Each clause depends on the clause before it.

### Before and after

**R8-B1.** Rewritten from corpus.

Before:

> The vendor export has always carried it as "Date of Issue" and the import
> script has always extracted it; the warehouse mapping dropped it and the
> `policy` table had no column, so the only date available for reporting was
> the wrong one.

After:

> The vendor export carries the issue date, and the import script extracts the
> date. But the warehouse mapping dropped the date, and the `policy` table had
> no issue-date column. So the only date available for reporting was the wrong
> one.

Why it works: the "before" holds several facts, and the semicolon hides the turn
from "the data was there" to "the data was lost". The "after" puts that turn in
a "but" and the result in a "so". It also names the date each time,
where the "before" called it "it" three times.

**R8-B2.** Rewritten from corpus. This one goes the other way: two short
sentences become one longer one.

Before:

> The downgrade gives each list a new UUID. No code reads a list's identity
> across two rebuilds.

After:

> The downgrade gives each list a new UUID, and the new UUID is safe because no
> code relies on a list keeping its identity across rebuilds.

Why it works: the "before" leaves the reader to guess why the second sentence
is there. The longer "after" says that it answers a worry: a new UUID is safe.

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

## Sources quoted

| Project | Page | License | Copyright |
| --- | --- | --- | --- |
| The Rust Programming Language | <https://doc.rust-lang.org/book/> | MIT or Apache-2.0 | 2010 The Rust Project Developers |
| PostgreSQL documentation | <https://www.postgresql.org/docs/current/mvcc-intro.html> | PostgreSQL License | 1996-2026 The PostgreSQL Global Development Group |
| Python documentation | <https://docs.python.org/3/tutorial/controlflow.html> | PSF License Version 2 | 2001 Python Software Foundation |
| SQLite documentation | <https://www.sqlite.org/wal.html>, <https://www.sqlite.org/lang_transaction.html>, <https://www.sqlite.org/isolation.html>, <https://www.sqlite.org/lockingv3.html> | Public domain, per <https://www.sqlite.org/copyright.html> | none claimed |
| Go FAQ | <https://go.dev/doc/faq> | CC BY 4.0, per <https://go.dev/copyright> | not named on that page. Attribute to the Go project. |

The MIT, PostgreSQL, and PSF licenses ask that the copyright notice stay with
the copied text. This table keeps that notice in the same file as the quotes.
CC BY 4.0 asks for attribution and a note of changes. The quotes in this file
have no changes other than marked cuts.
