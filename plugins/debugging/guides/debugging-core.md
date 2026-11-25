# Debugging guide: core

These rules apply when you investigate a failure, a wrong result, or a data
mismatch. Where they differ from superpowers `systematic-debugging`, these
rules win. Phase 2 of that skill compares working code with broken code, but
these rules compare a working run with a broken run first. Phase 3 forms a new
hypothesis after a failed test, but these rules split, merge, or combine the
existing hypotheses first, as rule 6 says.

If an error names its cause and the first fix works, skip the table. The other
rules still apply.

## The rules

1. Gather runtime facts before you read code to form a hypothesis. Code shows
   what can happen, but a log, a query result, or a trace shows what did
   happen. If a fact is out of reach, ask the user for it by name. Do not guess
   its value.
2. Compare the broken case with a control. A control is a working case, or a
   case that fails in a different, louder way. A fact in the broken case and
   not in the control is a signal. A fact in both cases is noise, and noise can
   remove a hypothesis but never points at one. If no control exists, say so,
   and go on with the facts alone.
3. When the first hypothesis fails, or when two or more hypotheses are live,
   write a table in the reply. Each row is a hypothesis, and each column is a
   fact. Put `Hypothesis` in the first header cell. Each cell says whether the
   fact fits the hypothesis: ✓ if it fits, ✗ if it contradicts, and blank if
   nobody knows yet. One ✗ removes a hypothesis.
4. For each removed hypothesis, name a fact that would restore it if someone
   found it.
5. Rate a signal by the number of ✓ cells in its column. A signal that fits one
   hypothesis is strong, and a signal that fits all of them steers nothing.
6. When no row is all ✓, repair the set in this order:
   1. Check each contradicting fact for a gathering error, such as a wrong host
      or a log that lags. Gather it again, or ask the person who gathered it.
   2. Split a hypothesis that bundles two ideas. Merge narrow hypotheses into
      the one thing they share. Combine two hypotheses that each explain facts
      the other cannot.
   3. Write a new hypothesis from the facts you hold.
   4. Gather facts from one layer further down, such as from logs to packets
      to process state. Stop at the first strong signal.
7. Before you trust a new query or measurement, run it on one known-positive
   case and one known-negative case. A check that gives the same result for
   both cannot tell them apart.
8. Accept a reproduction only when it shows the strongest signal of the real
   reports. A matching symptom is not enough, because a different cause can
   produce it.
9. When you start a reviewer, tell it to find one fact that contradicts the
   hypothesis under review. A reviewer cannot see a fact that nobody gathered,
   so the agreement of a reviewer proves nothing.
10. Put the full path of this file in each brief for a subagent that
    investigates. A subagent knows only what its brief says.
11. End with a report that names the root cause and the facts that support it.
    When more than one fix exists, list each fix with its trade-off.

Read `debugging.md` next to this file for the reasons and the examples.
