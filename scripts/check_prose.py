"""Check that student-facing prose stays in plain English.

Most students read this material in English as a second language, so §7.8 of the
design makes plain English a constraint rather than a preference. A stated rule
is kept by a careful author and missed by a hurried one, so this script checks
it in CI.

The gate is a floor, not the goal. It measures four things:

``sentence-too-long``
    One sentence runs past ``MAX_SENTENCE_WORDS`` words.
``mean-sentence-too-long``
    No single sentence is long, but the text as a whole reads dense.
``discouraged-phrase``
    A phrase in ``PLAIN_ALTERNATIVES`` has a plainer replacement.
``jargon-not-in-glossary``
    A term in ``JARGON`` is used, but ``site/glossary.qmd`` does not define it.

It cannot tell whether prose is good for these readers. Prose that is dense but
short passes. A sentence that reads badly aloud passes. A term explained in a
way nobody understands passes. Read your own writing out loud as well.

Code is not prose, so fenced blocks, inline code spans, table rows and URLs are
taken out before anything is measured.

Usage:
    uv run python scripts/check_prose.py site/index.qmd hints/
"""

from __future__ import annotations

import ast
import json
import re
import sys
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from functools import cache
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
GLOSSARY = REPO_ROOT / "site" / "glossary.qmd"

MAX_SENTENCE_WORDS = 25
MAX_MEAN_SENTENCE_WORDS = 18
# A mean over one or two sentences says nothing about a text's register, and a
# single long sentence is already reported by its own rule.
MIN_SENTENCES_FOR_MEAN = 3
# In a Python module, a one-word literal is a name, a key or a column, not
# prose. Two words can already be a phrase, so that is where the gate starts.
MIN_LITERAL_WORDS = 2

# A discouraged phrase, and the plain word to write instead. The list grows:
# adding to it is ordinary maintenance, not a change of policy.
PLAIN_ALTERNATIVES: dict[str, str] = {
    "utilise": "use",
    "regarding": "about",
    "prior to": "before",
    "in order to": "to",
    "bear in mind": "remember",
    "a number of": "some",
    "in the event that": "if",
    "commence": "start",
    "terminate": "stop",
    "endeavour": "try",
    "facilitate": "help",
    "subsequently": "then",
    "nevertheless": "but",
    "call off": "cancel",
    "cut down on": "reduce",
    "carry out": "do",
    "down the line": "later",
    "on the fly": "while it runs",
}

# Technical terms that must be in the glossary before they are used. Sentence
# length cannot catch an undefined term: "the slice has no denominator" is nine
# plain words in the active voice, and a student who has met neither word is
# still stuck. Seeded with the transport and statistics vocabulary of stages 1
# and 2, which the glossary's programming terms did not cover, and then with
# the four words the gate's first run over the stage pages showed it was
# missing: the name of the dataset, and the three words stage 2 is about.
JARGON: frozenset[str] = frozenset(
    {
        "agent",
        "agentic",
        "aggregate",
        "autocomplete",
        "casualty",
        "categorical",
        "collision",
        "denominator",
        "diff",
        "exposure",
        "kernel",
        "KSI",
        "parquet",
        "rate",
        "severity",
        "slice",
        "STATS19",
    }
)

# Skipped by name, with the reason, so a later reader sees a decision and not
# an oversight. Nothing else is exempt.
EXEMPT: dict[str, str] = {
    "accessibility.qmd": (
        "A legal statement. Its precision is the point, and it quotes the "
        "regulations in their own words."
    ),
    "glossary.qmd": (
        "A list of terms, not prose. It is also where the jargon rule looks "
        "each term up, so it cannot be held to that rule itself."
    ),
}


@dataclass(frozen=True)
class Finding:
    """One problem with one sentence, named where an author can fix it."""

    source: str
    line: int
    rule: str
    detail: str


# --- taking the code out of the prose ---

_FENCE = re.compile(r"^(?:```|~~~)")
_TABLE_ROW = re.compile(r"^\|.*\|$")
_DIV_FENCE = re.compile(r"^:::+\s*(?:\{.*\})?$")
_CODE_SPAN = re.compile(r"`{1,2}[^`\n]+`{1,2}")
_URL = re.compile(r"(?:https?://|www\.)\S+")
_MASK = re.compile("\x00(\\d+)\x00")
_LINK = re.compile(r"\[([^\]]*)\]\([^)\s]*\)")
_HTML_TAG = re.compile(r"<[^>\n]+>")
_ATTRIBUTES = re.compile(r"\{[^}\n]*\}")
_HEADING = re.compile(r"^#{1,6}\s+")
_BULLET = re.compile(r"^(?:[-*+]\s+|\d+[.)]\s+|>\s*)")
_EMPHASIS = re.compile(r"\*{1,3}|__")
_WORD = re.compile(r"[0-9A-Za-z]")
_TERMINATOR = re.compile(r"[.!?]+[\"')\]]*")
# Guarded so that a short abbreviation does not end a sentence. "etc." is left
# out on purpose: it usually does end one.
_ABBREVIATIONS = frozenset(
    {
        "e.g.",
        "i.e.",
        "cf.",
        "vs.",
        "approx.",
        "dr.",
        "mr.",
        "mrs.",
        "ms.",
    }
)
# These guard only when a number follows, which is when they are abbreviating
# something. An unguarded "no." swallowed the sentence after "the answer is
# no.", and merging two sentences inflates the count of both.
_NUMBERED = frozenset({"no.", "nos.", "fig.", "figs.", "p.", "pp.", "ch."})


def _mask(line: str, masks: list[str]) -> str:
    """Replace code spans and URLs with a token that counts as one word."""

    def keep(match: re.Match[str]) -> str:
        masks.append(match.group(0))
        return f"\x00{len(masks) - 1}\x00"

    return _URL.sub(keep, _CODE_SPAN.sub(keep, line))


def _unmask(text: str, masks: list[str]) -> str:
    return _MASK.sub(lambda m: masks[int(m.group(1))], text)


def _strip_markup(line: str) -> str:
    """Drop the markup around the words, keeping the words themselves."""
    line = _HEADING.sub("", line.strip())
    line = _BULLET.sub("", line)
    line = _LINK.sub(r"\1", line)
    line = _HTML_TAG.sub(" ", line)
    line = _ATTRIBUTES.sub("", line)
    return _EMPHASIS.sub("", line).strip()


def _word_count(text: str) -> int:
    return sum(1 for token in text.split() if _WORD.search(token))


def _starts_sentence(char: str) -> bool:
    """Whether a character can open a sentence.

    A capital is not required. A sentence may start with a lower-case name,
    such as ``pandas``. What keeps a decimal or an abbreviation from splitting
    is the whitespace test and ``_ABBREVIATIONS``, not a capital.

    The dashes matter here. This repository writes an em dash as ``--``, so a
    sentence really does begin with a hyphen, and a missing one merged two
    sentences into a count that could fail the length rule on its own.
    """
    return char.isalnum() or char in "\x00\"'`([*_#-—–“‘"


def _after_abbreviation(text: str, end: int) -> bool:
    tail = text[:end].split()
    token = tail[-1].lower() if tail else ""
    if token in _ABBREVIATIONS:
        return True
    return token in _NUMBERED and text[end:].lstrip()[:1].isdigit()


def _spans(paragraph: str) -> list[tuple[int, int]]:
    """The (start, end) of each sentence in one paragraph."""
    spans: list[tuple[int, int]] = []
    start = 0
    for match in _TERMINATOR.finditer(paragraph):
        end = match.end()
        rest = paragraph[end:]
        if not rest[:1].isspace():
            continue  # a decimal point, or a dot inside a word
        nxt = rest.lstrip()
        if not nxt or not _starts_sentence(nxt[0]):
            continue
        if _after_abbreviation(paragraph, end):
            continue
        spans.append((start, end))
        start = len(paragraph) - len(nxt)
    if paragraph[start:].strip():
        spans.append((start, len(paragraph)))
    return spans


@dataclass(frozen=True)
class _Unit:
    """One sentence, with the line it starts on and the code masked out."""

    line: int
    masked: str
    text: str
    punctuated: bool


def _prose_lines(text: str, first_line: int, masks: list[str]) -> list[tuple[int, str]]:
    lines: list[tuple[int, str]] = []
    fenced = False
    for offset, raw in enumerate(text.split("\n")):
        stripped = raw.strip()
        if _FENCE.match(stripped):
            fenced = not fenced
            continue
        if fenced or _TABLE_ROW.match(stripped) or _DIV_FENCE.match(stripped):
            continue
        lines.append((first_line + offset, _strip_markup(_mask(raw, masks))))
    return lines


def _units(text: str, first_line: int) -> list[_Unit]:
    """Split a text into sentences, each knowing the line it starts on."""
    masks: list[str] = []
    units: list[_Unit] = []
    paragraph: list[tuple[int, str]] = []

    def flush() -> None:
        if not paragraph:
            return
        joined = ""
        starts: list[tuple[int, int]] = []
        for line, content in paragraph:
            if joined:
                joined += " "
            starts.append((len(joined), line))
            joined += content
        for start, end in _spans(joined):
            masked = joined[start:end].strip()
            if not masked:
                continue
            line = next(no for at, no in reversed(starts) if at <= start)
            units.append(
                _Unit(
                    line=line,
                    masked=masked,
                    text=_unmask(masked, masks),
                    punctuated=bool(_TERMINATOR.search(masked[-3:])),
                )
            )
        paragraph.clear()

    for line, content in _prose_lines(text, first_line, masks):
        if content:
            paragraph.append((line, content))
        else:
            flush()
    flush()
    return units


def sentences(text: str) -> list[str]:
    """The sentences in ``text``, with code, tables and markup taken out."""
    return [unit.text for unit in _units(text, 1)]


# --- the glossary the jargon rule reads ---


@cache
def glossary_terms(path: Path | None = None) -> frozenset[str]:
    """The English terms defined in the glossary table, in lower case."""
    rows = (Path(path) if path else GLOSSARY).read_text(encoding="utf-8").split("\n")
    terms = set()
    for row in rows:
        row = row.strip()
        if not row.startswith("|"):
            continue
        term = row.strip("|").split("|")[0].strip().strip("`*").strip().lower()
        if not term or term == "english" or not _WORD.search(term):
            continue
        terms.add(term)
    return frozenset(terms)


def _plural(term: str) -> str:
    stem = re.escape(term).replace(r"\ ", r"\s+")
    if term.endswith("y"):
        return stem[:-1] + "(?:y|ies)"
    return stem + "(?:e?s)?"


@cache
def _phrase_patterns() -> tuple[tuple[str, str, re.Pattern[str]], ...]:
    return tuple(
        (phrase, plain, re.compile(rf"\b{re.escape(phrase)}\b", re.IGNORECASE))
        for phrase, plain in PLAIN_ALTERNATIVES.items()
    )


@cache
def _jargon_patterns() -> tuple[tuple[str, re.Pattern[str]], ...]:
    return tuple(
        (term, re.compile(rf"\b{_plural(term)}\b", re.IGNORECASE))
        for term in sorted(JARGON)
    )


# --- the rules ---


def check_text(
    text: str,
    source: str,
    *,
    glossary: frozenset[str] | None = None,
    first_line: int = 1,
) -> list[Finding]:
    """Every problem the rules find in ``text``, in the order they appear."""
    known = glossary_terms() if glossary is None else glossary
    units = _units(text, first_line)
    findings: list[Finding] = []

    for unit in units:
        words = _word_count(unit.masked)
        if words > MAX_SENTENCE_WORDS:
            findings.append(
                Finding(
                    source,
                    unit.line,
                    "sentence-too-long",
                    f"{words} words in one sentence, and the limit is "
                    f"{MAX_SENTENCE_WORDS}. Say one thing per sentence.",
                )
            )
        for phrase, plain, pattern in _phrase_patterns():
            if pattern.search(unit.masked):
                findings.append(
                    Finding(
                        source,
                        unit.line,
                        "discouraged-phrase",
                        f'"{phrase}" is hard to read for a reader whose first '
                        f'language is not English. Write "{plain}".',
                    )
                )

    reported: set[str] = set()
    for unit in units:
        for term, pattern in _jargon_patterns():
            if term in reported or term.lower() in known:
                continue
            if pattern.search(unit.masked):
                reported.add(term)
                findings.append(
                    Finding(
                        source,
                        unit.line,
                        "jargon-not-in-glossary",
                        f'"{term}" is a technical term, and site/glossary.qmd '
                        "does not define it. Add it there, then explain it "
                        "the first time you use it.",
                    )
                )

    punctuated = [unit for unit in units if unit.punctuated]
    if len(punctuated) >= MIN_SENTENCES_FOR_MEAN:
        mean = sum(_word_count(u.masked) for u in punctuated) / len(punctuated)
        if mean > MAX_MEAN_SENTENCE_WORDS:
            findings.append(
                Finding(
                    source,
                    punctuated[0].line,
                    "mean-sentence-too-long",
                    f"{mean:.1f} words per sentence over {len(punctuated)} "
                    f"sentences, and the limit is {MAX_MEAN_SENTENCE_WORDS}. "
                    "No one sentence is too long, but the text reads dense.",
                )
            )

    return sorted(findings, key=lambda f: (f.line, f.rule))


# --- the file readers ---


def check_qmd(path: Path) -> list[Finding]:
    """Check a Quarto page: its front matter, then its body."""
    path = Path(path)
    lines = path.read_text(encoding="utf-8").split("\n")
    findings: list[Finding] = []
    body_at = 1
    if lines and lines[0].strip() == "---":
        for index in range(1, len(lines)):
            if lines[index].strip() in {"---", "..."}:
                findings += _check_yaml("\n".join(lines[1:index]), str(path), offset=2)
                body_at = index + 2
                break
    body = "\n".join(lines[body_at - 1 :])
    return findings + check_text(body, str(path), first_line=body_at)


def check_notebook(path: Path) -> list[Finding]:
    """Check a notebook's markdown cells.

    A code cell is not checked. Its comments are written for the next author,
    and the student reads the markdown around it.
    """
    path = Path(path)
    cells = json.loads(path.read_text(encoding="utf-8")).get("cells", [])
    findings: list[Finding] = []
    for index, cell in enumerate(cells, start=1):
        if cell.get("cell_type") != "markdown":
            continue
        source = cell.get("source", "")
        text = "".join(source) if isinstance(source, list) else source
        findings += check_text(text, f"{path} (cell {index})")
    return findings


def check_hints(path: Path) -> list[Finding]:
    """Check the hint wording in a ``hints/*.yml`` file.

    A student reads a hint when they are stuck, which is the worst moment to
    meet a long sentence. Keys are ids, not prose, so only values are checked.
    """
    path = Path(path)
    return _check_yaml(path.read_text(encoding="utf-8"), str(path), offset=1)


def check_module(path: Path) -> list[Finding]:
    """Check the message strings in a Python module.

    Docstrings are left alone: the next author reads those, not a student. A
    line number points at the start of the string, not always at the sentence.
    """
    path = Path(path)
    tree = ast.parse(path.read_text(encoding="utf-8"))
    findings: list[Finding] = []
    for node in _literals(tree):
        text = _literal_text(node)
        if _word_count(text) >= MIN_LITERAL_WORDS:
            findings += check_text(text, str(path), first_line=node.lineno)
    return sorted(findings, key=lambda f: (f.line, f.rule))


def _check_yaml(text: str, source: str, offset: int) -> list[Finding]:
    """Check every string value in a YAML document; ``offset`` is its first line."""
    findings: list[Finding] = []
    node = yaml.compose(text)
    for scalar in _scalar_values(node):
        if scalar.tag != "tag:yaml.org,2002:str":
            continue
        findings += check_text(
            scalar.value, source, first_line=scalar.start_mark.line + offset
        )
    return findings


def _scalar_values(node: yaml.Node | None) -> Iterator[yaml.ScalarNode]:
    if isinstance(node, yaml.ScalarNode):
        yield node
    elif isinstance(node, yaml.SequenceNode):
        for item in node.value:
            yield from _scalar_values(item)
    elif isinstance(node, yaml.MappingNode):
        for _key, value in node.value:
            yield from _scalar_values(value)


def _docstrings(tree: ast.AST) -> set[int]:
    holders = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
    found = set()
    for node in ast.walk(tree):
        if not isinstance(node, holders):
            continue
        first = node.body[0] if node.body else None
        if (
            isinstance(first, ast.Expr)
            and isinstance(first.value, ast.Constant)
            and isinstance(first.value.value, str)
        ):
            found.add(id(first.value))
    return found


def _literals(tree: ast.AST) -> Iterator[ast.Constant | ast.JoinedStr]:
    """Every string literal in a module, skipping docstrings."""
    skip = _docstrings(tree)
    queue: list[ast.AST] = [tree]
    while queue:
        node = queue.pop(0)
        if isinstance(node, ast.JoinedStr):
            if id(node) not in skip:
                yield node
            continue  # its parts are one string, so do not visit them twice
        if isinstance(node, ast.Constant):
            if isinstance(node.value, str) and id(node) not in skip:
                yield node
            continue
        queue.extend(ast.iter_child_nodes(node))


def _literal_text(node: ast.Constant | ast.JoinedStr) -> str:
    """The literal text of a string, with any ``{...}`` expression as one word."""
    if isinstance(node, ast.Constant):
        return node.value
    parts = []
    for part in node.values:
        if isinstance(part, ast.Constant) and isinstance(part.value, str):
            parts.append(part.value)
        else:
            parts.append("value")
    return "".join(parts)


# --- the command line ---

READERS = {
    ".qmd": check_qmd,
    ".md": check_qmd,
    ".ipynb": check_notebook,
    ".yml": check_hints,
    ".yaml": check_hints,
    ".py": check_module,
}
# Walked when a directory is given. A Python module is checked only when it is
# named, because most modules in this repository are build tools and a licence
# registry, and neither is prose a student reads.
WALKED = (".qmd", ".ipynb", ".yml", ".yaml")


def _unusable(target: str, detail: str) -> Finding:
    """A target the gate cannot read is a finding, never a silent pass.

    The whole value of this gate is that a future author cannot drift past it.
    A renamed path that reported success would be worse than no gate at all,
    because the green tick would say the prose had been checked.
    """
    return Finding(target, 0, "unusable-target", detail)


def check_path(path: Path) -> list[Finding]:
    """Check one file, unless it is exempt. Report it if it cannot be read."""
    path = Path(path)
    if path.name in EXEMPT:
        return []  # a decision, recorded in EXEMPT with its reason
    if not path.exists():
        return [
            _unusable(
                str(path),
                "no such file or directory, so nothing here was checked. "
                "Correct the path given to the gate.",
            )
        ]
    reader = READERS.get(path.suffix)
    if reader is None:
        return [
            _unusable(
                str(path),
                f"the gate has no rule set for a '{path.suffix}' file, so "
                "nothing here was checked. Give it a file it can read, or add "
                "a reader for this kind.",
            )
        ]
    return reader(path)


def _walk(folder: Path) -> list[Path]:
    return sorted(
        found
        for found in folder.rglob("*")
        if found.is_file()
        and found.suffix in WALKED
        and ".ipynb_checkpoints" not in found.parts
    )


def _collect(targets: Iterable[str]) -> list[Path]:
    """Every file the given targets name. A directory is walked for WALKED."""
    paths: list[Path] = []
    for target in targets:
        path = Path(target)
        paths += _walk(path) if path.is_dir() else [path]
    return paths


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else list(argv)
    if not args:
        print(__doc__)
        return 2
    findings: list[Finding] = []
    for target in args:
        folder = Path(target)
        if folder.is_dir() and not _walk(folder):
            findings.append(
                _unusable(
                    target,
                    "this directory holds no file the gate can read "
                    f"({', '.join(WALKED)}), so nothing here was checked.",
                )
            )
    for path in _collect(args):
        findings += check_path(path)
    for finding in findings:
        print(f"{finding.source}:{finding.line}: {finding.rule} — {finding.detail}")
    if findings:
        count = len(findings)
        problems = "problem" if count == 1 else "problems"
        print(f"\n{count} {problems}. See §7.8 of the design, or this script.")
        return 1
    print("Prose gate passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
