# Debugging guide

This guide gives the reason for each rule in
[debugging-core.md](debugging-core.md), in the same order, with an example
where the article gives one. The method comes
from Cindy Sridharan,
[How to effectively debug when you no longer understand the code](https://copyconstruct.medium.com/how-to-effectively-debug-when-you-no-longer-understand-the-code-bd3dcb2c5f7b),
October 2026. Each example retells one of her cases in new words.

The method treats each gathered fact as a constraint. A hypothesis survives
only if it fits every constraint, so the work is to gather enough facts that
one hypothesis is left.

## 1. Facts before code

Code shows each path that a run can take. A log, a query result, a trace, or a
heap profile shows the path that one run took. A hypothesis that starts from
code starts from a wide set of possibilities. You also pick the part of the
code that you read, so a plausible story comes easily and proves little.

Gather the facts that are cheap first: the bug report, the logs, the
telemetry, the configuration, and the version history. Then form a hypothesis
that explains them, and read the code to test it.

If a fact is out of reach, because access is denied or the data is gone, ask
the user for that one named fact. Do not guess its value. A guessed fact looks
the same in the table as a gathered fact, so it hides the gap.

Example: a memory leak came with a bug report that had the first bad version,
the last good version, steps to reproduce, and a heap profile. The agent read
the code and blamed retries in a state machine. The state machine cannot reach
the state that the agent named. The leak was also new in a recent version. So
two facts in the report ruled the story out before any code was read.

## 2. Compare with a control

A broken case holds many facts, and most of them are also true of a working
case. Without a control, nothing marks which facts matter. A fact that is in
the broken case and not in the control is a signal. A fact that is in both is
noise. Noise is still useful, because a hypothesis that rests on it is wrong,
but noise never shows where to look.

The best control differs from the broken case in one thing, such as the same
code with a feature flag off. For a hard bug, a working case can differ in too
many ways. Then pick a broken case whose cause you already know, and whose
failure leaves a clear error. That kind of control is often already in the data you hold.
Look for an older report with a known cause, a failure with a clear error, or
a run from before the change.

A control that shares the fault hides every signal, so check that its cause
is known and different. If no control exists, say so in the reply, and go on with the facts
alone. The table then has more live rows, so expect to gather more facts.

Example: a client regression showed a higher tail latency on the server. The
control ran the same client with the new feature flag off. Connection setup
times were the same in both runs, so they were noise. One lookup returned about
5 addresses in the control and about 400 in the broken run, and that signal led
to the fix.

## 3. The table

The table makes the state of the investigation visible to the user and to
you. It also stops a habit of an agent: when one hypothesis fails, the agent
proposes a new one and forgets which facts removed the first one.

When the first hypothesis fails, or when two or more hypotheses are live,
write the table. An obvious bug does not need one. Read the table by row to
find a hypothesis that fits every fact. Read it by column to rate a signal, as
in rule 5.

This table is the end state of the memory leak in section 6. The leak was new
in a recent version, an opt-in optimization was off for the user, and the heap
profile pointed at a plain recursive call.

| Hypothesis                       | New in recent version | Optimization was off | Profile frame |
| -------------------------------- | --------------------- | -------------------- | ------------- |
| Unbounded retries                | ✗                     | ✓                    |               |
| The opt-in optimization          | ✓                     | ✗                    | ✗             |
| New cache and one-use state code | ✓                     | ✓                    | ✓             |

## 4. A fact to bring back a removed hypothesis

A removed hypothesis rests on the facts as they stand. If one of those facts
was gathered wrong, the right answer is among the removed rows. When each
removed row names a fact that can restore it, a later correction shows at
once which row comes back.

Example: "Unbounded retries" is out because the retry code is old and the leak
is new. A report of the same leak on an old version would bring it back.

## 5. Rate each signal

A signal that most hypotheses fit does not choose between them. A signal that
one hypothesis fits points at the answer. Count the ✓ cells in each column. A
blank cell does not count.
Spend the next step on the hypothesis that the strongest signal supports.

A service-level number, such as an error rate or a tail latency, is often a
weak signal. It is the symptom, so nearly every cause fits it.

Example: in the latency case, the server tail latency fit seven hypotheses,
which made an early guess about certificate loading sound right. The address
count fit one hypothesis, client routing.

## 6. When no row fits

If no row is all ✓, the set of hypotheses is wrong, or a fact is wrong. Repair
them in this order, from the cheapest step to the most expensive:

1. Check how each contradicting fact was gathered. A query against the wrong
   host, a log that lags, a wrong time window, or a tool that returns an empty
   result with no error can each make the right hypothesis look wrong. If you
   gathered the fact, gather it again with the error fixed. If someone else
   gathered it, ask them to check it, because you cannot change their data.
2. Split a hypothesis that bundles two ideas. A fact that removes one part does
   not remove the other.
3. Merge narrow hypotheses that each explain one host or one symptom into one
   that names what they share.
4. Combine two hypotheses when each explains facts that the other cannot, and
   neither has a ✗. Each part must be necessary: remove one, and a fact is left
   unexplained.
5. Write a new hypothesis from the facts you hold.
6. If that fails too, gather facts from one layer further down, such as from
   logs to packets, to process state, or to kernel tables. Stop at the first
   strong signal. A lower layer costs more to read, and it adds nothing once a
   signal fits one hypothesis.

Example: in the memory leak, "the recent feature work caused it" bundled a
cache that was on by default with an optimization that was off by default. A
split kept the cache. The cache explained why the leak was new, but not the
frame in the heap profile. A second, older part explained the frame: the state
code was built for one use, and it added a stack frame each time the cache sent
it back in. That part alone did not explain why the leak was new. Combined, the
two fit every fact.

## 7. Test a new query on known cases

A new query can be wrong in a way that looks like a result. A filter on the
wrong field returns nothing, and nothing reads as "this case is clean". Run the
query on one case that must match and one case that must not. If both give the
same result, the query cannot tell the cases apart, so fix it before you use
it.

## 8. A reproduction must show the reported signal

A system holds many faults at once, and a reproduction can find one that is
not the reported fault. A matching symptom does not prove the match, because a
different cause can produce the same symptom. Pick the strongest signal from
the real reports, and check that the reproduction shows it too. A reproduction
that does not show it is noise for this investigation.

Example: a desktop daemon hung after a successful connection. A test harness
with clock skew between client and server reproduced the hang. In the real reports, the packet sequence
was always the same, and a kernel table held an unanswered reply for the
daemon's request. The reproduction had a different packet sequence and no
unanswered reply, so it was a different bug.

## 9. Brief a reviewer to contradict

A reviewer can check whether a hypothesis fits the facts in the table. It
cannot know about a fact that nobody gathered. A reviewer with the same model
and the same context often agrees with the first agent, so two agreements can
be one opinion.
A reviewer that searches for a contradiction removes a wrong hypothesis, and
one contradiction is enough.

When you start a reviewer, give it this task: "Find one fact that contradicts
this hypothesis. Check that each fact the hypothesis rests on is absent from
the control. Check that the control does not share the fault. Check how each
fact was gathered." When you
start `reviews:gemini-review` or `codex-review` on a debugging claim, add the
same task to its prompt.

Example: in the latency case, the first theory said that the server loaded its
certificate on every call. A subagent checked the theory and agreed with it.
Later, a trace showed one certificate load per session and removed the
theory. Nobody had gathered that trace when the subagent checked.

## 10. Brief a debugging subagent

A subagent does not see this conversation, so it knows only what its brief
says. Put the full path of `debugging-core.md` in its brief, and tell
it to read that file first. Give it the facts you hold and the table, so it
does not start again from the code.

## 11. The report

The report names the root cause and the facts that support it, so the user can
check the claim without a second investigation. If more than one fix exists,
list each fix with its trade-off. The choice depends on cost and risk, and the
user can judge those better.

Example: in the latency case, the cause was one new code path that used a
client with no shard routing. That client looked up every server, not the
servers of one shard, so the lookup returned about 400 addresses. Each request
went to a random server, which then forwarded it. The fix was one line, to use
the routing client.
