import os
import re
import shutil
from html import escape as html_escape
from pathlib import Path

import nbformat
import pytest
import yaml
from build_student_notebooks import (
    EXERCISE_TAG,
    SOLUTION_MARKER,
    SOLUTION_TAG,
    build,
    wrap_solution,
)
from render_site import SITE_OUT, STAGE_DIRS, render

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
        # Attribution is read from the registry, not retyped.
        assert html_escape(info.attribution, quote=False) in html


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
#
# Two grounds, not one: --cwai-bg is the page and --cwai-surface is what the
# sidebar, the route cards and the reference cards sit on, so every text token
# is checked against both. Anything that only ever appears on one of them would
# still be an untested pair the first time somebody moved it.
PAIRS = [
    ("fg", "bg", 4.5),
    ("fg", "surface", 4.5),
    ("muted", "bg", 4.5),
    ("muted", "surface", 4.5),
    ("link", "bg", 4.5),
    ("link", "surface", 4.5),
    ("code-fg", "code-bg", 4.5),
    ("link", "code-bg", 4.5),
    ("fg", "callout-bg", 4.5),
    ("link", "callout-bg", 4.5),
    # The accent tint carries the "Choose this if ..." lines, the current
    # sidebar item and the table headers, all of which hold body-sized text.
    ("fg", "accent-soft", 4.5),
    ("link", "accent-soft", 4.5),
    # Text on a filled accent block.
    ("accent-fg", "accent", 4.5),
    ("border", "bg", 3.0),
    ("border", "surface", 3.0),
    ("border", "accent-soft", 3.0),
    ("focus", "bg", 3.0),
    ("focus", "surface", 3.0),
    ("accent", "bg", 3.0),
    ("accent", "surface", 3.0),
]


@pytest.mark.parametrize(
    "theme,selector", [("light", ":root"), ("dark", "body.quarto-dark")]
)
def test_styles_meet_wcag_aa_contrast(theme, selector):
    tokens = _tokens((SITE_SRC / "styles.css").read_text(), selector)
    for fg, bg, minimum in PAIRS:
        ratio = contrast(tokens[fg], tokens[bg])
        assert ratio >= minimum, f"{theme}: {fg} on {bg} is {ratio:.2f}:1"


def test_accessibility_statement_makes_no_response_time_promise():
    assert "working days" not in (SITE_SRC / "accessibility.qmd").read_text()


# Read the gate with .get() truthiness, never `"CWAI_PUBLISH_GATE" in
# os.environ`: checks.yml sets the variable to an empty string on every caller
# that is not publishing, so an `in` check would arm the gate on every pull
# request and fail it on a statement nobody is about to publish.
@pytest.mark.skipif(
    not os.environ.get("CWAI_PUBLISH_GATE"),
    reason="publication gate: only enforced by the site workflow",
)
def test_accessibility_statement_is_ready_to_publish():
    """Fails while the contact TODO remains, so a green site build means it is done."""
    text = (SITE_SRC / "accessibility.qmd").read_text()
    assert "TODO" not in text, (
        "add the accessibility contact route, then remove the TODO"
    )


def test_headings_never_skip_a_level(site):
    for page in site.rglob("*.html"):
        if "site_libs" in page.parts:
            continue
        html = page.read_text()
        # Without this, find() returns -1 on a page with no <main>, the slice
        # examines one character, and the page passes having been unchecked.
        assert "<main" in html, page
        levels = [
            int(n) for n in re.findall(r"<h([1-6])[ >]", html[html.find("<main") :])
        ]
        for before, after in zip(levels, levels[1:], strict=False):
            assert after <= before + 1, f"{page}: h{before} then h{after}"


def test_long_links_wrap_for_reflow():
    css = (SITE_SRC / "styles.css").read_text()
    assert "overflow-wrap: anywhere" in css


# Bootstrap is themed by the SCSS files, the course's own rules by the CSS
# tokens, and the contrast test above reads only the CSS. So a token changed in
# one place and forgotten in the other leaves that test green while Bootstrap
# renders the old colour, under a published conformance statement. Every SCSS
# variable must therefore name the token it mirrors.
SCSS_TO_TOKEN = {
    "body-bg": "bg",
    "body-color": "fg",
    "link-color": "link",
    "link-hover-color": "link",
    "code-color": "code-fg",
    "code-bg": "code-bg",
    "pre-color": "code-fg",
    "navbar-bg": "bg",
    "border-color": "border",
    "card-bg": "surface",
    "input-bg": "surface",
    "input-color": "fg",
    "input-border-color": "border",
}


@pytest.mark.parametrize(
    ("scss_name", "selector"),
    [("theme-light.scss", ":root"), ("theme-dark.scss", "body.quarto-dark")],
)
def test_scss_theme_values_match_the_css_tokens(scss_name, selector):
    tokens = _tokens((SITE_SRC / "styles.css").read_text(), selector)
    scss = dict(
        re.findall(
            r"\$([\w-]+):\s*(#[0-9a-fA-F]{6})", (SITE_SRC / scss_name).read_text()
        )
    )
    assert scss, scss_name
    for name, value in scss.items():
        assert name in SCSS_TO_TOKEN, (
            f"{scss_name} sets ${name}, which maps to no --cwai-* token. "
            "Add it to SCSS_TO_TOKEN, or drop it from the theme."
        )
        token = SCSS_TO_TOKEN[name]
        assert value.lower() == tokens[token].lower(), (
            f"{scss_name}: ${name} is {value} but --cwai-{token} is "
            f"{tokens[token]}; the contrast test only reads the CSS."
        )


# ---------------------------------------------------------------------------
# The Tailwind design layer. site/tailwind.css is generated from
# site/_tailwind/ and committed; scripts/build_tailwind.py --check rebuilds it
# in CI and fails if the two have diverged. The tests below guard the things
# that check cannot see: that the stylesheet is wired up, that the palette has
# exactly one home, that nothing reaches a third party, and that Tailwind's
# utilities cannot collide with the Bootstrap classes Quarto's chrome is
# built from.
# ---------------------------------------------------------------------------

TAILWIND_SRC = SITE_SRC / "_tailwind" / "input.css"
TAILWIND_CONFIG = SITE_SRC / "_tailwind" / "tailwind.config.js"
TAILWIND_OUT = SITE_SRC / "tailwind.css"


def test_generated_stylesheet_is_committed_and_loaded_after_the_tokens():
    assert TAILWIND_OUT.exists(), "run scripts/build_tailwind.py"
    assert "GENERATED FILE" in TAILWIND_OUT.read_text()
    css = yaml.safe_load((SITE_SRC / "_quarto.yml").read_text())["format"]["html"][
        "css"
    ]
    # styles.css declares the --cwai-* tokens the design layer refers to, and
    # the reflow safety net; tailwind.css must come after it so the design
    # layer wins on equal specificity.
    assert css == ["styles.css", "tailwind.css"], css


def test_design_layer_holds_no_colour_of_its_own():
    """Every colour must be a --cwai-* token, because only those are measured.

    A hex value written straight into the design layer is a colour the contrast
    test above never sees, sitting under a published conformance statement.
    """
    literals = re.findall(r"#[0-9a-fA-F]{3,8}\b", TAILWIND_SRC.read_text())
    assert not literals, f"{TAILWIND_SRC.name} names colours directly: {literals}"


def test_tailwind_utilities_are_prefixed_so_they_cannot_clobber_bootstrap():
    """Unprefixed, Tailwind emits a utility for any scanned word that names one.

    Several of those words are ordinary English that this site's prose uses,
    and several are also Bootstrap class names that Quarto's chrome depends on.
    The first build of this site emitted `.collapse { visibility: collapse }`,
    which beat Bootstrap's and hid the sidebar on every page.
    """
    assert re.search(r'prefix:\s*"cw-"', TAILWIND_CONFIG.read_text())
    collidable = {
        "collapse",
        "container",
        "table",
        "fixed",
        "static",
        "sticky",
        "absolute",
        "relative",
        "visible",
        "invisible",
        "hidden",
        "block",
        "inline",
        "flex",
        "grid",
        "border",
        "shadow",
        "rounded",
        "active",
        "disabled",
        "contents",
        "isolate",
    }
    emitted = set(
        re.findall(r"^\.([a-z][\w-]*)\s*[,{]", TAILWIND_OUT.read_text(), re.M)
    )
    assert not (emitted & collidable), emitted & collidable


# The two Quarto injects into every page rendered by its Jupyter engine. They
# are not ours and removing them is a Quarto question, not a stylesheet one,
# but they are listed rather than ignored: this site has to open on a poor
# connection from Chengdu, so a new third-party request should fail a build
# and be a decision somebody takes on purpose.
ALLOWED_THIRD_PARTY = {
    "https://cdn.jsdelivr.net/npm/jquery@3.5.1/dist/jquery.min.js",
    "https://cdn.jsdelivr.net/npm/requirejs@2.3.6/require.min.js",
}


def test_pages_fetch_no_new_third_party_resource(site):
    """Nothing the browser must wait for may come from another origin.

    In particular the Tailwind stylesheet is built into site/tailwind.css and
    served from this site; cdn.tailwindcss.com is a browser-side JIT build and
    would be a blocking request to a third party on every page load.
    """
    found: set[str] = set()
    for page in site.rglob("*.html"):
        html = page.read_text()
        found |= set(
            re.findall(r'<(?:script|link)[^>]+(?:src|href)="(https?://[^"]+)"', html)
        )
    assert not (found - ALLOWED_THIRD_PARTY), found - ALLOWED_THIRD_PARTY
    assert "cdn.tailwindcss.com" not in "".join(sorted(found))


def test_checks_workflow_verifies_the_generated_stylesheet():
    """A committed build artefact whose freshness check went missing is a trap."""
    workflow = (REPO / ".github/workflows/checks.yml").read_text()
    assert "scripts/build_tailwind.py --check" in workflow


def test_every_stage_directory_has_a_sidebar_section():
    """STAGE_DIRS and the Quarto sidebar are two lists that must stay in step."""
    config = yaml.safe_load((SITE_SRC / "_quarto.yml").read_text())
    hrefs = {
        entry.get("href")
        for entry in config["website"]["sidebar"]["contents"]
        if isinstance(entry, dict)
    }
    for stage in STAGE_DIRS:
        assert f"notebooks/{stage}/index.qmd" in hrefs, stage
