import re
import shutil
from pathlib import Path

import nbformat
import pytest
from build_student_notebooks import (
    EXERCISE_TAG,
    SOLUTION_MARKER,
    SOLUTION_TAG,
    build,
    wrap_solution,
)
from render_site import SITE_OUT, render

from cwai import registry

REPO = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).parent / "fixtures"
SITE_SRC = REPO / "site"
SECRET_OUTPUT = "the-secret-answer-1234"


def _copy_site(dest: Path) -> Path:
    """A throwaway copy of the Quarto project, so rendering never dirties ``site/``."""
    shutil.copytree(
        SITE_SRC,
        dest,
        ignore=shutil.ignore_patterns(
            "_freeze", ".quarto", "notebooks", "data.qmd", "_site"
        ),
    )
    return dest


@pytest.fixture(scope="module")
def site(tmp_path_factory) -> Path:
    """The real site, rendered once from the student notebooks."""
    root = tmp_path_factory.mktemp("real")
    out = root / SITE_OUT
    done = render(_copy_site(root / "site"), out)
    assert done.returncode == 0, done.stdout + done.stderr
    return out


def solution_notebook_site(tmp_path: Path) -> tuple[Path, Path]:
    """Render a notebook that really had a solution cell, via the real stripper."""
    nb = nbformat.v4.new_notebook()
    exercise = nbformat.v4.new_code_cell(
        "# your code here", metadata={"tags": [EXERCISE_TAG]}
    )
    solution = nbformat.v4.new_code_cell(
        wrap_solution(f"print('{SECRET_OUTPUT}')"),
        metadata={"tags": [SOLUTION_TAG]},
    )
    solution.outputs = [nbformat.v4.new_output("stream", text=SECRET_OUTPUT)]
    nb.cells = [nbformat.v4.new_markdown_cell("# Exercise page"), exercise, solution]
    nb.metadata["kernelspec"] = {
        "display_name": "Python 3",
        "language": "python",
        "name": "python3",
    }
    full = tmp_path / "full"
    (full / "stage").mkdir(parents=True)
    nbformat.write(nb, full / "stage" / "with-solution.ipynb")
    # Precondition: the unstripped notebook does contain what must not leak.
    assert SOLUTION_MARKER in (full / "stage" / "with-solution.ipynb").read_text()
    student = tmp_path / "student"
    (path,) = build(full, student)
    return path, tmp_path


def test_render_fails_when_a_notebook_errors(tmp_path):
    # A broken notebook must not reach a published page.
    site = _copy_site(tmp_path / "site")
    done = render(site, tmp_path / "out", notebooks=[FIXTURES / "broken.ipynb"])
    assert done.returncode != 0


def test_render_runs_a_good_notebook_and_shows_its_output(site):
    html = (site / "notebooks/01-foundations/00-smoke.html").read_text()
    assert "Smoke test" in html
    # The student copy ships without outputs, so this proves the render executed it.
    assert "sensor" in html.lower()
    assert "cell-output" in html


def test_rendered_site_contains_no_solution_cell_content(site, tmp_path):
    html = (site / "notebooks/01-foundations/00-smoke.html").read_text()
    assert SOLUTION_MARKER not in html


def test_stripped_solution_cell_never_reaches_the_rendered_page(tmp_path):
    """Non-vacuous: a notebook with a real solution, through the real stripper."""
    path, root = solution_notebook_site(tmp_path)
    assert SOLUTION_MARKER not in path.read_text()
    out = root / "out"
    done = render(_copy_site(root / "site"), out, notebooks=[path])
    assert done.returncode == 0, done.stdout + done.stderr
    pages = list(out.rglob("with-solution.html"))
    assert len(pages) == 1
    html = pages[0].read_text()
    assert "Exercise page" in html  # it rendered the notebook, not an empty case
    assert "your code here" in html  # the stub is what the student sees
    assert SOLUTION_MARKER not in html
    assert SECRET_OUTPUT not in html


def test_data_page_lists_every_registered_dataset(site):
    html = (site / "data.html").read_text()
    for info in registry.list_datasets():
        assert info.title in html


def test_data_page_carries_required_attribution_strings(site):
    html = (site / "data.html").read_text()
    assert "Open Government Licence v3.0" in html
    assert "OpenStreetMap contributors" in html
    for info in registry.list_datasets():
        # Attribution is read from the registry, not retyped; HTML-escape aside.
        assert info.attribution.replace("©", "©") in html


def test_every_page_declares_a_language(site):
    pages = list(site.rglob("*.html"))
    assert pages
    for page in pages:
        assert 'lang="en"' in page.read_text(), page


def test_index_states_both_routes(site):
    html = (site / "index.html").read_text().lower()
    assert "codespace-first" in html
    assert "site-first" in html


def test_accessibility_statement_and_glossary_are_published(site):
    assert "WCAG 2.2" in (site / "accessibility.html").read_text()
    glossary = (site / "glossary.html").read_text()
    assert "变量" in glossary  # Chinese equivalents are present
    assert len(re.findall(r"<tr", glossary)) >= 21  # header + twenty terms


def _tokens(css: str, selector: str) -> dict[str, str]:
    block = re.search(re.escape(selector) + r"\s*\{(.*?)\}", css, re.S).group(1)
    return dict(re.findall(r"--cwai-([\w-]+):\s*(#[0-9a-fA-F]{6})", block))


def _luminance(hex_colour: str) -> float:
    channels = [int(hex_colour[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    r, g, b = (
        c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels
    )
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a: str, b: str) -> float:
    hi, lo = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


# (foreground, background, minimum ratio): 4.5 for text, 3 for non-text.
PAIRS = [
    ("fg", "bg", 4.5),
    ("muted", "bg", 4.5),
    ("link", "bg", 4.5),
    ("code-fg", "code-bg", 4.5),
    ("link", "code-bg", 4.5),
    ("fg", "callout-bg", 4.5),
    ("link", "callout-bg", 4.5),
    ("border", "bg", 3.0),
    ("focus", "bg", 3.0),
]


@pytest.mark.parametrize(
    "theme,selector", [("light", ":root"), ("dark", "body.quarto-dark")]
)
def test_styles_meet_wcag_aa_contrast(theme, selector):
    tokens = _tokens((SITE_SRC / "styles.css").read_text(), selector)
    for fg, bg, minimum in PAIRS:
        ratio = contrast(tokens[fg], tokens[bg])
        assert ratio >= minimum, f"{theme}: {fg} on {bg} is {ratio:.2f}:1"
