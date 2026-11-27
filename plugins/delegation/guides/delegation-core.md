# Delegation guide: core

These rules apply when you give work to a subagent. A fork is a subagent that
inherits this conversation. A fresh subagent knows only its brief.

## The rules

1. Choose a fork or a fresh subagent by the judgment that the work needs, not
   by its size. If the worker must make decisions that depend on what this
   conversation settled, give the work to a fork. A plan is that kind of work
   even when it touches few files, because a plan is mostly decisions, and the
   decisions are not in the code. To compare competing plans, give each plan
   to a fresh `Plan` agent, so each plan starts independently. Follow rule 3
   for each brief, so the brief states the decisions that the session settled.
2. If rule 1 does not call for a fork, give small, mechanical work with a
   clear result to a fresh subagent. A fresh context costs less, and the worker
   reads no unrelated history.
3. Do not trust a brief because it looks complete. Your own context fills its
   gaps, so you cannot see them by a read. Before you send a brief, list what
   the worker must know, and check that the brief states each item. A fact in
   a file or in git is in a place the worker can look, so a brief can send a
   worker with tools there. A fact that exists only in this conversation has
   no such place. Write that fact in the brief. Do not tell the worker to find
   it, as in "use the error we saw earlier".
4. Keep the coordinator role in the main session. The plan as a whole lives in
   this conversation, so a fresh subagent that coordinates starts without it.
5. Give an independent review to a fresh subagent, because a fork inherits your
   reasoning. Send it the code and the claim to test, without the reasoning
   that led you to the claim.
6. If a source is small, read it yourself. A subagent pays off when the source
   is large, or when you need only a short result from it, because the
   subagent keeps the full source out of each later turn.
