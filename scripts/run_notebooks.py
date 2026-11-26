"""Execute every notebook in a fresh kernel and report which ones fail.

Each notebook runs on its own, from the repository root, so a notebook that
quietly relies on another notebook's variables (or on a file only present on the
author's machine) fails here rather than in a student's hands.

A cell that fails on purpose needs the `raises-exception` tag so this script
accepts it, and `#| error: true` as its first line so the Quarto render accepts
it. See "Writing a cell that fails on purpose" in `student/README.md`.

Usage:
    uv run python scripts/run_notebooks.py notebooks/
"""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass
from pathlib import Path

import nbformat
from nbclient import NotebookClient

# The design's ceiling for one notebook on the 2-core, 8 GB target machine.
TIMEOUT_SECONDS = 120
REPO_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class NotebookResult:
    path: Path
    passed: bool
    seconds: float
    error: str | None


def run(path: Path, timeout: int = TIMEOUT_SECONDS) -> NotebookResult:
    """Execute one notebook in a fresh kernel; report failure, never raise it.

    ``timeout`` bounds each cell inside the kernel, and the notebook as a whole
    is also failed if it finishes later than ``timeout`` seconds after starting.
    """
    start = time.monotonic()
    error: str | None = None
    try:
        notebook = nbformat.read(path, as_version=4)
        NotebookClient(
            notebook,
            timeout=timeout,
            kernel_name="python3",
            allow_errors=False,
            resources={"metadata": {"path": str(REPO_ROOT)}},
        ).execute()
    except Exception as exc:  # noqa: BLE001 - one bad notebook must not hide the rest
        error = f"{type(exc).__name__}: {exc}"
    seconds = time.monotonic() - start
    if error is None and seconds > timeout:
        error = f"Timeout: took {seconds:.0f}s, over the {timeout}s limit."
    return NotebookResult(path, error is None, seconds, error)


def _find(root: Path) -> list[Path]:
    return sorted(
        p for p in root.rglob("*.ipynb") if ".ipynb_checkpoints" not in p.parts
    )


def run_all(root: Path, timeout: int = TIMEOUT_SECONDS) -> list[NotebookResult]:
    """Run every notebook under ``root``, sorted by path, one result each."""
    return [run(path, timeout) for path in _find(root)]


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    root = Path(args[0]) if args else REPO_ROOT / "notebooks"
    results = run_all(root)
    if not results:
        print(f"No notebooks found under {root}.", file=sys.stderr)
        return 1
    for r in results:
        print(f"{'PASS' if r.passed else 'FAIL'}  {r.path}  ({r.seconds:.1f}s)")
        if r.error:
            print(r.error)
    failed = [r for r in results if not r.passed]
    print(f"\n{len(results) - len(failed)} passed, {len(failed)} failed.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
