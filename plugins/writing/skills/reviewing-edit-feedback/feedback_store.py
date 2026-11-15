"""The store of draft and final pairs for the reviewing-edit-feedback skill.

The store is a directory under `CLAUDE_PLUGIN_DATA`. It holds these files:

- `records.jsonl`: one draft and final pair on each line.
- `classified.jsonl`: one cause and correction label on each line. A later line for a record
  replaces an earlier one.
- `state.json`: the time of the last review.

The store holds messages to coworkers and text from client repositories, so it never enters a
repository.
"""

import contextlib
import fcntl
import json
import os
import re
import tempfile
from collections import Counter
from collections.abc import Iterator
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

KINDS = frozenset({"message", "pr", "ticket"})
CAUSES = frozenset({"wrong-rule", "broken-rule", "wrong-fact", "final-error", "taste"})
# An edit of a PR or a ticket in a later session is not a new first draft, so the store keeps one
# record for each target of these kinds.
TARGETED = frozenset({"pr", "ticket"})
WHITESPACE = re.compile(r"\s+")


@dataclass(frozen=True)
class Record:
    """One draft that Claude wrote, and the text that the user sent."""

    id: str
    kind: str
    session: str
    timestamp: str
    cwd: str
    draft: str
    final: str
    requests: list[str] = field(default_factory=list)
    target: str = ""
    # The name of the ticket tool in `tickets.json` that made a `ticket` record.
    tool: str = ""

    @staticmethod
    def make_id(session: str, draft_uuid: str) -> str:
        return f"{session}:{draft_uuid}"


class Store:
    """Read and write the store in *root*. A missing directory reads as an empty store."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self._records = root / "records.jsonl"
        self._classified = root / "classified.jsonl"
        self._state = root / "state.json"
        # The count of lines in `records.jsonl` that the last read did not use.
        self.skipped_lines = 0

    def records(self) -> list[Record]:
        return self._scan()[0]

    def _scan(self) -> tuple[list[Record], list[str]]:
        """Read the records, and keep each line that does not build a record as raw text.

        A torn line, a hand edit, or a line from another version of this code fits no `Record`. A
        rewrite keeps those lines as they are, because a later version can still read them.
        """
        records: list[Record] = []
        raw: list[str] = []
        for line in _raw_lines(self._records):
            try:
                value = json.loads(line)
                records.append(Record(**value))
            except ValueError, TypeError:
                raw.append(line)
        self.skipped_lines = len(raw)
        return records, raw

    @contextlib.contextmanager
    def _locked(self) -> Iterator[None]:
        """Hold the store lock, so two extractions or a review and an extraction never interleave.

        The SessionStart hook starts a detached extraction, and a review can start while it runs.
        Without the lock, a read and a later write in one run could discard the other run's records.
        """
        self.root.mkdir(parents=True, exist_ok=True)
        with (self.root / ".lock").open("w") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            yield

    def add(self, records: list[Record]) -> int:
        """Append each record that the store lacks, and return the count added."""
        with self._locked():
            return self._add(records)

    def _add(self, records: list[Record]) -> int:
        held = self.records()
        ids = {record.id for record in held}
        targets = {record.target for record in held if record.kind in TARGETED}
        new: list[Record] = []
        for record in records:
            if record.kind not in KINDS:
                raise ValueError(f"unknown kind: {record.kind}")
            if record.id in ids or (record.kind in TARGETED and record.target in targets):
                continue
            ids.add(record.id)
            if record.kind in TARGETED:
                targets.add(record.target)
            new.append(record)
        if new:
            _append(self._records, [json.dumps(asdict(record)) for record in new])
        return len(new)

    def update_final(self, record_id: str, final: str) -> None:
        self.update_finals({record_id: final})

    def update_finals(self, finals: dict[str, str]) -> None:
        """Set the final of each record in *finals*, in one rewrite of the file."""
        with self._locked():
            held, raw = self._scan()
            missing = set(finals) - {record.id for record in held}
            if missing:
                raise KeyError(sorted(missing)[0])
            updated = [_with_final(record, finals[record.id]) if record.id in finals else record for record in held]
            lines = [json.dumps(asdict(record)) for record in updated] + raw
            _replace(self._records, "".join(line + "\n" for line in lines))

    def classify(self, record_id: str, cause: str, label: str) -> None:
        if cause not in CAUSES:
            raise ValueError(f"unknown cause: {cause}")
        if record_id not in {record.id for record in self.records()}:
            raise KeyError(record_id)
        with self._locked():
            _append(self._classified, [json.dumps({"id": record_id, "cause": cause, "label": label})])

    def unclassified(self) -> list[Record]:
        done = self._classifications()
        return [record for record in self.records() if record.final and record.id not in done and not same_text(record.draft, record.final)]

    def labels(self) -> dict[str, Counter[str]]:
        """Count the causes of the classified records for each label."""
        counts: dict[str, Counter[str]] = {}
        for cause, label in self._classifications().values():
            counts.setdefault(label, Counter())[cause] += 1
        return counts

    def last_review(self) -> str:
        try:
            return str(json.loads(self._state.read_text(encoding="utf-8")).get("last_review", ""))
        except OSError, ValueError, AttributeError:
            return ""

    def mark_reviewed(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(UTC).isoformat(timespec="seconds")
        _replace(self._state, json.dumps({"last_review": stamp}) + "\n")

    def _classifications(self) -> dict[str, tuple[str, str]]:
        """Map each record ID to its latest (cause, label)."""
        return {str(line["id"]): (str(line["cause"]), str(line["label"])) for line in _read_lines(self._classified)}


def same_text(first: str, second: str) -> bool:
    """Compare two texts with each run of whitespace collapsed to one space."""
    return WHITESPACE.sub(" ", first).strip() == WHITESPACE.sub(" ", second).strip()


def _with_final(record: Record, final: str) -> Record:
    return Record(**{**asdict(record), "final": final})


def _raw_lines(path: Path) -> list[str]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return []
    return [line for line in text.splitlines() if line.strip()]


def _append(path: Path, lines: list[str]) -> None:
    """Append *lines* to a JSON-lines file. A torn last line has no newline, so a new line must start on its own."""
    with path.open("a", encoding="utf-8") as handle:
        if handle.tell() and not path.read_bytes().endswith(b"\n"):
            handle.write("\n")
        for line in lines:
            handle.write(line + "\n")


def _read_lines(path: Path) -> list[dict[str, object]]:
    """Read one JSON object from each line.

    A process killed during a write can leave a torn line, so a line that does not parse drops out.
    """
    lines: list[dict[str, object]] = []
    for line in _raw_lines(path):
        try:
            value = json.loads(line)
        except ValueError:
            continue
        if isinstance(value, dict):
            lines.append(value)
    return lines


def _replace(path: Path, text: str) -> None:
    """Write *text* to a temporary file next to *path*, then rename it, so a crash leaves the current file whole."""
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        handle.write(text)
    os.replace(handle.name, path)
