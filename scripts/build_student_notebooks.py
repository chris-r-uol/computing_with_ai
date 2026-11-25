"""Generate student notebooks from the full ones, and validate their hints.

Authoring happens in the full notebooks under ``notebooks/``; the student copies
under ``student/`` are generated and never hand-maintained. A solution cell is
replaced by a stub, and its outputs are cleared, so no answer text leaves with it.

Solutions are deliberately open elsewhere in the module: students can always
reach the answer through the hint tiers on the site. What must never happen is
an answer sitting in the notebook a student is meant to write in, which is why
this stripping is tested and checked in CI.

Usage:
    uv run python scripts/build_student_notebooks.py            # regenerate
    uv run python scripts/build_student_notebooks.py --check    # fail if stale
"""

from __future__ import annotations

import argparse
import copy
import sys
from collections.abc import Sequence
from pathlib import Path

import nbformat
import yaml

SOLUTION_TAG = "solution"
EXERCISE_TAG = "exercise"
STUB_MARKER = "# your code here"
# Markdown and raw solution cells get a note, not a code comment (which would
# render as a heading).
TEXT_STUB = "*Write your answer here.*"
# The full notebooks wrap every solution source in this marker. The site render
# test greps rendered HTML for it, so a stripping bug fails that test as well.
SOLUTION_MARKER = "CWAI-SOLUTION"
HINT_TIERS = ("nudge", "method", "code")
REQUIRED_TIERS = ("nudge", "method")

REPO_ROOT = Path(__file__).resolve().parent.parent
NOTEBOOKS_DIR = REPO_ROOT / "notebooks"
STUDENT_DIR = REPO_ROOT / "student"


class SolutionMarkerError(ValueError):
    """A cell holds the solution marker but is not tagged as a solution."""


class MissingHintError(ValueError):
    """An exercise lacks a required hint tier, or has an unrecognised one."""


def wrap_solution(source: str) -> str:
    """Wrap a solution cell's source in the full notebooks' marker comments."""
    return f"# {SOLUTION_MARKER} begin\n{source}\n# {SOLUTION_MARKER} end"


def _tags(cell) -> list[str]:
    return list(cell.get("metadata", {}).get("tags", []))


def strip_solutions(nb: nbformat.NotebookNode) -> nbformat.NotebookNode:
    """Return a copy with every solution cell reduced to a stub.

    Tags are kept, so stripping an already-stripped notebook is a no-op. Outputs,
    attachments and all metadata other than tags are dropped, as they can carry
    the answer. Raises ``SolutionMarkerError`` if the solution marker appears in a
    cell that lacks the ``solution`` tag: a mistyped tag would otherwise leak.
    """
    out = copy.deepcopy(nb)
    for index, cell in enumerate(out.cells):
        tags = _tags(cell)
        if SOLUTION_TAG not in tags:
            if SOLUTION_MARKER in cell.source:
                raise SolutionMarkerError(
                    f"cell {index} contains {SOLUTION_MARKER} but its tags {tags} "
                    f"do not include {SOLUTION_TAG!r} (tags are case-sensitive)"
                )
            continue
        cell.metadata = nbformat.from_dict({"tags": tags} if tags else {})
        cell.pop("attachments", None)
        if cell.cell_type == "code":
            cell.source = STUB_MARKER
            cell.outputs = []
            cell.execution_count = None
        else:
            cell.source = TEXT_STUB
    return out


def _serialise(nb: nbformat.NotebookNode) -> bytes:
    return (nbformat.writes(nb) + "\n").encode("utf-8")


def _source_notebooks(root: Path) -> list[Path]:
    return sorted(
        p for p in root.rglob("*.ipynb") if ".ipynb_checkpoints" not in p.parts
    )


def _expected(src_root: Path) -> dict[Path, bytes]:
    """Relative path -> the exact bytes the student notebook should contain."""
    if not src_root.is_dir():
        raise NotADirectoryError(f"notebook source directory not found: {src_root}")
    return {
        p.relative_to(src_root): _serialise(
            strip_solutions(nbformat.read(p, as_version=4))
        )
        for p in _source_notebooks(src_root)
    }


def build(src_root: Path, out_root: Path) -> list[Path]:
    """Write a stripped copy of every notebook under ``src_root`` into ``out_root``."""
    written = []
    for rel, data in _expected(src_root).items():
        target = out_root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        written.append(target)
    return written


def stale_paths(src_root: Path, out_root: Path) -> list[Path]:
    """Student notebooks that are missing, out of date or orphaned. Writes nothing."""
    expected = _expected(src_root)
    problems = []
    for rel, data in expected.items():
        target = out_root / rel
        if not target.exists() or target.read_bytes() != data:
            problems.append(rel)
    if out_root.exists():
        problems += [
            p.relative_to(out_root)
            for p in _source_notebooks(out_root)
            if p.relative_to(out_root) not in expected
        ]
    return sorted(problems)


def exercise_ids(nb: nbformat.NotebookNode) -> list[str]:
    """Exercise ids in notebook order, from each cell's ``metadata.cwai.id``."""
    ids: list[str] = []
    for index, cell in enumerate(nb.cells):
        if EXERCISE_TAG not in _tags(cell):
            continue
        ex_id = cell.get("metadata", {}).get("cwai", {}).get("id")
        if not ex_id:
            raise ValueError(
                f"exercise cell {index} has no metadata.cwai.id; it cannot have hints"
            )
        if ex_id in ids:
            raise ValueError(f"duplicate exercise id {ex_id!r} (cell {index})")
        ids.append(ex_id)
    return ids


def hints_file_for(notebook_path: Path) -> Path:
    """Map ``notebooks/<stage>/<name>.ipynb`` to ``hints/<stage>.yml``."""
    stage_dir = notebook_path.parent
    return stage_dir.parent.parent / "hints" / f"{stage_dir.name}.yml"


def load_hints(path: Path) -> dict[str, dict[str, str]]:
    """Read a hints file: exercise id to tier name to text. An empty file is empty."""
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if data is None:
        return {}
    if not isinstance(data, dict) or not all(
        isinstance(v, dict) for v in data.values()
    ):
        raise ValueError(f"{path}: expected a mapping of exercise id to hint tiers")
    return data


def validate_hints(
    hints: dict[str, dict[str, str]], exercise_ids: Sequence[str]
) -> None:
    """Require a non-blank nudge and method for each exercise, and no other tier names.

    Hints for ids not in ``exercise_ids`` are ignored: one file serves a whole stage.
    """
    for ex_id in exercise_ids:
        tiers = hints.get(ex_id, {})
        unknown = sorted(set(tiers) - set(HINT_TIERS))
        if unknown:
            raise MissingHintError(
                f"exercise {ex_id!r} has unrecognised hint tier(s) {unknown}; "
                f"use only {list(HINT_TIERS)}"
            )
        for tier in REQUIRED_TIERS:
            text = tiers.get(tier)
            if not isinstance(text, str) or not text.strip():
                raise MissingHintError(
                    f"exercise {ex_id!r} is missing its {tier!r} hint"
                )


def check_notebook_hints(notebook_path: Path) -> None:
    """Validate one notebook's exercises against its stage's hints file."""
    ids = exercise_ids(nbformat.read(notebook_path, as_version=4))
    if not ids:
        return
    hints_file = hints_file_for(notebook_path)
    hints = load_hints(hints_file) if hints_file.exists() else {}
    validate_hints(hints, ids)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--src", type=Path, default=NOTEBOOKS_DIR)
    parser.add_argument("--out", type=Path, default=STUDENT_DIR)
    parser.add_argument(
        "--check",
        action="store_true",
        help="write nothing; exit 1 if the student notebooks are out of date",
    )
    args = parser.parse_args(argv)

    try:
        return _run(args)
    except (NotADirectoryError, SolutionMarkerError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


def _run(args: argparse.Namespace) -> int:
    if args.check:
        stale = stale_paths(args.src, args.out)
        for rel in stale:
            print(f"out of date: {rel}")
        if stale:
            print("Run: uv run python scripts/build_student_notebooks.py")
            return 1
        return 0

    for path in build(args.src, args.out):
        print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
