"""Classify prose as procedural or descriptive, and lint each register by its own rules.

A procedure keeps the strict STE limits. An explanation can use the looser rules, so the
descriptive half moves some counts from hard to advisory. The prose gate and the hooks share
this module.
"""

import re
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))
import ste_lint  # noqa: E402

# `note` is absent on purpose. "Note that the cache expires" explains. It gives no instruction.
IMPERATIVES = frozenset(
    {
        "add",
        "always",
        "apply",
        "avoid",
        "build",
        "call",
        "check",
        "choose",
        "close",
        "configure",
        "confirm",
        "copy",
        "count",
        "create",
        "decrease",
        "delete",
        "disable",
        "do",
        "download",
        "enable",
        "ensure",
        "increase",
        "install",
        "join",
        "keep",
        "list",
        "make",
        "move",
        "name",
        "never",
        "open",
        "pick",
        "prefer",
        "push",
        "put",
        "read",
        "remove",
        "replace",
        "report",
        "restart",
        "return",
        "run",
        "see",
        "select",
        "send",
        "set",
        "split",
        "start",
        "stop",
        "store",
        "update",
        "use",
        "verify",
        "wait",
        "write",
    }
)
# These imperatives are also common nouns or modifiers, as in "Name collisions would break the
# registry". See `_reads_as_noun`.
NOUN_IMPERATIVES = frozenset(
    {
        "build",
        "call",
        "check",
        "close",
        "copy",
        "count",
        "download",
        "join",
        "list",
        "make",
        "move",
        "name",
        "open",
        "push",
        "read",
        "report",
        "restart",
        "return",
        "run",
        "select",
        "set",
        "split",
        "start",
        "stop",
        "store",
        "update",
        "use",
        "wait",
    }
)
# A word in this set starts the object of a command: "Set the flag", "Run `uv sync`", "Name what
# was rejected".
OBJECT_OPENERS = frozenset(
    {
        "a",
        "an",
        "the",
        "this",
        "that",
        "these",
        "those",
        "each",
        "every",
        "all",
        "any",
        "both",
        "your",
        "its",
        "their",
        "our",
        "my",
        "it",
        "them",
        "one",
        "no",
        "codespan",
        "what",
        "which",
        "who",
        "how",
        "where",
        "when",
        "why",
        "whether",
        "to",
        "up",
        "out",
        "down",
        "off",
        "on",
        "in",
        "into",
        "with",
        "for",
        "from",
        "at",
        "again",
        "only",
    }
)
# After a noun subject, one of these words is the verb of the sentence: "Set membership is".
FINITE_VERBS = frozenset(
    {
        "is",
        "are",
        "was",
        "were",
        "has",
        "have",
        "had",
        "does",
        "do",
        "did",
        "can",
        "cannot",
        "will",
        "must",
        "would",
        "could",
        "might",
        "should",
        "may",
    }
)
CONDITION_OPENERS = ("if", "when", "unless", "before", "after", "once")
PROCEDURE_HEADINGS = frozenset(
    {
        "steps",
        "setup",
        "install",
        "installation",
        "run",
        "procedure",
        "usage",
        "safety",
        "warning",
        "warnings",
        "caution",
        "danger",
    }
)
# A sub-heading that opens with one of these words starts an explanation inside a procedure
# section, so the procedure register stops there.
EXPLANATION_HEADINGS = frozenset({"design", "why", "notes", "rationale", "overview", "about", "concepts"})
EXPLANATION_HEADING_PHRASES = ("how it works", "design notes")
# A heading that opens with one of these phrases names a procedure too.
PROCEDURE_HEADING_PHRASES = ("getting started", "quick start", "quickstart")
PROCEDURE_CALLOUTS = frozenset({"WARNING", "CAUTION", "DANGER"})
# A firm modal states a requirement or a permission, so it stays banned in an explanation.
# A soft modal reports a possibility, and an explanation needs it.
FIRM_MODALS = re.compile(r"\b(should|may)(?:n't)?\b", re.IGNORECASE)
SOFT_MODALS = re.compile(r"\b(would|could|might)(?:n't)?\b", re.IGNORECASE)

CODE_SPAN = re.compile(r"``[^`\n]+``|`[^`\n]+`")
# A task-list item opens with `[ ]` or `[x]` after its marker.
LEADING_MARKUP = re.compile(r"^\s*(?:>\s*)*(?:(?:[-*+]|\d+[.)])\s+)*(?:\[[ xX]\]\s+)?[*_]*")
# The bold can close before the colon, as in `**Warning**: text`.
CONDITION_CONTINUES = re.compile(r"^\s*(?:and|or)\b", re.IGNORECASE)
THEN = re.compile(r"^\s*then\s+", re.IGNORECASE)
WARNING_LABEL = re.compile(r"^(?:warning|caution|danger)[*_]*\s*:", re.IGNORECASE)
# A YAML key can be quoted, dotted, or start with a digit.
FRONTMATTER_KEY = re.compile(r"""^\s*(?:"[^"]+"|'[^']+'|[\w.-]+)\s*:(?:\s|$)""")
HEADING_NUMBER = re.compile(r"^\d+[.)]\s+")
ATX_HEADING = re.compile(r"^\s{0,3}(#{1,6})(?:\s|$)")
QUOTE_PREFIX = re.compile(r"^\s*(?:>\s*)+")
CALLOUT_OPEN = re.compile(r"^\s*>\s*\[!(\w+)\]")
LIST_ITEM = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")
# A thematic break, such as `---` or `***`, separates sections. It holds no prose.
THEMATIC_BREAK = re.compile(r"^\s{0,3}([-*_])(?:\s*\1){2,}\s*$")
TASK_BOX = re.compile(r"^\[[ xX]\]\s+")
# A wholly bold line is a lead-in, the same pattern that `ste_lint.strip_code` drops. It is its
# own unit, so its words never set the register of the text under it.
BOLD_LINE = re.compile(r"^\s*\*\*[^\n]+\*\*\s*$")
# A closing marker can sit between the terminator and the space, as in "the proof.** After".
# Without those markers here, an inline bold sentence joins the sentence after it. A colon does
# not end a sentence, so a label such as `Warning:` stays with the words it labels.
SENTENCE_SPLIT = re.compile(r"(?<=[.!?])[*_`'\")\]]*\s+")
WORD_EDGES = ",.:;*_()\"'"

# In the descriptive half, a long sentence is advisory. Its count moves to this name.
_DESCRIPTIVE_RENAMES = {"sentence_over_limit": "length_read"}


@dataclass
class Sentence:
    """One sentence and the register it belongs to."""

    text: str
    procedural: bool


def _first_word(text: str) -> str:
    words = text.split()
    return words[0].strip(WORD_EDGES).lower() if words else ""


def heading_is_procedure(heading: str) -> bool:
    """Report whether a heading opens a procedure section, such as Setup or Deploy steps."""
    words = _heading_words(heading)
    if not words:
        return False
    phrase = " ".join(words)
    return words[0] in PROCEDURE_HEADINGS or words[-1] == "steps" or phrase.startswith(PROCEDURE_HEADING_PHRASES)


def _heading_words(heading: str) -> list[str]:
    text = heading.strip().lstrip("#").strip().replace("*", "").replace("_", "").strip()
    text = HEADING_NUMBER.sub("", text)
    return [word for word in (word.strip(WORD_EDGES).lower() for word in text.split()) if word]


def heading_is_explanation(heading: str) -> bool:
    """Report whether a heading opens an explanation, such as Design or How it works."""
    words = _heading_words(heading)
    return bool(words) and (words[0] in EXPLANATION_HEADINGS or " ".join(words).startswith(EXPLANATION_HEADING_PHRASES))


def _reads_as_noun(words: list[str]) -> bool:
    """Report whether a clause that opens with a word of `NOUN_IMPERATIVES` reads as a fact.

    A fact opens with a two-word noun phrase and then a form of be, a form of have, or a modal,
    as in "Set membership is constant time". Every other clause stays a command. A regex cannot
    tell "Read access stops" from "Run unit tests", so a clause with an ordinary verb third
    stays a command, and a fact in that shape gets the procedure rules.
    """
    return len(words) >= 3 and words[1] not in OBJECT_OPENERS and words[2] in FINITE_VERBS


def _opens_command(clause: str) -> bool:
    words = [word.strip(WORD_EDGES).lower() for word in clause.split()]
    words = [word for word in words if word]
    if not words or words[0] not in IMPERATIVES:
        return False
    return words[0] not in NOUN_IMPERATIVES or not _reads_as_noun(words)


def frontmatter_end(lines: list[str]) -> int:
    """Return the index of the first line after the YAML frontmatter, or 0 when there is none.

    Frontmatter is machine-facing configuration, not prose a reader reads. It opens with `---`,
    and its first line that is not blank and not a `#` comment is a `key:` line. A `---` rule
    before ordinary text is a thematic break, not frontmatter. A file that opens frontmatter and
    never closes it loses its first line only.
    """
    if not lines or lines[0].strip() != "---":
        return 0
    first = next((line for line in lines[1:] if line.strip() and not line.lstrip().startswith("#")), "")
    if not FRONTMATTER_KEY.match(first):
        return 0
    closing = next((index for index, line in enumerate(lines[1:], start=1) if line.strip() == "---"), 0)
    return closing + 1


def is_procedural(sentence: str, *, heading: str = "", callout: str = "") -> bool:
    """Report whether a sentence is an instruction.

    The sentence is procedural on its own words, or because its heading or callout is.
    """
    if callout.upper() in PROCEDURE_CALLOUTS or heading_is_procedure(heading):
        return True
    # A code span becomes a placeholder, so "`uv run` reads" does not start with "reads".
    text = LEADING_MARKUP.sub("", CODE_SPAN.sub("CODESPAN", sentence))
    if WARNING_LABEL.match(text):
        return True
    if _opens_command(text):
        return True
    if _first_word(text) in CONDITION_OPENERS:
        # The condition can hold a comma of its own, as in "If the job fails, or times out,
        # restart it". A clause that opens with "and" or "or" continues the condition, so the
        # test skips it. The first other clause is the main clause, and only that clause counts,
        # so a later clause such as ", never an error" does not make a fact a command.
        for clause in text.split(",")[1:]:
            if CONDITION_CONTINUES.match(clause):
                continue
            return _opens_command(THEN.sub("", clause))
    return False


class MarkdownContext:
    """Track the heading and the open callout while a reader walks markdown line by line.

    The prose gate and `classify` share this class, so both give one register to one text.
    A heading is an ATX line only. A wholly bold line is emphasis, not a heading.

    The class keeps every open heading by level. A sub-heading inside a procedure section,
    such as `### macOS` under `## Setup`, stays in that procedure. An explanation sub-heading,
    such as `### Design notes`, ends the procedure for its own section. A level-1 heading is the
    document title, so it never passes its register down. `heading` is the procedure heading
    that governs the current section, or the last heading when no procedure heading does.
    """

    def __init__(self) -> None:
        self.heading = ""
        self.callout = ""
        self._open: list[tuple[int, str]] = []

    def feed(self, line: str) -> str:
        """Update the context from one line and return the prose text of the line.

        A `> [!NAME]` line opens a callout. The first line that does not start with `>` closes
        it. The quote prefix is removed. Text after `[!NAME]` on the same line stays. An ATX
        heading line sets the heading and returns an empty string.
        """
        opened = CALLOUT_OPEN.match(line)
        if opened:
            self.callout = opened.group(1).upper()
            line = line[opened.end() :]
        elif self.callout and not line.lstrip().startswith(">"):
            self.callout = ""
        line = QUOTE_PREFIX.sub("", line)
        heading = ATX_HEADING.match(line)
        if heading:
            level = len(heading.group(1))
            self._open = [(depth, text) for depth, text in self._open if depth < level] + [(level, line)]
            self.heading = line
            for depth, text in reversed(self._open):
                if heading_is_procedure(text) and (depth > 1 or depth == level):
                    self.heading = text
                    break
                if heading_is_explanation(text):
                    break
            return ""
        return line


def sentence_spans(text: str) -> list[tuple[int, int]]:
    """Return the start and end of each sentence in *text*, with the outer space removed.

    The prose gate and `classify` both split with this function, so both read one text as the
    same sentences. A code span is masked first, so a period inside it does not end a sentence.
    """
    masked = CODE_SPAN.sub(lambda match: "X" * len(match.group(0)), text)
    spans: list[tuple[int, int]] = []
    start = 0
    for match in [*SENTENCE_SPLIT.finditer(masked), None]:
        stop = match.start() if match else len(text)
        left = start + len(text[start:stop]) - len(text[start:stop].lstrip())
        right = stop - (len(text[start:stop]) - len(text[start:stop].rstrip()))
        if left < right:
            spans.append((left, right))
        if match:
            start = match.end()
    return spans


def classify(markdown: str) -> list[Sentence]:
    """Split markdown into sentences and mark each as procedural or descriptive.

    YAML frontmatter is left out. A heading sets the register until the next heading of its
    level or higher. A `> [!NAME]` callout sets it until
    the first line outside the quote. A `Warning:` label marks the sentence it opens. A wholly
    bold line is a unit of its own. A unit of one word carries no sentence, so it is left out.
    """
    result: list[Sentence] = []
    context = MarkdownContext()
    buffer: list[str] = []

    def flush(heading: str, callout: str) -> None:
        paragraph = " ".join(buffer)
        buffer.clear()
        for start, stop in sentence_spans(paragraph):
            text = paragraph[start:stop]
            if len(text.split()) < 2:
                continue
            result.append(Sentence(text, is_procedural(text, heading=heading, callout=callout)))

    lines = ste_lint.strip_fences(markdown).split("\n")
    for raw in lines[frontmatter_end(lines) :]:
        before = (context.heading, context.callout)
        line = context.feed(raw)
        if (context.heading, context.callout) != before:
            # The buffer belongs to the context that ended on this line.
            flush(*before)
        if not line.strip() or THEMATIC_BREAK.match(line):
            flush(context.heading, context.callout)
            continue
        item = TASK_BOX.sub("", LIST_ITEM.sub("", line).strip())
        bold = bool(BOLD_LINE.match(item))
        if LIST_ITEM.match(line) or bold:
            flush(context.heading, context.callout)
        # The task box is markup, so it does not count as two words.
        buffer.append(item)
        if bold:
            flush(context.heading, context.callout)
    flush(context.heading, context.callout)
    return result


def split_registers(markdown: str) -> tuple[str, str]:
    """Return the procedural text and the descriptive text, one sentence per line."""
    items = classify(markdown)
    procedural = "\n".join(item.text for item in items if item.procedural)
    descriptive = "\n".join(item.text for item in items if not item.procedural)
    return procedural, descriptive


def _add(counts: dict[str, int], name: str, value: int) -> None:
    if value:
        counts[name] = counts.get(name, 0) + value


def lint_registers(text: str) -> dict[str, object]:
    """Lint each register by its own rules and return the counts.

    Every procedural count is hard. In the descriptive half, a soft modal and a long
    sentence are advisory, a trailing condition is ignored, and every other count is hard.
    Each sentence is linted alone, because `ste_lint.sentences` joins an unterminated line
    (a list item with no final period) to the next line. Synonym rotation compares
    sentences, so it comes from one run over each half.
    """
    items = classify(text)
    hard: dict[str, int] = {}
    advisory: dict[str, int] = {}
    lengths: list[int] = []
    for procedural in (True, False):
        texts = [item.text for item in items if item.procedural == procedural]
        register = "procedural" if procedural else "descriptive"
        for sentence in texts:
            report = ste_lint.lint(sentence, register)
            lengths.append(report["longest_sentence_words"])
            soft = 0 if procedural else len(SOFT_MODALS.findall(ste_lint.strip_code(sentence)))
            for name, value in report["violations"].items():
                if name == "synonym_rotation":
                    continue
                if procedural:
                    _add(hard, name, value)
                elif name == "banned_modal":
                    _add(hard, name, value - soft)
                    _add(advisory, "modal_read", soft)
                elif name == "trailing_condition":
                    continue
                elif name in _DESCRIPTIVE_RENAMES:
                    _add(advisory, _DESCRIPTIVE_RENAMES[name], value)
                else:
                    _add(hard, name, value)
        whole = ste_lint.lint("\n".join(texts), register)
        _add(hard, "synonym_rotation", whole["violations"]["synonym_rotation"])
    lengths = [length for length in lengths if length]
    return {
        "hard": hard,
        "advisory": advisory,
        "longest_sentence_words": max(lengths, default=0),
        "mean_sentence_words": round(sum(lengths) / max(1, len(lengths)), 1),
    }
