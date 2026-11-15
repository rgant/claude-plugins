#!/usr/bin/env python3
"""Check the register classifier in lib/register.py.

Each case compares a result with the value the standards require.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
import register  # noqa: E402

DESCRIPTIVE_30 = (
    "The parser reads the manifest and then the scheduler reads the queue and then the worker "
    "reads the job and then the runner reads the log and then it writes."
)
IMPERATIVE_30 = DESCRIPTIVE_30.replace("The parser reads the manifest", "Read all of the manifest", 1)

failures = 0


def case(name: str, got: object, want: object) -> None:
    global failures
    passed = got == want
    failures += not passed
    print(f"{'ok ' if passed else 'FAIL'} {name}")
    if not passed:
        print(f"     got {got!r}, want {want!r}")


def flags(markdown: str) -> list[bool]:
    return [item.procedural for item in register.classify(markdown)]


def main() -> None:
    proc = register.is_procedural
    case("imperative opener", proc("Run the tests before you push."), True)
    case("condition then imperative", proc("If the build fails, read the log."), True)
    case("warning label", proc("Warning: the command deletes the branch."), True)
    needs = "The script needs uv."
    case("procedure heading, phrase", proc(needs, heading="Setup on a new machine"), True)
    case("procedure heading, bold", proc(needs, heading="**Setup**"), True)
    case("procedure heading, numbered", proc(needs, heading="2. Install"), True)
    case("procedure heading, hashes", proc(needs, heading="## Install"), True)
    case("steps as last word", proc(needs, heading="Deploy steps"), True)
    case("warning callout", proc("The command deletes the branch.", callout="WARNING"), True)
    case("plain descriptive", proc("The parser reads the manifest first."), False)
    case("note is not imperative", proc("Note that the cache expires after one hour."), False)
    case("consider is not imperative", proc("Consider the case where two writers start."), False)
    case("condition then descriptive", proc("If the cache is cold, the first call takes longer."), False)
    case("code span opener", proc("`uv run` reads the lock file."), False)
    case("run as noun in heading", proc(needs, heading="How the run works"), False)
    case("note callout", proc("The command deletes the branch.", callout="NOTE"), False)
    case("open task item", proc("- [ ] Run the tests before you push."), True)
    case("done task item", proc("- [x] Run the tests before you push."), True)
    case("noun opener with a modal", proc("Name collisions would break the registry."), False)
    case("noun opener with is", proc("Set membership is constant time."), False)
    case("noun opener with are", proc("Return values are cached by the worker."), False)
    case("noun opener with must", proc("List items must not nest."), False)
    case("noun opener with has", proc("Build output has one file per target."), False)
    case("noun opener after a condition", proc("If the token expires, read access is gone."), False)
    case("bare plural object", proc("Run tests before you push."), True)
    case("question word object", proc("Name what was rejected and why."), True)
    case("modifier and plural object", proc("Run unit tests before merging."), True)
    case("object after an adjective", proc("Set environment variables now."), True)
    case("command with a condition after it", proc("Stop if errors appear."), True)
    case("wait until", proc("Wait until jobs finish."), True)
    case("known limit: a fact with an ordinary verb", proc("Read access stops at midnight."), True)
    case("comma inside the condition", proc("If the job fails, or times out, restart it."), True)
    case("then after the condition", proc("When you finish, then run the tests."), True)
    case("condition, fact, never", proc("If the file is missing, the loader returns an empty list, never an error."), False)
    case("condition holds a list", proc("If a user can read, edit, or delete an item, the audit log records it."), False)
    case("condition with and, then a fact", proc("When the cache is cold, and use of the disk rises, the log grows."), False)
    case("condition with and, then a command", proc("If the build fails, and the log is empty, restart the job."), True)
    case("condition then two facts", proc("If the cache is cold, the first call takes longer, and the log grows."), False)
    case("danger callout", proc("The script needs uv.", callout="DANGER"), True)
    case("object with a determiner", proc("Set the flag before the build."), True)
    case("object as a code span", proc("Run `uv sync` first."), True)
    case("command after a condition", proc("If the token expires, set a new one."), True)
    case("never opener", proc("Never push to main."), True)
    case("remove opener", proc("Remove the lock file."), True)
    case("bold warning, colon outside", proc("**Warning**: this deletes data."), True)
    case("getting started heading", proc(needs, heading="## Getting started"), True)
    case("quick start heading", proc(needs, heading="Quick start"), True)

    case("numbered list item", register.classify("1. The cache is per user."), [register.Sentence("The cache is per user.", False)])
    case("heading scope", flags("## Steps\n\nThe script needs uv.\n\n## Design\n\nThe script needs uv.\n"), [True, False])
    case(
        "callout scope",
        flags("> [!WARNING]\n> The command deletes the branch.\n\nThe command deletes the branch.\n"),
        [True, False],
    )
    case("bold line is not a heading", flags("**Setup**\n\nThe script needs uv.\n"), [False])
    case("callout text on the opening line", flags("> [!WARNING] The command deletes the branch.\n"), [True])
    context = register.MarkdownContext()
    case("context strips the quote", context.feed("> [!NOTE] Text here."), " Text here.")
    case("context keeps the callout", context.callout, "NOTE")
    case("context ends the callout", (context.feed("Plain."), context.callout), ("Plain.", ""))
    case("context sets an ATX heading", (context.feed("## Setup"), context.heading), ("", "## Setup"))
    case("warning label in classify", flags("Warning: the command deletes the branch.\n"), [True])
    case("fenced code is skipped", flags("```\nRun the tests now.\n```\n"), [])
    case(
        "sub-heading stays in the procedure",
        flags("## Setup\n\n### macOS\n\nThe script needs uv.\n\n## Design\n\nThe script needs uv.\n"),
        [True, False],
    )
    case(
        "procedure sub-heading under an explanation",
        flags("## Design\n\n### Steps\n\nThe script needs uv.\n\n### Notes\n\nThe script needs uv.\n"),
        [True, False],
    )
    frontmatter = "---\nname: demo\ndescription: it's done; you should run it\n---\n\nThe cache is per user.\n"
    case("frontmatter is skipped", flags(frontmatter), [False])
    front = register.lint_registers(frontmatter)
    case("frontmatter adds no counts", (front["hard"], front["advisory"]), ({}, {}))
    case("frontmatter_end without frontmatter", register.frontmatter_end(["# Title", "---"]), 0)
    case("frontmatter_end with frontmatter", register.frontmatter_end(["---", "a: b", "---", "Text"]), 3)
    case("frontmatter_end with a thematic break", register.frontmatter_end(["---", "Hello there.", "", "---", "More."]), 0)
    case("frontmatter_end unclosed", register.frontmatter_end(["---", "a: b", "Text"]), 1)
    case("frontmatter_end after a comment", register.frontmatter_end(["---", "# note", "name: x", "---", "Body."]), 4)
    case("frontmatter_end after a blank line", register.frontmatter_end(["---", "", "name: x", "---", "Body."]), 4)
    for key in ('"name": x', "x.y: z", "2fa: on"):
        case(f"frontmatter_end with key {key}", register.frontmatter_end(["---", key, "---", "Body."]), 3)
    case("frontmatter_end with a colon in prose", register.frontmatter_end(["---", "Note:this", "---"]), 0)
    broken = register.classify("---\nHello there, this is an intro.\n\n---\n\nMore text here.\n")
    want = [register.Sentence("Hello there, this is an intro.", False), register.Sentence("More text here.", False)]
    case("a thematic break keeps its text", broken, want)
    case("title does not pass a procedure down", flags("# Setup guide\n\n## Design\n\nThe script needs uv.\n"), [False])
    case("title is a procedure for its own text", flags("# Setup guide\n\nThe script needs uv.\n"), [True])
    case(
        "explanation sub-heading ends the procedure",
        flags("## Usage\n\n### Design notes\n\nThe script needs uv.\n\n#### Details\n\nThe script needs uv.\n"),
        [False, False],
    )
    case("background jobs stays a procedure", flags("## Setup\n\n### Background jobs\n\nThe script needs uv.\n"), [True])
    case("how it works sub-heading", flags("## Setup\n\n### How it works\n\nThe script needs uv.\n"), [False])

    procedural, descriptive = register.split_registers("Run the tests now.\n\nThe cache is per user. Stop the worker.\n")
    case("split procedural", procedural, "Run the tests now.\nStop the worker.")
    case("split descriptive", descriptive, "The cache is per user.")

    modal = register.lint_registers("The default would carry a credential, so the deployment might connect to a sandbox.\n")
    case("soft modals are advisory", modal["advisory"], {"modal_read": 2})
    case("soft modals are not hard", "banned_modal" in modal["hard"], False)
    case("firm modal is hard", register.lint_registers("You should restart the worker.\n")["hard"], {"banned_modal": 1})
    case(
        "soft modal in an imperative is hard",
        register.lint_registers("Run the worker, and it would restart.\n")["hard"],
        {"banned_modal": 1},
    )
    desc = register.lint_registers(DESCRIPTIVE_30)
    case("fixture is 30 words", desc["longest_sentence_words"], 30)
    case("long descriptive is advisory", desc["advisory"], {"length_read": 1})
    case("long descriptive is not hard", desc["hard"], {})
    imp = register.lint_registers(IMPERATIVE_30)
    case("fixture imperative is 30 words", imp["longest_sentence_words"], 30)
    case("long imperative is hard", imp["hard"], {"sentence_over_limit": 1})
    trailing = register.lint_registers("The worker restarts the queue when the lock expires.\n")
    case("trailing when is dropped", (trailing["hard"], trailing["advisory"]), ({}, {}))

    task = "- [ ] Run the full suite on the staging server and read the report for each failure in the cache today.\n"
    task_report = register.lint_registers(task)
    case("task fixture is 19 words", task_report["longest_sentence_words"], 19)
    case("task box adds no words", task_report["hard"], {})
    case("task item in classify", flags(task), [True])

    items = ["Start the worker", "Open the queue", "Read the log file", "Stop the worker"]
    imperative = register.lint_registers("\n".join(f"- {item}" for item in items) + "\n")
    case("unterminated imperative list is not hard", imperative["hard"], {})
    case("unterminated imperative list longest", imperative["longest_sentence_words"], 4)
    facts = ["The worker owns the queue", "The cache is per user", "The log holds one line", "The lock expires"]
    listed = register.lint_registers("\n".join(f"- {item}" for item in facts) + "\n")
    case("unterminated descriptive list has no length_read", listed["advisory"], {})
    case("unterminated descriptive list is not hard", listed["hard"], {})
    case("unterminated descriptive list longest", listed["longest_sentence_words"], 5)

    print("ALL PASS" if not failures else f"FAILURES: {failures}")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
