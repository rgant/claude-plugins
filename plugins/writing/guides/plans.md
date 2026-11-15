# Plans

- Plan documents contain requirements, not code. No fenced implementation
  blocks, and do not start implementing while writing the doc. Paths, signatures
  (inline code ok), exact commands, and tests that must pass are the content.
- Do not count what is not built yet. A plan that says "six call sites" or
  "three retry paths" asserts a number nothing can know until the code exists.
  It rots as soon as it is wrong, and designing around it shapes the fix to a
  quantity rather than to the case. Name the case, say how to detect it, and say
  what to do about it. Six or twelve changes neither answer.
- This overrides the superpowers `writing-plans` rule mandating complete code in
  every step. Keep that skill's structure: task breakdown, TDD step order,
  checkboxes, interfaces, acceptance criteria, self-review. Applies when
  executing-plans or subagent-driven-development reference a plan too.
- Mark steps complete in the document as you finish them.
- Until the work ships, the design and the plan are working documents. Record
  each decision that the build or a review makes, so the steps and the types
  match the code. A plan with wrong steps teaches wrong steps to the reader who
  harvests it. After the work ships, the retire and audit skills govern the
  documents.
