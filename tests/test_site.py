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
from render_site import SITE_OUT, STAGE_DIRS, STAGE_EYEBROWS, render
from selfhost_assets import ASSETS, check, rewrite_html

from cwai import registry

REPO = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).parent / "fixtures"
SITE_SRC = REPO / "site"
SECRET_OUTPUT = "the-secret-answer-1234"


def _copy_site(dest: Path) -> Path:
    """A throwaway copy of the Quarto project, so rendering never dirties ``site/``.

    ``_quarto.yml`` runs ``../scripts/selfhost_assets.py`` after rendering, so the
    copy carries that script at the same relative place.
    """
    scripts = dest.parent / "scripts"
    scripts.mkdir(parents=True, exist_ok=True)
    shutil.copy2(REPO / "scripts" / "selfhost_assets.py", scripts)
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


@pytest.mark.slow
def test_a_raising_cell_renders_its_traceback_instead_of_failing_the_render(tmp_path):
    """Quarto ignores raises-exception; the cell option is what saves the render."""
    site = _copy_site(tmp_path / "site")
    out = tmp_path / "out"
    done = render(site, out, notebooks=[FIXTURES / "raises_exception.ipynb"])
    assert done.returncode == 0, done.stdout + done.stderr
    html = (out / "notebooks/90-stretch/raises_exception.html").read_text()
    assert "ValueError" in html
    assert "invalid literal" in html
    # The last cell prints a computed value that is not in its own source, so
    # this text can only come from the cell having run after the failing one.
    assert "sentinel 42" in html


def _raising_cell_problems(nb) -> list[str]:
    """Cells that carry only one half of the two-part contract."""
    problems = []
    for index, cell in enumerate(nb.cells):
        if cell.cell_type != "code":
            continue
        tagged = "raises-exception" in cell.metadata.get("tags", [])
        first = cell.source.splitlines()[0].strip() if cell.source else ""
        optioned = first == "#| error: true"
        if tagged != optioned:
            have = "the tag" if tagged else "the cell option"
            need = "#| error: true" if tagged else "the raises-exception tag"
            problems.append(f"cell {index} has {have} but not {need}")
    return problems


def test_every_raising_cell_carries_both_mechanisms():
    """One without the other breaks either CI or the published page."""
    found = []
    for path in sorted((REPO / "notebooks").rglob("*.ipynb")):
        if ".ipynb_checkpoints" in path.parts:
            continue
        found += [
            f"{path.relative_to(REPO)}: {p}"
            for p in _raising_cell_problems(nbformat.read(path, as_version=4))
        ]
    assert not found, "\n".join(found)


def test_the_contract_check_catches_a_half_marked_cell():
    nb = nbformat.read(FIXTURES / "raises_exception.ipynb", as_version=4)
    assert _raising_cell_problems(nb) == []
    nb.cells[2].source = "int('not a number')"
    assert len(_raising_cell_problems(nb)) == 1
    nb.cells[2].source = "#| error: true\nint('x')"
    nb.cells[2].metadata["tags"] = []
    assert len(_raising_cell_problems(nb)) == 1


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
    # The accent tint carries the "Choose this if ..." lines, the current
    # sidebar item and the table headers, all of which hold body-sized text.
    ("fg", "accent-soft", 4.5),
    ("link", "accent-soft", 4.5),
    # No ("accent-fg", "accent") pair, and no --cwai-callout-bg pairs: both
    # tokens were declared and measured while nothing painted them. The callout
    # body is --cwai-surface and no filled accent block carries text, so those
    # three entries measured colours the site never showed. The tokens are
    # gone; test_every_palette_token_is_painted_by_something keeps them gone.
    ("border", "bg", 3.0),
    ("border", "surface", 3.0),
    ("border", "accent-soft", 3.0),
    ("focus", "bg", 3.0),
    ("focus", "surface", 3.0),
    # 4.5, not 3: the accent stopped being a line colour only when the eyebrow
    # above every page title was drawn in it. That is small text, and the
    # threshold for small text is 4.5 whatever the colour is normally used for.
    ("accent", "bg", 4.5),
    ("accent", "surface", 4.5),
    # The top navbar is a dark surface in both themes, so nothing measured
    # against the page grounds says anything about the text on it.
    ("navbar-fg", "navbar-bg", 4.5),
    # Measured as text as well as as a mark: the active stage's underline is
    # non-text, but the same token colours a navbar link on hover and focus.
    ("navbar-accent", "navbar-bg", 4.5),
    ("navbar-focus", "navbar-bg", 3.0),
    # And the hairline that is the only thing separating the bar from the page
    # in the dark theme, where the two fills are 1.04:1 apart.
    ("border", "navbar-bg", 3.0),
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


def test_statement_never_sends_a_reader_to_a_regulator_it_names_no_duty_for():
    """EASS and ECNI are the route created by the 2018 Regulations.

    The statement once told a reader to escalate to them while citing no
    Regulations and naming no responsible body, which is a statement
    contradicting itself: it pointed at the enforcer of a duty it did not
    assert, on behalf of nobody it was willing to name. Either both are present
    or neither is.
    """
    # Whitespace-normalised: the citation is long enough to be wrapped across
    # two source lines, and was, which a plain substring search would miss.
    text = " ".join((SITE_SRC / "accessibility.qmd").read_text().split())
    names_a_regulator = "Equality Advisory" in text or "Equality Commission" in text
    cites_the_regulations = "Accessibility Regulations 2018" in text
    assert cites_the_regulations or not names_a_regulator, (
        "the statement names an enforcement body but cites no Regulations and "
        "so asserts no duty; name the responsible institution or drop the "
        "enforcement route"
    )


# Read the gate with .get() truthiness, never `"CWAI_PUBLISH_GATE" in
# os.environ`: checks.yml sets the variable to an empty string on every caller
# that is not publishing, so an `in` check would arm the gate on every pull
# request and fail it on a statement nobody is about to publish.
@pytest.mark.skipif(
    not os.environ.get("CWAI_PUBLISH_GATE"),
    reason="publication gate: only enforced by the site workflow",
)
def test_accessibility_statement_is_ready_to_publish():
    """Fails while the TODO remains, so a green site build means it is done.

    The TODO names two missing pieces, and the second is the reason this gate
    exists rather than a note in a tracker: with the institution unnamed, the
    statement cites no Regulations and offers no enforcement route, so a reader
    cannot find out who owes the duty. A placeholder that quietly drops a
    statutory citation is exactly what gets forgotten on a public repository.
    """
    text = (SITE_SRC / "accessibility.qmd").read_text()
    assert "TODO" not in text, (
        "name the responsible institution (which restores the Accessibility "
        "Regulations citation and the EASS/ECNI enforcement route) and add the "
        "contact route, then remove the TODO"
    )


def test_the_statement_names_a_measuring_script_and_it_is_committed():
    """The statement publishes numbers, so what produced them must be here.

    Those numbers were first taken with a script typed into a browser session,
    which left them unreproducible -- and this statement had already been
    returned three times for claiming more than had been measured. The script
    is committed; this keeps the citation and the file from parting company.
    """
    statement = (SITE_SRC / "accessibility.qmd").read_text()
    cited = re.findall(r"scripts/[\w./-]+\.py", statement)
    assert cited, "the statement cites no script for the numbers it publishes"
    for script in cited:
        assert (REPO / script).exists(), script


def test_the_audit_script_imports_without_a_browser_and_skips_quartos_libraries(
    tmp_path,
):
    """It is deliberately not a test dependency, so it must import without one.

    playwright is imported inside ``audit()``, not at the top of the module:
    the script needs a browser binary, which is why it is run by hand rather
    than in CI. ``pages_of`` is the part worth testing here -- Quarto writes
    HTML into site_libs/ that is nobody's page.
    """
    from audit_site_a11y import pages_of

    (tmp_path / "site_libs" / "bootstrap").mkdir(parents=True)
    (tmp_path / "site_libs" / "bootstrap" / "x.html").write_text("")
    (tmp_path / "notebooks").mkdir()
    for page in ("index.html", "notebooks/a.html"):
        (tmp_path / page).write_text("")
    assert [p.relative_to(tmp_path).as_posix() for p in pages_of(tmp_path)] == [
        "index.html",
        "notebooks/a.html",
    ]


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


def test_long_links_and_inline_code_wrap_for_reflow():
    """Both halves are needed, and the second was missing for a while.

    ``overflow-wrap: anywhere`` cannot break pre-formatted text, and Quarto's
    stylesheet sets ``white-space: pre`` on every ``code``. So inline code took
    no wrap at all until the second rule arrived, and a path written in the
    prose pushed a 320px page to 345px. Code blocks keep ``pre`` deliberately.
    """
    css = (SITE_SRC / "styles.css").read_text()
    assert "overflow-wrap: anywhere" in css
    assert "main :not(pre) > code" in css
    assert "white-space: pre-wrap" in css


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
    # Quarto's three navbar variables. They used to be one, $navbar-bg, set to
    # the page ground, because the navbar was not drawn. The bar is its own
    # surface now and Bootstrap computes the collapsed menu, the toggler icon
    # and the dropdown from these, so all three have to mirror a token.
    "navbar-bg": "navbar-bg",
    "navbar-fg": "navbar-fg",
    "navbar-hl": "navbar-accent",
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


# Every check around the generated stylesheet is a check on a *relation*: that
# it matches its source (build_tailwind.py --check), that it is loaded in the
# right order, that it names no colour of its own, that its utilities are
# prefixed. An empty site/_tailwind/input.css satisfies all of them -- nothing
# rebuilds to nothing, an empty file holds no hex literal, and the empty set
# collides with no Bootstrap class. Three of the four 320px reflow fixes and
# the WCAG 1.4.1 link underline live only in this generated file, so "it
# matches its source" is worth nothing unless something asserts the source
# still says anything. These are the declarations that would be silently lost.
LOAD_BEARING_CSS = [
    ("the route cards on the home page", ".cwai-routes"),
    ('each route card\'s "Choose this if ..." panel', ".route-when"),
    ("the current entry in the in-page contents list", "#TOC a.nav-link.active"),
    ("the accent rule under every section heading", "main.content h2::after"),
    # The shell. Without these the navbar is Bootstrap's default bar, which is
    # the page ground with no marking on it: the whole of "where am I in this
    # course" disappears and nothing fails anywhere else.
    ("the top navbar's own dark surface", "var(--cwai-navbar-bg)"),
    (
        "the stage you are in, marked on the navbar",
        "#quarto-header .navbar .navbar-nav .nav-link.active::after",
    ),
    ("the eyebrow above every page title", ".cwai-eyebrow {"),
    # The right rail is a stack of panels rather than a bare table of
    # contents, which is what lets a progress panel join it later as an
    # element rather than as a rewrite.
    ("the right rail's panel stack", "#quarto-margin-sidebar > * {"),
    ("the stage cards on the home page", ".cwai-stages {"),
    ("a stage page's listing of its notebooks", "main.content .quarto-post {"),
    # WCAG 1.4.10. Each was found by measuring a 320px window, not by reading
    # the CSS, and each is the difference between a reachable search button and
    # one carried off the right-hand edge.
    ("reflow: the content column may shrink", "main.content {\n  min-width: 0;\n}"),
    (
        "reflow: the navbar brand may shrink and wrap",
        "#quarto-header .navbar .navbar-brand {\n  min-width: 0;\n}",
    ),
    # WCAG 1.4.1: body links carry an underline, so colour is not the only cue.
    ("body links are underlined", "text-underline-offset: 0.15em;"),
]

# The accent is the site's one line colour, used by the title rule, the heading
# rules, the route bullets, the current sidebar item and the focus ring's
# neighbours. A build that painted it once or twice has lost most of the design
# layer; the floor is well under the real count (9 at the time of writing) so
# that ordinary edits do not trip it.
MINIMUM_ACCENT_USES = 5


def test_generated_stylesheet_still_contains_the_rules_that_carry_the_site():
    css = TAILWIND_OUT.read_text()
    missing = [what for what, needle in LOAD_BEARING_CSS if needle not in css]
    assert not missing, f"{TAILWIND_OUT.name} no longer styles: {missing}"
    uses = css.count("var(--cwai-accent)")
    assert uses >= MINIMUM_ACCENT_USES, (
        f"{TAILWIND_OUT.name} paints the accent only {uses} time(s); "
        "the design layer has mostly vanished"
    )


@pytest.mark.parametrize(
    "theme,selector", [("light", ":root"), ("dark", "body.quarto-dark")]
)
def test_every_palette_token_is_painted_by_something(theme, selector):
    """A token nothing paints is a colour the contrast test measures in vain.

    ``--cwai-callout-bg`` and ``--cwai-accent-fg`` were both declared, both
    measured by three entries in PAIRS, and referred to by nothing: the callout
    body is painted ``--cwai-surface`` and no filled accent block carries text.
    A conformance statement should not rest partly on tests of dead tokens.
    """
    painted = (SITE_SRC / "styles.css").read_text() + TAILWIND_OUT.read_text()
    for name in _tokens((SITE_SRC / "styles.css").read_text(), selector):
        assert f"var(--cwai-{name})" in painted, (
            f"{theme}: --cwai-{name} is declared and measured but nothing uses "
            "it; paint it or delete it, and its PAIRS entries with it"
        )


def test_tailwind_scans_the_committed_pages_and_not_the_generated_ones():
    """``./site/*.qmd`` also matched site/data.qmd, which is generated.

    scripts/render_site.py writes that page into the Quarto project on every
    local render and it is gitignored, so CI scanned three top-level pages from
    a clean checkout while a developer who had rendered scanned four, and
    ``--check`` compared a build of one input set against a build of another.
    """
    content = re.search(
        r"content:\s*\[(.*?)\]", TAILWIND_CONFIG.read_text(), re.S
    ).group(1)
    patterns = re.findall(r'"([^"]+)"', content)
    assert patterns
    scanned = {
        path.resolve()
        for pattern in patterns
        for path in REPO.glob(pattern.removeprefix("./"))
    }
    authored = {
        path.resolve()
        for path in [*SITE_SRC.glob("*.qmd"), *SITE_SRC.glob("_stages/*.qmd")]
        if path.name != "data.qmd"
    }
    assert scanned == authored, {
        "scanned but not authored": sorted(str(p) for p in scanned - authored),
        "authored but not scanned": sorted(str(p) for p in authored - scanned),
    }


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


# Everything a browser fetches to show a page: scripts, stylesheets, images,
# frames, media. Plain ``<a href>`` links are navigation, not a fetch, so a link
# to GitHub is fine; ``<link>`` is not (stylesheets, preloads, fonts).
_FETCHING_TAG = re.compile(
    r"<(?:script|link|img|iframe|source|video|audio|embed|object|track)\b[^>]*>",
    re.IGNORECASE,
)
_FETCHING_ATTR = re.compile(r'\b(src|href|srcset|imagesrcset|data|poster)="([^"]*)"')
_CSS_FETCH = re.compile(r"""(?:@import\s*|url\()\s*["']?\s*((?:https?:)?//[^"')\s]+)""")
_THIRD_PARTY = re.compile(r"^(?:https?:)?//", re.IGNORECASE)


def _candidate_urls(attribute: str, value: str) -> list[str]:
    """The URLs one attribute asks the browser to fetch.

    ``srcset`` (and ``imagesrcset`` on a preload) holds a comma-separated list
    of "url descriptor" pairs, so the value as a whole is not a URL. Matched
    whole against a scheme, ``srcset="a.png 1x, https://cdn/x.png 2x"`` begins
    with a relative path and the CDN candidate goes unseen.
    """
    if not attribute.lower().endswith("srcset"):
        return [value.strip()]
    return [parts[0] for candidate in value.split(",") if (parts := candidate.split())]


def third_party_fetches(page: Path) -> set[str]:
    """Absolute or protocol-relative URLs a page or stylesheet makes a browser fetch."""
    text = page.read_text(encoding="utf-8")
    found: set[str] = set()
    if page.suffix == ".html":
        for tag in _FETCHING_TAG.findall(text):
            for attribute, value in _FETCHING_ATTR.findall(tag):
                found |= {
                    url
                    for url in _candidate_urls(attribute, value)
                    if _THIRD_PARTY.match(url)
                }
    # Inline <style> blocks and style="" attributes, and whole .css files.
    found |= set(_CSS_FETCH.findall(text))
    return found


def test_pages_fetch_nothing_from_a_third_party(site):
    """No page, and no stylesheet it loads, may fetch from another origin.

    This site is the degraded-mode path for a student whose Codespace will not
    connect, read from Chengdu on a poor connection, so a third-party request
    is a blocking dependency on a host that may never answer. Quarto injects
    jquery and requirejs from cdn.jsdelivr.net into notebook pages; those are
    rewritten to site/vendor/ by scripts/selfhost_assets.py. Anything new here,
    a web font, a CDN script, or Tailwind's browser build (cdn.tailwindcss.com),
    must be vendored, not allow-listed.
    """
    assert list(site.rglob("*.html")), "nothing rendered"
    offenders = {
        str(path.relative_to(site)): urls
        for path in sorted([*site.rglob("*.html"), *site.rglob("*.css")])
        if (urls := third_party_fetches(path))
    }
    assert not offenders, offenders


def _every_key(node) -> "list[str]":
    """Every mapping key anywhere in a parsed YAML document."""
    if isinstance(node, dict):
        return [k for key, value in node.items() for k in (key, *_every_key(value))]
    if isinstance(node, list):
        return [k for item in node for k in _every_key(item)]
    return []


def test_the_config_turns_on_no_third_party_widget(site):
    """The two switches that would defeat the scan above without tripping it.

    ``test_pages_fetch_nothing_from_a_third_party`` scans .html and .css by
    matching fetching *tags* and reading their URL attributes. Quarto does not
    give giscus a ``<script src=>``: with ``comments: giscus:`` set it writes an
    inline script into the page body that assigns ``script.src =
    "https://giscus.app/client.js"`` and appends the element. The URL is in a
    script body, not in a tag, so that guard returns an empty set while every
    page fetches giscus.app. Verified by rendering a probe site with the key
    set. An Algolia search backend hides the same way, behind the search box.

    Extending the scan to .js is the wrong answer: Quarto's bundled JavaScript
    names fifteen hosts, nearly all of them licence banners and documentation
    links, and sorting those from a real fetch needs exactly the allow-list the
    guard's own docstring refuses. So guard the configuration instead -- there
    is nothing to sift, and nothing to keep up to date.
    """
    config = yaml.safe_load((SITE_SRC / "_quarto.yml").read_text())
    keys = _every_key(config)
    assert "comments" not in keys, (
        "a comments provider (giscus, utterances, hypothesis) fetches from a "
        "third party at run time; vendor it or leave it off"
    )
    assert "algolia" not in keys, (
        "an Algolia backend sends every keystroke to algolia.net; Quarto's "
        "built-in search is served from this site"
    )
    # Non-vacuous: search is on, so this is a guard on how it is configured and
    # not an artefact of there being no search at all. It lives on the navbar
    # now; there is no sidebar to put it in.
    assert config["website"]["navbar"]["search"] is True
    # And the rendered pages really do carry a search box built from this site.
    assert "quarto-search" in (site / "index.html").read_text()


def test_notebook_pages_load_the_vendored_scripts_from_this_site(site):
    page = site / "notebooks" / "01-foundations" / "00-smoke.html"
    html = page.read_text(encoding="utf-8")
    for asset in ASSETS:
        assert f'src="../../vendor/{asset.filename}"' in html, asset.filename
        assert (site / "vendor" / asset.filename).read_bytes() == (
            VENDOR_SRC / asset.filename
        ).read_bytes()
    # jQuery before the inline define('jquery') shim, RequireJS before the shim.
    assert html.index("jquery-3.5.1.min.js") < html.index("define('jquery'")
    assert html.index("require-2.3.6.min.js") < html.index("define('jquery'")
    assert "integrity=" not in re.search(r"<script[^>]*vendor/[^>]*>", html).group(0)


def test_the_third_party_scan_catches_what_it_is_meant_to_catch(tmp_path):
    """The guard above is only worth having if it can fail."""
    page = tmp_path / "p.html"
    css = tmp_path / "s.css"
    for markup in (
        '<script src="https://cdn.jsdelivr.net/npm/jquery@3.5.1/dist/jquery.min.js"></script>',
        '<link rel="stylesheet" href="//fonts.googleapis.com/css2?family=Inter">',
        '<img src="http://example.com/x.png">',
        "<style>@import url('https://fonts.googleapis.com/css2');</style>",
        # A srcset is a comma-separated list of "url descriptor" pairs: the
        # third party is the second candidate, not the value as a whole.
        '<img src="a.png" srcset="a.png 1x, https://cdn.example.com/x.png 2x">',
        '<link rel="preload" as="image" '
        'imagesrcset="a.png 1x, //cdn.example.com/x.png 2x">',
    ):
        page.write_text(f"<html>{markup}</html>")
        assert third_party_fetches(page), markup
    # ... and the descriptor is not reported as part of the URL.
    page.write_text('<img srcset="a.png 1x, https://cdn.example.com/x.png 2x">')
    assert third_party_fetches(page) == {"https://cdn.example.com/x.png"}
    css.write_text('@import"https://fonts.googleapis.com/css2?family=Inter";')
    assert third_party_fetches(css)
    page.write_text(
        '<a href="https://github.com/x">x</a><script src="../vendor/a.js"></script>'
        '<link href="site_libs/a.css" rel="stylesheet">'
        '<img src="a.png" srcset="a.png 1x, a@2x.png 2x">'
    )
    assert not third_party_fetches(page)


# ---------------------------------------------------------------------------
# Vendored scripts (scripts/selfhost_assets.py)
# ---------------------------------------------------------------------------

VENDOR_SRC = SITE_SRC / "vendor"


def test_vendored_scripts_are_as_pinned_and_attributed():
    assert check(VENDOR_SRC) == []


def test_vendored_check_fails_on_a_tampered_file(tmp_path):
    shutil.copytree(VENDOR_SRC, tmp_path / "vendor")
    victim = tmp_path / "vendor" / ASSETS[0].filename
    victim.write_text(victim.read_text() + "\n// edited")
    assert any("SHA-256" in problem for problem in check(tmp_path / "vendor"))


def test_rewrite_is_idempotent_and_leaves_other_scripts_alone(tmp_path):
    (tmp_path / "vendor").mkdir()
    for asset in ASSETS:
        (tmp_path / "vendor" / asset.filename).write_text("x")
    page = tmp_path / "a" / "b.html"
    page.parent.mkdir()
    other = '<script src="../site_libs/x.js" integrity="sha384-keep"></script>'
    page.write_text(
        f'<script src="{ASSETS[0].cdn_url}" integrity="sha384-abc" '
        f'crossorigin="anonymous" data-relocate-top="true"></script>{other}'
    )
    once = rewrite_html(page.read_text(), page, tmp_path)
    assert once == (
        '<script src="../vendor/jquery-3.5.1.min.js" data-relocate-top="true">'
        f"</script>{other}"
    )
    assert rewrite_html(once, page, tmp_path) == once


def test_quarto_project_runs_the_rewrite_after_every_render():
    config = yaml.safe_load((SITE_SRC / "_quarto.yml").read_text())
    assert config["project"]["post-render"] == "../scripts/selfhost_assets.py"
    # Quarto only publishes files a page references, unless told.
    assert "/vendor/*" in config["project"]["resources"]
    assert (REPO / "scripts" / "selfhost_assets.py").exists()


def test_checks_workflow_verifies_the_vendored_scripts():
    workflow = (REPO / ".github/workflows/checks.yml").read_text()
    assert "scripts/selfhost_assets.py --check" in workflow


def test_checks_workflow_verifies_the_generated_stylesheet():
    """A committed build artefact whose freshness check went missing is a trap."""
    workflow = (REPO / ".github/workflows/checks.yml").read_text()
    assert "scripts/build_tailwind.py --check" in workflow


def test_every_stage_directory_has_a_navbar_item():
    """STAGE_DIRS and the navbar are two lists that must stay in step.

    This guarded the sidebar until the sidebar was removed. The relation it
    protects is unchanged and is now the only way into a stage: a stage folder
    that no navbar item points at is a stage no reader can reach, and
    scripts/render_site.py would still generate its landing page, so nothing
    else on the site would look wrong.
    """
    config = yaml.safe_load((SITE_SRC / "_quarto.yml").read_text())
    navbar = config["website"]["navbar"]
    hrefs = {
        entry.get("href")
        for side in ("left", "right")
        for entry in navbar.get(side, [])
        if isinstance(entry, dict)
    }
    for stage in STAGE_DIRS:
        assert f"notebooks/{stage}/index.qmd" in hrefs, stage
    # And the other direction: an item pointing at a folder STAGE_DIRS does
    # not know about would be a 404, because nothing would generate it.
    stage_hrefs = {h for h in hrefs if h and h.startswith("notebooks/")}
    assert stage_hrefs == {f"notebooks/{stage}/index.qmd" for stage in STAGE_DIRS}


def test_every_stage_has_an_eyebrow_label():
    """The eyebrow is how a notebook page says which stage it belongs to.

    A stage missing from STAGE_EYEBROWS raises at render time, which is the
    right failure but a late one; a stage left in STAGE_EYEBROWS after its
    folder went would never be noticed at all.
    """
    assert set(STAGE_EYEBROWS) == set(STAGE_DIRS)
    assert all(STAGE_EYEBROWS[stage].strip() for stage in STAGE_DIRS)


def test_a_notebook_page_names_the_stage_it_is_in(site):
    """The plain-text half of the navbar's "you are here".

    The marking on the navbar itself is added by a script, so this is the part
    a reader gets with JavaScript off. It is written by Quarto's per-folder
    metadata, which means a notebook added to the folder later inherits it
    without anybody remembering to.
    """
    html = (site / "notebooks/01-foundations/00-smoke.html").read_text()
    assert '<div class="cwai-eyebrow">Stage 1</div>' in html
    # Before the <h1>, not after it: a screen reader should hear the label
    # that qualifies the title before the title.
    assert html.index('class="cwai-eyebrow"') < html.index('<h1 class="title"')


def test_a_stage_page_links_to_the_notebooks_in_that_stage(site):
    """Removing the sidebar removed the only list of a stage's notebooks.

    The smoke test was reachable from the sidebar and from nowhere else. Each
    stage landing page now carries a Quarto listing of its own folder, added
    by scripts/render_site.py to the stages that have notebooks -- and if that
    stops happening, a published notebook is simply unreachable while every
    other test on this site stays green.
    """
    html = (site / "notebooks/01-foundations/index.html").read_text()
    assert "Smoke test" in html
    assert re.search(r'href="[^"]*00-smoke\.html"', html)
    # A stage with no notebooks says so, rather than showing an empty listing.
    empty = (site / "notebooks/00-warmup/index.html").read_text()
    assert "No notebooks here yet" in empty
    assert "quarto-listing" not in empty


def test_the_navbar_marking_script_is_inline_and_optional():
    """It is an enhancement, and it must not become a request.

    An external script would be one more thing to fetch before the chrome is
    right, on a connection where that is the whole problem; and the page has
    to make sense without it, which is why the eyebrow exists.
    """
    include = SITE_SRC / "_includes" / "navbar-active.html"
    config = yaml.safe_load((SITE_SRC / "_quarto.yml").read_text())
    assert config["format"]["html"]["include-after-body"] == [
        "_includes/navbar-active.html"
    ]
    assert not re.search(r"<script[^>]*\bsrc=", include.read_text())
