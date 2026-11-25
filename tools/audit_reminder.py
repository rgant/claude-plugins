#!/usr/bin/env python3
"""SessionStart hook. Tells Claude to suggest a session audit when the last run is 21 days old.

A hook in Rob's own `~/.claude/settings.json` runs this script, because the audit serves him and
not other users of the plugins. The script reads the totals file back from its end, and stops at
the start of the last line, so it stays fast at the start of every session.

A missing totals file, or a last line whose run time does not parse, counts as due. If either
counted as not due, the reminder would stop for good after one bad write. On any other error the
script prints nothing and exits 0, so a fault here cannot block a session.
"""

import argparse
import json
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

# Claude Code deletes a transcript after about 30 days, so a run must come sooner than that, or the
# sessions of the gap are lost.
DUE_AFTER = timedelta(days=21)
CHUNK_BYTES = 65536
AUDIT = Path(__file__).resolve().parent / "audit_sessions.py"
DEFAULT_TOTALS = Path.home() / ".claude" / "session-audit" / "totals.jsonl"
TOTALS_VARIABLE = "SESSION_AUDIT_TOTALS"


def last_line(path: Path) -> str:
    """Return the last non-empty line of *path*. Read back from the end until the whole line is in hand.

    Each run writes one line that holds every session, so the line can be longer than one read.
    """
    with path.open("rb") as handle:
        end = handle.seek(0, os.SEEK_END)
        tail = b""
        while end > 0:
            start = max(0, end - CHUNK_BYTES)
            handle.seek(start)
            tail = handle.read(end - start) + tail
            end = start
            if b"\n" in tail.rstrip(b"\n"):
                break
    lines = tail.decode("utf-8", errors="replace").splitlines()
    return next((line for line in reversed(lines) if line.strip()), "")


def due(totals: Path, now: datetime) -> bool:
    """Answer whether the last run in *totals* is absent, unreadable, or older than `DUE_AFTER`."""
    if not totals.is_file():
        return True
    try:
        run = datetime.fromisoformat(str(json.loads(last_line(totals))["run"]))
    except ValueError, KeyError, TypeError:
        return True
    return run.tzinfo is None or now - run > DUE_AFTER


def main() -> int:
    argparse.ArgumentParser(description=__doc__.splitlines()[0]).parse_args()
    try:
        named = os.environ.get(TOTALS_VARIABLE)
        if due(Path(named) if named else DEFAULT_TOTALS, datetime.now(UTC)):
            print(f"A session audit is due. Suggest that the user run `{AUDIT}`, which counts how sessions follow the guides.")
    except Exception:  # The hook must never block a session, so any fault prints nothing.
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
