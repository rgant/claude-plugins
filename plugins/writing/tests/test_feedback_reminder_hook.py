#!/usr/bin/env python3
"""Regression harness for feedback-reminder-hook.py, the SessionStart hook of the feedback loop."""

import json
import os
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOOK = ROOT / "hooks" / "feedback-reminder-hook.py"
sys.path.insert(0, str(ROOT / "skills" / "reviewing-edit-feedback"))
from extract_feedback import PASTE_BACK  # noqa: E402

SKILL = "writing:reviewing-edit-feedback"


def stamp(days_ago: float) -> str:
    return (datetime.now(UTC) - timedelta(days=days_ago)).isoformat(timespec="seconds")


def run(folder: Path, *, data: bool = True) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ, CLAUDE_CONFIG_DIR=str(folder / "config"))
    env.pop("CLAUDE_PLUGIN_DATA", None)
    if data:
        env["CLAUDE_PLUGIN_DATA"] = str(folder / "data")
    payload = json.dumps({"hook_event_name": "SessionStart", "source": "startup"})
    return subprocess.run([sys.executable, str(HOOK)], input=payload, capture_output=True, text=True, env=env, timeout=30)


def store(folder: Path) -> Path:
    path = folder / "data" / "feedback"
    path.mkdir(parents=True, exist_ok=True)
    return path


def seed(folder: Path, *, last_review: str | None, extracted: bool = True) -> None:
    """Write the state files. A recent extraction time keeps the hook from starting an extraction."""
    if last_review is not None:
        (store(folder) / "state.json").write_text(json.dumps({"last_review": last_review}), encoding="utf-8")
    if extracted:
        (store(folder) / "reminder.json").write_text(json.dumps({"last_extract": stamp(0)}), encoding="utf-8")


def reminds(proc: subprocess.CompletedProcess[str]) -> bool:
    if proc.returncode != 0 or not proc.stdout.strip():
        return False
    payload = json.loads(proc.stdout)["hookSpecificOutput"]
    return payload["hookEventName"] == "SessionStart" and SKILL in payload["additionalContext"]


def quiet(proc: subprocess.CompletedProcess[str]) -> bool:
    return proc.returncode == 0 and not proc.stdout.strip() and not proc.stderr.strip()


def recent_review_is_quiet(folder: Path) -> bool:
    seed(folder, last_review=stamp(2))
    return quiet(run(folder))


def old_review_reminds(folder: Path) -> bool:
    seed(folder, last_review=stamp(8))
    return reminds(run(folder))


def absent_state_reminds(folder: Path) -> bool:
    seed(folder, last_review=None)
    return reminds(run(folder))


def once_a_day(folder: Path) -> bool:
    seed(folder, last_review=stamp(8))
    return reminds(run(folder)) and quiet(run(folder))


def daily_extraction(folder: Path) -> bool:
    session = folder / "config" / "projects" / "proj" / "s1.jsonl"
    session.parent.mkdir(parents=True)
    lines = [
        {
            "type": "assistant",
            "sessionId": "s1",
            "uuid": "a1",
            "timestamp": "2026-11-01T10:00:00Z",
            "cwd": "/w",
            "message": {"content": [{"type": "text", "text": f"Draft.\n\n{PASTE_BACK}"}]},
        },
        {
            "type": "user",
            "sessionId": "s1",
            "uuid": "b1",
            "timestamp": "2026-11-01T10:01:00Z",
            "cwd": "/w",
            "message": {"content": "SENT> Sent text."},
        },
    ]
    session.write_text("".join(json.dumps(line) + "\n" for line in lines), encoding="utf-8")
    seed(folder, last_review=stamp(2), extracted=False)
    run(folder)
    records = store(folder) / "records.jsonl"
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline and not records.exists():
        time.sleep(0.2)
    time.sleep(1)
    run(folder)
    time.sleep(1)
    log = (store(folder) / "extract.log").read_text(encoding="utf-8")
    return records.exists() and log.count("added ") == 1


def unreadable_state_is_quiet(folder: Path) -> bool:
    seed(folder, last_review=None)
    (store(folder) / "state.json").write_text("not json", encoding="utf-8")
    return quiet(run(folder))


def corrupt_times_recover(folder: Path) -> bool:
    seed(folder, last_review=stamp(8), extracted=False)
    (store(folder) / "reminder.json").write_text("not json", encoding="utf-8")
    first = run(folder)
    times = json.loads((store(folder) / "reminder.json").read_text(encoding="utf-8"))
    return reminds(first) and bool(times.get("last_extract"))


def no_data_directory_is_quiet(folder: Path) -> bool:
    return quiet(run(folder, data=False))


def corrupt_state_saves_the_extraction_time(folder: Path) -> bool:
    seed(folder, last_review=None, extracted=False)
    (store(folder) / "state.json").write_text("[1", encoding="utf-8")
    first = run(folder)
    times = json.loads((store(folder) / "reminder.json").read_text(encoding="utf-8"))
    return quiet(first) and bool(times.get("last_extract"))


def bad_timestamp_recovers(folder: Path) -> bool:
    seed(folder, last_review=stamp(2), extracted=False)
    (store(folder) / "reminder.json").write_text(json.dumps({"last_extract": "garbage"}), encoding="utf-8")
    run(folder)
    times = json.loads((store(folder) / "reminder.json").read_text(encoding="utf-8"))
    return times.get("last_extract") not in {None, "garbage"}


CASES: list[tuple[str, Callable[[Path], bool]]] = [
    ("corrupt state saves the extraction time", corrupt_state_saves_the_extraction_time),
    ("bad timestamp recovers", bad_timestamp_recovers),
    ("recent review is quiet", recent_review_is_quiet),
    ("old review reminds", old_review_reminds),
    ("absent state reminds", absent_state_reminds),
    ("once a day", once_a_day),
    ("daily extraction", daily_extraction),
    ("unreadable state is quiet", unreadable_state_is_quiet),
    ("corrupt times recover", corrupt_times_recover),
    ("no data directory is quiet", no_data_directory_is_quiet),
]


def main() -> None:
    failures = 0
    for name, case in CASES:
        with tempfile.TemporaryDirectory() as folder:
            try:
                ok = case(Path(folder))
            except Exception as error:  # noqa: BLE001 - a crash in one case is a failure of that case
                print(f"     {type(error).__name__}: {error}")
                ok = False
        print(f"{'ok ' if ok else 'FAIL'} {name}")
        failures += not ok
    print("ALL PASS" if not failures else f"FAILURES: {failures}")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
