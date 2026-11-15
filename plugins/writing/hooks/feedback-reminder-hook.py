#!/usr/bin/env python3
"""SessionStart hook. Saves new feedback pairs once a day, and reminds Claude when a review is due.

Claude Code deletes old transcripts, so the hook starts the extractor of the
reviewing-edit-feedback skill once a day in a detached process. The pairs then reach the store
even if the user skips reviews. The extraction runs without the network fetch, and the hook does
not wait for it.

If the last review is more than 7 days old, or no review exists, the hook adds one line that tells
Claude to suggest a review. It adds that line at most once a day.

The hook reads `state.json` with `json` and imports no script of the skill, so a fault in the
skill cannot block a session. On any error, it prints nothing and exits 0. It keeps its own times
in `reminder.json`, so no other code writes that file, and it writes the file through a rename.
"""

import json
import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

EXTRACTOR = Path(__file__).resolve().parent.parent / "skills" / "reviewing-edit-feedback" / "extract_feedback.py"
REVIEW_DUE = timedelta(days=7)
DAILY = timedelta(days=1)
REMINDER = (
    "A writing review is due. Suggest that the user run the `writing:reviewing-edit-feedback` skill, "
    "which turns the user's edits to Claude's drafts into proposed rule changes."
)


def older_than(stamp: object, age: timedelta, now: datetime) -> bool:
    """Answer whether *stamp* is absent or older than *age*. A stamp that does not parse counts as absent, so the hook rewrites it."""
    try:
        moment = datetime.fromisoformat(str(stamp))
    except ValueError:
        return True
    return moment.tzinfo is None or now - moment > age


def read_times(path: Path) -> dict[str, str]:
    """Read the hook's own times. A file that does not parse reads as empty, so the hook rewrites it.

    If an unreadable file stopped the hook, the daily extraction would stop with no notice, and the
    transcripts would expire.
    """
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except OSError, ValueError:
        return {}
    return value if isinstance(value, dict) else {}


def start_extraction(store: Path) -> None:
    store.mkdir(parents=True, exist_ok=True)
    with (store / "extract.log").open("a", encoding="utf-8") as log:
        subprocess.Popen(
            [sys.executable, str(EXTRACTOR), "--store", str(store), "extract"],
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )


def run() -> None:
    data = os.environ.get("CLAUDE_PLUGIN_DATA")
    if not data:
        return
    store = Path(data) / "feedback"
    now = datetime.now(UTC)
    times_file = store / "reminder.json"
    times = read_times(times_file)
    if older_than(times.get("last_extract"), DAILY, now):
        start_extraction(store)
        times["last_extract"] = now.isoformat(timespec="seconds")
    state_file = store / "state.json"
    # A state file that does not parse gives no reminder, because the time of the last review is
    # unknown. The hook still saves its own times, so the daily extraction keeps its pace.
    state = read_times(state_file) if state_file.exists() else {"last_review": ""}
    review_due = "last_review" in state and older_than(state["last_review"], REVIEW_DUE, now)
    remind = review_due and older_than(times.get("last_reminder"), DAILY, now)
    if remind:
        times["last_reminder"] = now.isoformat(timespec="seconds")
    store.mkdir(parents=True, exist_ok=True)
    temporary = times_file.with_suffix(".tmp")
    temporary.write_text(json.dumps(times) + "\n", encoding="utf-8")
    os.replace(temporary, times_file)
    if remind:
        output = {"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": REMINDER}}
        print(json.dumps(output))


def main() -> None:
    try:
        run()
    except Exception:  # noqa: BLE001, S110 - a reminder must never block a session
        pass


if __name__ == "__main__":
    main()
