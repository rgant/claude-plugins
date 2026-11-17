# Commit messages and pull requests

These rules add to `writing-for-people.md` in this directory. The
`writing:commit-message` skill applies them.

A commit subject and a PR title keep strict STE, as a procedure does. A commit
body and a PR description are explanations, so they follow `explanations.md` in
this directory.

- Commit subjects and PR titles name the change in the imperative mood: "if
  applied, this commit will ___". Write "fix the parser", never "fixed" or
  "fixes". A squash merge turns the PR title into a commit subject, so both
  follow these rules.
  - Name the change one level above the file list. "fix the integration tests",
    not a list of the four test classes that changed. The diff already shows
    which files.
  - Write: "stop triage from re-deciding settled labels". Not: "Triage was
    re-deciding settled labels, so I stopped it."
- Commit bodies describe the final code against the previous commit. PR
  descriptions describe it against the base branch. Either way that is the diff
  the reader opens, so the body must match it.
  - Existing commits are not the standard. These rules are. Do not read git log
    for style.
  - A defect in that baseline is worth naming. It is the reason for the change.
  - Do not describe code that was written then reworked before the commit. It is
    not in the diff.
  - If a change came out of review, describe the resulting code, not the
    finding.
  - A commit body leaves out how the change was verified. A future reader acts
    on none of it.
  - A PR description states each acceptance criterion and the evidence for it,
    because the reviewer acts on it. If a Jira item covers the PR, the criteria
    come from the item. If the repo has a PR template, fill in each section.
