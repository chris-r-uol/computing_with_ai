import json
from pathlib import Path

import pytest
import render_site
import yaml
from check_prose import (
    EXEMPT,
    JARGON,
    MAX_SENTENCE_WORDS,
    PLAIN_ALTERNATIVES,
    check_hints,
    check_module,
    check_notebook,
    check_qmd,
    check_text,
    glossary_terms,
    main,
    sentences,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "checks.yml"


def _gated_paths() -> list[str]:
    """The paths CI gives the gate, read from the workflow rather than retyped.

    Taking them from CI is what keeps the two in step. A path added to the
    workflow is checked here as well. A path dropped from the workflow stops
    being checked in both places at once.
    """
    steps = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))["jobs"]["checks"][
        "steps"
    ]
    commands = [s["run"] for s in steps if "check_prose.py" in s.get("run", "")]
    assert len(commands) == 1, "the workflow should run the prose gate exactly once"
    paths = commands[0].split("check_prose.py", 1)[1].split()
    assert paths, "the workflow runs the gate with no paths, so it checks nothing"
    return paths


# --- sentence splitting ---


def test_sentences_splits_on_terminators():
    assert sentences("One idea. Then another! A third?") == [
        "One idea.",
        "Then another!",
        "A third?",
    ]


def test_sentences_ignores_fenced_code():
    text = "Read it.\n\n```python\nx = 1; y = 2; z = 3\n```\n\nThen run it."
    assert sentences(text) == ["Read it.", "Then run it."]


def test_sentences_ignores_inline_code_but_keeps_the_sentence():
    assert len(sentences("Call `df.groupby('a').size()` on it.")) == 1


def test_sentences_does_not_split_on_a_decimal_or_an_abbreviation():
    assert len(sentences("The rate is 31.75 per cent.")) == 1
    assert len(sentences("Use e.g. a filter.")) == 1


def test_sentences_ignores_markdown_tables_and_urls():
    assert sentences(
        "| a | b |\n|---|---|\n| 1 | 2 |\n\nSee https://example.com/a.b.c now."
    ) == ["See https://example.com/a.b.c now."]


def test_sentences_splits_after_a_plain_no():
    """Merging two sentences inflates the count, which can manufacture a finding."""
    assert len(sentences("The answer is no. Then we move on.")) == 2


def test_sentences_does_not_split_a_number_reference():
    """'no.' and 'fig.' guard only when a number follows.

    That is when they are abbreviating something.
    """
    assert len(sentences("See no. 5 for the answer.")) == 1
    assert len(sentences("Read fig. 3 before you start.")) == 1


def test_sentences_splits_before_the_house_em_dash():
    """This repository writes an em dash as `--`, so prose really does start with it."""
    assert len(sentences("Use it. -- then stop.")) == 2


def test_sentences_splits_before_a_curly_quote_or_a_real_dash():
    assert len(sentences("He said it. “Then stop.”")) == 2
    assert len(sentences("Use it. — then stop.")) == 2
    assert len(sentences("Use it. ‘then stop’.")) == 2


# --- the rules ---


def test_a_long_sentence_is_flagged_with_its_length():
    text = " ".join(["word"] * 30) + "."
    findings = check_text(text, "x.md")
    assert [f.rule for f in findings] == ["sentence-too-long"]
    assert "30" in findings[0].detail


def test_a_sentence_at_the_limit_passes():
    assert check_text(" ".join(["word"] * MAX_SENTENCE_WORDS) + ".", "x.md") == []


def test_a_high_mean_sentence_length_is_flagged_even_when_no_sentence_is_long():
    text = " ".join([" ".join(["word"] * 24) + "."] * 5)
    rules = {f.rule for f in check_text(text, "x.md")}
    assert rules == {"mean-sentence-too-long"}


def test_a_discouraged_phrase_is_flagged_with_its_replacement():
    findings = check_text("Bear in mind that we utilise it.", "x.md")
    rules = {f.rule for f in findings}
    assert rules == {"discouraged-phrase"}
    details = " ".join(f.detail for f in findings)
    assert "remember" in details and "use" in details


def test_a_discouraged_phrase_is_matched_case_insensitively_on_word_boundaries():
    assert check_text("Utilise it.", "x.md")
    assert (
        check_text("The autobus is late.", "x.md") == []
    )  # 'bus' must not match inside a word


def test_findings_carry_the_line_number_they_were_found_on():
    findings = check_text("Fine.\n\nWe utilise it.", "x.md")
    assert findings[0].line == 3


def test_every_discouraged_phrase_has_a_plain_replacement():
    """A finding that cannot say what to write instead is a finding nobody acts on."""
    assert PLAIN_ALTERNATIVES
    for phrase, plain in PLAIN_ALTERNATIVES.items():
        assert phrase == phrase.lower(), phrase
        assert plain and plain != phrase, phrase


# --- the jargon rule ---


def test_jargon_absent_from_the_glossary_is_flagged():
    findings = check_text("The slice has no denominator.", "x.md", glossary=frozenset())
    assert {f.rule for f in findings} == {"jargon-not-in-glossary"}
    terms = " ".join(f.detail for f in findings)
    assert "slice" in terms and "denominator" in terms


def test_jargon_present_in_the_glossary_is_not_flagged():
    glossary = frozenset({"slice", "denominator"})
    assert check_text("The slice has no denominator.", "x.md", glossary=glossary) == []


def test_the_jargon_check_is_case_insensitive_and_matches_plurals():
    assert check_text("KSI counts are low.", "x.md", glossary=frozenset())
    assert check_text("ksi counts are low.", "x.md", glossary=frozenset())
    assert check_text("Casualties are people.", "x.md", glossary=frozenset())


def test_jargon_inside_code_is_not_flagged():
    glossary = frozenset()
    assert check_text("Run `df.slice()` now.", "x.md", glossary=glossary) == []
    fenced = "Run it.\n\n```python\nslice = df[df.severity == 1]\n```\n"
    assert check_text(fenced, "x.md", glossary=glossary) == []


def test_every_jargon_term_is_in_the_glossary():
    """The gate demands these terms be defined, so the glossary must define them."""
    missing = sorted(term for term in JARGON if term.lower() not in glossary_terms())
    assert missing == []


def test_glossary_terms_reads_the_english_column_and_not_the_header():
    assert "dataframe" in glossary_terms()
    assert "english" not in glossary_terms()


def test_glossary_terms_reads_both_forms_of_a_term_written_with_a_slash(tmp_path):
    """One row can define two forms of one word, as "axis / axes" does.

    The plural rule adds an "s", so it turns "axis" into "axises" and never
    finds "axes". Writing the irregular form in the row is how the gate learns
    it, and it keeps the glossary one row per idea rather than two.
    """
    path = tmp_path / "glossary.qmd"
    path.write_text(
        "| English | 中文 | Meaning |\n|---|---|---|\n"
        "| axis / axes | a | One edge of a chart. |\n",
        encoding="utf-8",
    )
    assert glossary_terms(path) == frozenset({"axis", "axes"})


# --- the file readers and the exemptions ---


def _notebook(cells):
    return {
        "cells": cells,
        "metadata": {},
        "nbformat": 4,
        "nbformat_minor": 5,
    }


def _cell(kind, text):
    cell = {"cell_type": kind, "metadata": {}, "source": text}
    if kind == "code":
        cell |= {"outputs": [], "execution_count": None}
    return cell


def test_check_notebook_reads_markdown_cells_and_not_code_cells(tmp_path):
    """A code cell's comments are for the author, not the student."""
    long_sentence = " ".join(["word"] * 30) + "."
    path = tmp_path / "lesson.ipynb"
    path.write_text(
        json.dumps(
            _notebook(
                [
                    _cell("code", f"# {long_sentence}\nx = 1\n"),
                    _cell("markdown", f"We utilise it. {long_sentence}"),
                ]
            )
        ),
        encoding="utf-8",
    )
    rules = sorted(f.rule for f in check_notebook(path))
    assert rules == ["discouraged-phrase", "sentence-too-long"]


def test_check_notebook_names_the_cell_a_finding_came_from(tmp_path):
    path = tmp_path / "lesson.ipynb"
    path.write_text(
        json.dumps(
            _notebook([_cell("markdown", "Fine."), _cell("markdown", "Utilise it.")])
        ),
        encoding="utf-8",
    )
    findings = check_notebook(path)
    assert len(findings) == 1
    assert "cell 2" in findings[0].source


def test_check_hints_flags_a_hint_string(tmp_path):
    """Hint wording is student-facing prose and gets the same gate."""
    path = tmp_path / "01-foundations.yml"
    path.write_text(
        "first-look-row-count:\n  nudge: Bear in mind that the shape is a pair.\n",
        encoding="utf-8",
    )
    findings = check_hints(path)
    assert [f.rule for f in findings] == ["discouraged-phrase"]
    assert findings[0].line == 2


def test_check_hints_does_not_flag_an_exercise_id(tmp_path):
    """An id is a key, not prose: it is never read aloud to a student."""
    path = tmp_path / "01-foundations.yml"
    path.write_text(
        "utilise-the-rate:\n  nudge: Read the first line.\n", encoding="utf-8"
    )
    assert check_hints(path) == []


def test_check_qmd_reads_the_front_matter_and_the_body(tmp_path):
    path = tmp_path / "page.qmd"
    path.write_text(
        '---\ntitle: "A page"\nsubtitle: "Bear in mind that this is a page."\n---\n\n'
        "We utilise it.\n",
        encoding="utf-8",
    )
    findings = check_qmd(path)
    assert [f.rule for f in findings] == ["discouraged-phrase", "discouraged-phrase"]
    assert [f.line for f in findings] == [3, 6]


def test_check_module_reads_message_strings_and_not_docstrings(tmp_path):
    """A docstring is read by the next author; a message string is read by a student."""
    path = tmp_path / "mod.py"
    path.write_text(
        '"""Bear in mind that this module is for authors."""\n\n'
        'MESSAGE = "We utilise it."\n',
        encoding="utf-8",
    )
    findings = check_module(path)
    assert [f.rule for f in findings] == ["discouraged-phrase"]
    assert findings[0].line == 3


def test_check_module_reads_an_f_string_without_measuring_its_expressions(tmp_path):
    path = tmp_path / "mod.py"
    path.write_text('def f(n):\n    return f"We utilise {n} rows."\n', encoding="utf-8")
    assert [f.rule for f in check_module(path)] == ["discouraged-phrase"]


def test_the_two_exemptions_are_skipped_and_say_why():
    assert "accessibility.qmd" in EXEMPT
    assert "glossary.qmd" in EXEMPT
    assert all(reason for reason in EXEMPT.values())


def test_an_exempt_file_reports_nothing(tmp_path):
    path = tmp_path / "accessibility.qmd"
    path.write_text("---\ntitle: A\n---\n\nWe utilise it.\n", encoding="utf-8")
    assert main([str(path)]) == 0


# --- the command line ---


def test_main_returns_non_zero_when_a_finding_is_found(tmp_path, capsys):
    path = tmp_path / "page.qmd"
    path.write_text(" ".join(["word"] * 30) + ".\n", encoding="utf-8")
    assert main([str(path)]) == 1
    assert "sentence-too-long" in capsys.readouterr().out


def test_main_returns_zero_on_clean_prose(tmp_path, capsys):
    path = tmp_path / "page.qmd"
    path.write_text(
        "This page is short. Each sentence holds one idea.\n", encoding="utf-8"
    )
    assert main([str(path)]) == 0
    assert "sentence-too-long" not in capsys.readouterr().out


def test_main_fails_on_a_path_that_does_not_exist(tmp_path, capsys):
    """A renamed or mistyped path must not report success over nothing.

    This is the defect that matters most in a gate whose whole value is that a
    future author cannot drift past it.
    """
    assert main([str(tmp_path / "hints-renamed")]) == 1
    assert "unusable-target" in capsys.readouterr().out


def test_main_fails_on_a_directory_holding_nothing_it_can_read(tmp_path, capsys):
    (tmp_path / "notes.txt").write_text("We utilise it.\n", encoding="utf-8")
    assert main([str(tmp_path)]) == 1
    assert "unusable-target" in capsys.readouterr().out


def test_main_fails_on_a_file_it_has_no_rule_set_for(tmp_path, capsys):
    path = tmp_path / "lesson.rst"
    path.write_text("We utilise it.\n", encoding="utf-8")
    assert main([str(path)]) == 1
    assert "unusable-target" in capsys.readouterr().out


def test_an_exempt_target_is_a_decision_and_not_an_unusable_one(tmp_path, capsys):
    """An exemption passes; a path the gate cannot read does not."""
    path = tmp_path / "glossary.qmd"
    path.write_text("| a | b | We utilise it. |\n", encoding="utf-8")
    assert main([str(path)]) == 0
    assert "unusable-target" not in capsys.readouterr().out


def test_main_walks_a_directory_for_the_files_it_knows(tmp_path):
    (tmp_path / "hints").mkdir()
    (tmp_path / "hints" / "a.yml").write_text(
        "one:\n  nudge: We utilise it.\n", encoding="utf-8"
    )
    (tmp_path / "hints" / "README.md").write_text("We utilise it.\n", encoding="utf-8")
    assert main([str(tmp_path / "hints")]) == 1


# The only path in the list CI gates that is generated rather than committed.
# Keeping this set to one name is deliberate: every other gated path is in the
# repository, so an absent one is a real unusable-target and must still fail.
GENERATED = frozenset({"site/data.qmd"})


@pytest.fixture
def gated_target(request) -> Path:
    """One gated path, with the generated page written first if it is absent.

    ``site/data.qmd`` is built from the dataset registry at render time and is
    not committed, so after a fresh clone it does not exist. Without this, the
    case for it failed on a developer's first ``uv run pytest`` with nothing to
    say why, and passed only for someone who had run the renderer by hand.

    Writing it dirties nothing anyone would notice: the file is gitignored, and
    both ``render_site.py`` and the CI step before the gate overwrite it.

    This fixture owns one half of the dependency CI rests on -- that the page
    exists where the gate looks for it. The other half, that the flag writes
    the page at all, is owned by
    ``tests/test_site.py::test_the_data_page_can_be_written_without_a_render``.
    """
    path = REPO_ROOT / request.param
    if request.param in GENERATED and not path.exists():
        path.write_text(render_site.data_page(), encoding="utf-8")
    return path


@pytest.mark.parametrize("gated_target", _gated_paths(), indirect=True)
def test_the_gated_material_in_this_repository_passes(gated_target):
    """The gate is only a floor if the material already standing on it passes."""
    assert main([str(gated_target)]) == 0


def test_only_the_generated_page_is_written_for_the_gate():
    """The fixture is narrow on purpose, and this is what keeps it narrow.

    A committed path that goes missing is a real unusable-target and must keep
    failing. So every gated path except the generated one has to be here in the
    repository, and this fails if a second generated path joins the CI list
    without someone deciding what should write it.
    """
    assert GENERATED == frozenset({"site/data.qmd"})
    absent = [
        path
        for path in _gated_paths()
        if path not in GENERATED and not (REPO_ROOT / path).exists()
    ]
    assert absent == []


def test_the_exempt_pages_are_not_in_the_paths_ci_gates():
    """An exemption is a decision in the script, not a path quietly left out."""
    gated = {Path(path).name for path in _gated_paths()}
    assert not gated & set(EXEMPT)


def _authored_pages() -> set[str]:
    """Every page of the site a person wrote, as a repository-relative path."""
    pages = [
        *(REPO_ROOT / "site").glob("*.qmd"),
        *(REPO_ROOT / "site" / "_stages").glob("*.qmd"),
    ]
    return {page.relative_to(REPO_ROOT).as_posix() for page in pages} - GENERATED


def _pages_the_gate_accounts_for() -> set[str]:
    """Every page CI either gates or exempts, with gated directories expanded."""
    accounted = set()
    for target in _gated_paths():
        path = REPO_ROOT / target
        if path.is_dir():
            accounted |= {
                page.relative_to(REPO_ROOT).as_posix() for page in path.rglob("*.qmd")
            }
        elif path.suffix == ".qmd":
            accounted.add(target)
    accounted |= {f"site/{name}" for name in EXEMPT}
    return accounted - GENERATED


def test_every_authored_page_is_either_gated_or_exempt():
    """The other direction, and the one nothing enforced.

    The tests above check that no exempt page is gated and that every gated
    path is here. Neither notices a page nobody listed: a new ``site/setup.qmd``
    would publish to students without the gate ever reading it, and the
    workflow's comment -- "every student-facing surface is listed here" --
    would quietly stop being true.
    ``tests/test_site.py::test_tailwind_scans_the_committed_pages_and_not_the_generated_ones``
    guards the Tailwind content list the same way, for the same reason.

    This covers the site's pages. The Python modules in the gated list are
    still chosen by hand, because ``src/cwai/`` holds modules with no student
    prose in them; a new module that speaks to students has to be added there.
    """
    authored = _authored_pages()
    accounted = _pages_the_gate_accounts_for()
    assert authored == accounted, {
        "authored but neither gated nor exempt": sorted(authored - accounted),
        "accounted for but not an authored page": sorted(accounted - authored),
    }
