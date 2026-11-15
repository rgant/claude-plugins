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
