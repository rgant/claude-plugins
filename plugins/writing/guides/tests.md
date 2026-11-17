# Tests

These rules add to the Code section of `../standards.md`.

- Test doubles, in preference order: no double > fake > stub > spy > mock.
  Assert on behavior and state, not call sequences or implementation details.
  Mock only boundaries you do not own. In Python, use `patch` or `MagicMock` for
  a third-party SDK. In React, use MSW for an API call, a real provider over a
  mocked context, and `vi.fn()` for a callback prop. Three or more doubles means
  the production code needs a refactor first.
  - A double must match the real thing it stands in for: the same names,
    signatures, and return types. If a double drifts from the real one, fix the
    double. Never cast, silence, or loosen a type to pass a drifted double. A
    change to a real class includes the check of its doubles. A cast, a silence,
    or a loosened type at the place a test passes a double is evidence of drift.
    A test review reports each one, and an existing one too, with the drifted
    signature as the cause.
- Do not write a test that asserts a config value against a copy of itself. A
  person who changes the value on purpose edits the test in the same commit,
  so a pass tells little. If a config gap can recur, fix the structure. A test
  that compares two real sources is fine, such as a config file against the
  code constant that reads it.
- Judge lost coverage by whole-suite fault detection, not by the line coverage
  of one file. Before you recommend a test for a path, inject a fault there and
  run the whole suite. If another test catches the fault, the change removed
  duplicate coverage, and no new test is needed.
- In pytest, request a fixture that a test needs only for its side effect with
  `@pytest.mark.usefixtures`, or with a module `pytestmark`. Do not add an
  unused parameter and silence the linter on it.
