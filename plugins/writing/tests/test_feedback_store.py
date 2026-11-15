#!/usr/bin/env python3
"""Regression harness for the feedback store of the reviewing-edit-feedback skill."""

import fcntl
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "skills" / "reviewing-edit-feedback"))
from feedback_store import Record, Store  # noqa: E402


def record(draft_uuid: str, *, kind: str = "message", target: str = "", final: str = "Sent text.") -> Record:
    return Record(
        id=Record.make_id("s1", draft_uuid),
        kind=kind,
        session="s1",
        timestamp="2026-11-01T10:00:00Z",
        cwd="/work/repo",
        draft="Draft text.",
        final=final,
        requests=[],
        target=target,
    )


def add_twice_adds_once(root: Path) -> bool:
    store = Store(root)
    first = store.add([record("u1"), record("u2")])
    second = store.add([record("u1"), record("u2")])
    return first == 2 and second == 0 and len(store.records()) == 2


def known_target_skipped(root: Path) -> bool:
    store = Store(root)
    store.add([record("u1", kind="pr", target="https://github.com/o/r/pull/1", final="")])
    return store.add([record("u2", kind="pr", target="https://github.com/o/r/pull/1", final="")]) == 0


def update_final(root: Path) -> bool:
    store = Store(root)
    store.add([record("u1", kind="pr", target="https://github.com/o/r/pull/1", final="")])
    before = store.unclassified()
    store.update_final(Record.make_id("s1", "u1"), "Merged text.")
    after = store.unclassified()
    return before == [] and len(after) == 1 and after[0].final == "Merged text."


def unchanged_final_is_not_pending(root: Path) -> bool:
    store = Store(root)
    store.add([record("u1", kind="pr", target="https://github.com/o/r/pull/1", final="")])
    store.update_final(Record.make_id("s1", "u1"), "Draft   text.")
    return store.unclassified() == []


def labels_count_across_reviews(root: Path) -> bool:
    Store(root).add([record("u1"), record("u2")])
    Store(root).classify(Record.make_id("s1", "u1"), "wrong-rule", "drop-hedges")
    Store(root).classify(Record.make_id("s1", "u2"), "taste", "drop-hedges")
    counts = Store(root).labels()["drop-hedges"]
    return counts["wrong-rule"] == 1 and counts["taste"] == 1 and Store(root).unclassified() == []


def unknown_cause_fails(root: Path) -> bool:
    store = Store(root)
    store.add([record("u1")])
    try:
        store.classify(Record.make_id("s1", "u1"), "other", "drop-hedges")
    except ValueError:
        return True
    return False


def unknown_record_fails(root: Path) -> bool:
    try:
        Store(root).classify("missing", "taste", "drop-hedges")
    except KeyError:
        return True
    return False


def classify_twice_counts_once(root: Path) -> bool:
    store = Store(root)
    store.add([record("u1")])
    store.classify(Record.make_id("s1", "u1"), "taste", "drop-hedges")
    store.classify(Record.make_id("s1", "u1"), "wrong-rule", "drop-hedges")
    counts = store.labels()["drop-hedges"]
    return sum(counts.values()) == 1 and counts["wrong-rule"] == 1


def add_waits_for_the_lock(root: Path) -> bool:
    """A second writer must wait while another holds the store lock."""
    root.mkdir(parents=True)
    code = (
        f"import sys; sys.path.insert(0, {str(ROOT / 'skills' / 'reviewing-edit-feedback')!r}); "
        "from pathlib import Path; from feedback_store import Record, Store; "
        f"Store(Path({str(root)!r})).add([Record(id='s1:u9', kind='message', session='s1', timestamp='t', "
        "cwd='/w', draft='d', final='f')])"
    )
    with (root / ".lock").open("w") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        writer = subprocess.Popen([sys.executable, "-c", code])
        time.sleep(1)
        waited = writer.poll() is None
    writer.wait(timeout=10)
    return waited and len(Store(root).records()) == 1


def add_after_a_torn_line(root: Path) -> bool:
    root.mkdir(parents=True)
    (root / "records.jsonl").write_text('{"id": "torn', encoding="utf-8")
    store = Store(root)
    return store.add([record("u1")]) == 1 and len(store.records()) == 1


def empty_store(root: Path) -> bool:
    store = Store(root / "missing")
    return store.records() == [] and store.unclassified() == [] and store.labels() == {} and store.last_review() == ""


def mark_reviewed(root: Path) -> bool:
    store = Store(root)
    store.mark_reviewed()
    return Store(root).last_review().startswith("20")


def classify_after_a_torn_line(root: Path) -> bool:
    store = Store(root)
    store.add([record("u1")])
    (root / "classified.jsonl").write_text('{"id": "torn', encoding="utf-8")
    store.classify(Record.make_id("s1", "u1"), "taste", "drop-hedges")
    return sum(store.labels()["drop-hedges"].values()) == 1


def bad_record_line_is_skipped(root: Path) -> bool:
    store = Store(root)
    store.add([record("u1")])
    with (root / "records.jsonl").open("a", encoding="utf-8") as handle:
        handle.write('{"id": "s1:u2"}\n')
    return len(store.records()) == 1 and store.skipped_lines == 1


def update_finals_in_one_pass(root: Path) -> bool:
    store = Store(root)
    pr = "https://github.com/o/r/pull/"
    store.add([record("u1", kind="pr", target=pr + "1", final=""), record("u2", kind="pr", target=pr + "2", final="")])
    store.update_finals({Record.make_id("s1", "u1"): "One.", Record.make_id("s1", "u2"): "Two."})
    return sorted(item.final for item in store.records()) == ["One.", "Two."]


CASES: list[tuple[str, Callable[[Path], bool]]] = [
    ("classify after a torn line", classify_after_a_torn_line),
    ("bad record line is skipped", bad_record_line_is_skipped),
    ("update finals in one pass", update_finals_in_one_pass),
    ("add twice adds once", add_twice_adds_once),
    ("known target skipped", known_target_skipped),
    ("update final", update_final),
    ("unchanged final is not pending", unchanged_final_is_not_pending),
    ("labels count across reviews", labels_count_across_reviews),
    ("unknown cause fails", unknown_cause_fails),
    ("unknown record fails", unknown_record_fails),
    ("classify twice counts once", classify_twice_counts_once),
    ("add waits for the lock", add_waits_for_the_lock),
    ("add after a torn line", add_after_a_torn_line),
    ("empty store", empty_store),
    ("mark reviewed", mark_reviewed),
]


def main() -> None:
    failures = 0
    for name, case in CASES:
        with tempfile.TemporaryDirectory() as folder:
            try:
                ok = case(Path(folder) / "feedback")
            except Exception as error:  # noqa: BLE001 - a crash in one case is a failure of that case
                print(f"     {type(error).__name__}: {error}")
                ok = False
        print(f"{'ok ' if ok else 'FAIL'} {name}")
        failures += not ok
    print("ALL PASS" if not failures else f"FAILURES: {failures}")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
