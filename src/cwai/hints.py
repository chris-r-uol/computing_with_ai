"""Tiered hints and collapsed outputs for lesson notebooks.

Both functions return an ``IPython.display.HTML`` made of native
``<details>``/``<summary>`` elements. They need no JavaScript and no live
kernel, so they work in JupyterLab and in the rendered Quarto site, and every
part is reachable with the keyboard.
"""

from __future__ import annotations

import difflib
from html import escape
from pathlib import Path

import yaml
from IPython.display import HTML

from cwai import registry

# Tier names, in the order they are shown. Kept as a flat tuple of names:
# scripts/build_student_notebooks.py does ``set(HINT_TIERS)`` on it.
HINT_TIERS: tuple[str, ...] = ("nudge", "method", "code", "answer")
TIER_LABELS: dict[str, str] = {
    "nudge": "Nudge",
    "method": "Method",
    "code": "Show the answer",
    "answer": "A model answer",
}
REQUIRED_TIERS: tuple[str, ...] = ("nudge", "method")
EXCLUSIVE_TIERS: frozenset[str] = frozenset({"code", "answer"})


class UnknownExerciseError(KeyError):
    """The exercise id has no entry in the hint files."""

    def __str__(self) -> str:  # KeyError would otherwise show the repr, in quotes
        return str(self.args[0])


def _read(file: Path) -> dict[str, dict[str, str]]:
    return yaml.safe_load(file.read_text(encoding="utf-8")) or {}


def _load(path: Path | None) -> dict[str, dict[str, str]]:
    if path is not None:
        return _read(Path(path))
    merged: dict[str, dict[str, str]] = {}
    origin: dict[str, Path] = {}
    for file in sorted((registry.repo_root() / "hints").glob("*.yml")):
        for key, entry in _read(file).items():
            if key in merged:
                raise ValueError(
                    f"The exercise id {key!r} appears in both "
                    f"{origin[key].name} and {file.name}. Each id must be unique."
                )
            merged[key] = entry
            origin[key] = file
    return merged


def _body(tier: str, text: str) -> str:
    safe = escape(str(text).rstrip("\n"))
    if tier == "code":
        return f"<pre><code>{safe}</code></pre>"
    if tier == "answer":
        return f"<pre>{safe}</pre>"
    return f"<p>{safe}</p>"


def hint(exercise_id: str, path: Path | None = None) -> HTML:
    """Show the hints for one exercise as collapsed, nested disclosures."""
    entries = _load(path)
    if exercise_id not in entries:
        near = difflib.get_close_matches(exercise_id, entries, n=3)
        advice = (
            f"Did you mean {' or '.join(repr(n) for n in near)}?"
            if near
            else "Check the spelling against the id given in the notebook."
        )
        raise UnknownExerciseError(f"There are no hints for {exercise_id!r}. {advice}")
    entry = entries[exercise_id]
    tiers = "".join(
        f"<details><summary>{escape(TIER_LABELS[t])}</summary>"
        f"{_body(t, entry[t])}</details>"
        for t in HINT_TIERS
        if t in entry
    )
    return HTML(
        f"<details><summary>Hints for <code>{escape(exercise_id)}</code></summary>"
        f"{tiers}</details>"
    )


def reveal(value: object, label: str = "Show the output") -> HTML:
    """Show a value inside a collapsed disclosure."""
    body = None
    method = getattr(value, "_repr_html_", None)
    if method is not None:
        try:
            body = method()
        except Exception:  # noqa: BLE001 - any failure falls back to repr
            body = None
    if not isinstance(body, str):
        body = f"<pre>{escape(repr(value))}</pre>"
    return HTML(f"<details><summary>{escape(label)}</summary>{body}</details>")
