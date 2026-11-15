---
name: removing-llm-tropes
description: >-
  Use when writing or rewriting text for a reader outside the session: commit
  messages, PR titles and descriptions, documents, issues, tickets, and
  messages. Also use when the user asks to humanize text, remove AI slop, or
  unglaze writing. Writes the draft to the explanation guide of the writing
  plugin, then runs the upstream Writing Whip ban list and trope checklist as a
  separate post-generation audit and rewrite.
metadata:
  category: writing
  author: Ossama Chaib
  adapted-by: rednafi
  license: CC-BY-4.0
  source: https://github.com/rednafi/dotfiles/tree/3a7c084568006674f1f9ef1b228b37eec92d4e1f/dot_agents/skills/whip
  sources:
    whip: https://gist.github.com/ossa-ma/dae6f9571534f3fbd1266a384be00e11
    tropes: https://gist.github.com/ossa-ma/f3baa9d25154c33095e22272c631f5a1
    site: https://tropes.fyi
  upstream-version: 0.1.0
---

# Removing LLM Tropes

This skill adapts the Writing Whip and the trope list from
[tropes.fyi](https://tropes.fyi) by [ossama.is](https://ossama.is). Both are
under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). The upstream
text is in two gists:
[writing whip](https://gist.github.com/ossa-ma/dae6f9571534f3fbd1266a384be00e11)
and [tropes](https://gist.github.com/ossa-ma/f3baa9d25154c33095e22272c631f5a1).

This copy starts from the `whip` skill in
[rednafi/dotfiles](https://github.com/rednafi/dotfiles/tree/main/dot_agents/skills/whip).
The `metadata.source` link pins the copied commit. The upstream skill is for
blog articles. This copy has local edits for technical writing in a codebase.

## Scope

Apply this skill to text for a reader outside the session. The user's own
instructions and `${CLAUDE_PLUGIN_ROOT}/standards.md` control replies to the
user in the session, and code comments and docstrings.

## Conflicts

If a rule in this skill conflicts with the user's own instructions or with
`${CLAUDE_PLUGIN_ROOT}/standards.md`, obey the instructions or the standards.
Then do these steps:

1. Tell the user in the session, in one line. Name both rules and the rule that
   you obeyed.
2. Add one line to `${CLAUDE_PLUGIN_DATA}/removing-llm-tropes/CONFLICTS.md`.
   Create the file if it is absent. Give the date, the skill rule, the rule that
   you obeyed, and the type of text.
3. If that `CONFLICTS.md` already has a line for the same skill rule, ask the
   user for an edit to this skill.

Never put a conflict note in the text for the reader.

## Generation phase

Run both phases in order. Do not merge, skip, or reverse them.

1. Read `${CLAUDE_PLUGIN_ROOT}/guides/explanations.md` in full.
2. Create a complete draft in private working context. Write each explanation
   to the rules of that guide. A procedure keeps the procedure register of
   `${CLAUDE_PLUGIN_ROOT}/standards.md`.
3. Do not read `references/whip.md` or the trope reference until the complete
   first-pass draft exists.

The guide tells the writer what to write. The Writing Whip ban list and the
trope catalog name faults, so they work best on a draft that exists. Both are
review-time checks in this skill.

## Post-generation trope phase

If the text is one paragraph or shorter, check the draft against
[references/whip.md](references/whip.md) only. Then skip the rest of this phase.

An edit to an existing document is not short text. Audit each sentence that the
edit adds or changes against every trope, at any length. A rewrite that shortens
a passage is where "Short punchy fragments", "Empty label sentence" and
"Reference as actor" appear.

1. After the draft exists, read [references/whip.md](references/whip.md) and
   [references/tropes.md](references/tropes.md) in full.
2. Inspect the complete draft against every rule in `whip.md` and every trope
   in `tropes.md`.
3. Rewrite every violation unless keeping it is necessary for accuracy, safety,
   an explicit user constraint, a required format, code, or a quotation.
4. Check the rewritten draft once more so a correction does not introduce
   another listed trope.

Preserve the user's meaning, facts, constraints, intent, terminology, and
personal voice during the post-generation rewrite. Do not add unsupported claims
or ideas the user did not supply when editing existing text.

Return only the final revised text. Keep the first-pass draft, checklist,
audit, scores, reasoning, rule-break annotations, and changes out of the reply.
Show them only when the user asks for them. Never return the first-pass draft as
the final response.

## Hit log

The log shows which rules find tropes, and which rules never fire. A rule with
no hits is a candidate for removal. It is not proof, because the explanation guide can
stop a trope before the audit sees it.

1. After each use, add one line to
   `${CLAUDE_PLUGIN_DATA}/removing-llm-tropes/HITS.tsv`. If the file is absent,
   create it with the header row `date	source	text_type	rules`. Give the date,
   `self`, the type of text, and the names of the rules that caused a rewrite.
   If no rule caused a rewrite, leave the names empty.
2. If the user finds a trope in text that you wrote, add one line. Give the
   date, `user`, the type of text, and the name of the rule.
3. If `HITS.tsv` has 30 or more lines after the last `review` line, tell the
   user. List the rules in `references/whip.md` that have no hits since that
   line. Remove no rule until the user decides. Then add a `review` line with
   the date.
