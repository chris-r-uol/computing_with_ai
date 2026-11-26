# Stages 1–2 Machinery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the teaching machinery stages 1 and 2 depend on — inline hints, canonical slices, an unattempted check state, executable stubs, traceback cells that survive both runners, the road columns the stage-2 join needs, a gate that keeps the English plain — and prove it with one complete reference lesson and the workbook template.

**Architecture:** Everything a lesson calls lives in `src/cwai/`; everything that transforms a notebook lives in `scripts/`. Two new modules: `hints.py` (the `hint()` and `reveal()` renderers, and the single source of truth for tier names) and `slices.py` (the eight canonical slice definitions, and the metrics a handoff check recomputes from them). One new script, `check_prose.py`, enforces the language constraint in CI. Four existing files gain small, precise changes. The last two tasks are a vertical slice: the workbook template, and one lesson that exercises every mechanism end to end.

**Tech Stack:** Python 3.12, pandas, nbformat/nbclient, Quarto, pytest, `uv` for everything.

**Spec:** `docs/superpowers/specs/2026-11-25-stages-1-2-design.md`

## Scope note

The design covers both this machinery and the stage 1–2 lesson content. They are not independent — every lesson calls this machinery — but the content is mostly authoring judgement that the design deliberately leaves open ("exact lesson count and pagination", "the specific exercises, their planted faults, and their hint wording"). A single plan would have ended in tasks that decide nothing.

So this plan builds the machinery and **one complete reference lesson** that exercises all of it. The remaining lessons get their own plan, written with the working tools in hand and the reference lesson as the pattern. Each plan produces working software on its own: at the end of this one a student can sit down and do lesson 1.

## Global Constraints

Copied from the design and the built foundation. Every task's requirements include these.

- **Python 3.12**; run everything through `uv run`. Never invoke a bare `quarto` — use `uv run quarto`.
- **Every lesson notebook runs standalone on a fresh kernel, under 120 seconds, on a 2-core machine.** `scripts/run_notebooks.py` enforces this; `TIMEOUT_SECONDS = 120`.
- **No external network fetches** from the site or from any notebook. All data is vendored.
- **All data access goes through `cwai.data`.** No notebook or module reads a path under `data/` directly.
- **Hint tiers are `nudge`, `method`, `code`, `answer`**; `nudge` and `method` are required for every exercise; `code` and `answer` are mutually exclusive for any one exercise.
- **No answer text may appear in `student/`.** `SOLUTION_MARKER = "CWAI-SOLUTION"`; `scripts/build_student_notebooks.py --check` and the site render test both enforce this.
- **Years are `registry.YEARS == (2021, 2022, 2023, 2024, 2025)`**; area is the five West Yorkshire ONS districts `E08000032`–`E08000036`.
- **WCAG 2.2 AA.** Anything rendered into a page is keyboard-reachable and screen-reader sane. Disclosures are native `<details>`/`<summary>`; no JavaScript, no ARIA substitutes for native semantics.
- **Plain English, understood in English first.** Most students read this material in a second language. One idea per sentence; plain words over precise-sounding ones; active voice; no idioms, metaphors or English-dependent humour; plain verbs over phrasal verbs; every technical term defined on first use and added to the glossary; no unexplained abbreviations. This binds lesson text, hint wording, check messages and template prompts — every string a student can read. Design §7.8 has the full rule set. **Chinese appears in the glossary and nowhere else.**
- **Deliberately-failing cells carry both the `raises-exception` tag and `#| error: true` as the first source line.** One without the other breaks either CI or the published page (Task 6).
- **`ruff check` and `ruff format --check` pass at the end of every task.** Test output must be pristine — no new warnings.
- Fixes ship as changes to the file that owns the behaviour, not as new parallel files.

## Review Focus

Failure modes the design implies but that no task's main happy-path test exercises. Each gets a test in the task that owns the code.

1. **The stub sentinel reaching a raising helper.** A student's unanswered exercise passes `Ellipsis` to `expect_columns` or `expect_shape`, which raise rather than return — so the site render dies on an unattempted exercise even though `check()` was made safe. Both helpers must treat the sentinel as unattempted and return without raising. *(Task 4)*
2. **An unknown slice id.** A student typing `check_slice(..., "cyclist")` or `slices.get("leeds ")` should get the same teaching message `check()` gives for an unknown check name — naming near matches — not a bare `KeyError`. *(Tasks 3, 4)*
3. **A rate asked of a slice with no denominator.** Three of the eight slices have none; asking for a rate must say which slice and that it has no denominator, not divide by `None`. *(Task 3)*
4. **`reveal()` given something with no HTML representation.** A scalar, a string, `None`, or an object whose `_repr_html_` raises must still render a collapsed disclosure rather than breaking the cell. *(Task 1)*
5. **A missing or sentinel road number.** `first_road_number` carries `0` for unclassified roads and `-1` for unknown, and may be null; building a join key must not emit `A0`, `A-1` or `Anan`. *(Task 2)*

---

## File Structure

**Created**

| File | Responsibility |
|---|---|
| `src/cwai/hints.py` | `hint()` and `reveal()` renderers; `HINT_TIERS` as the single source of truth for tier names and their display labels |
| `src/cwai/slices.py` | the eight canonical `Slice` definitions, `load()`, and the `METRICS` a handoff check recomputes |
| `hints/01-foundations.yml` | hint tiers for stage 1's exercise ids |
| `notebooks/01-foundations/01-first-look.ipynb` | the reference lesson |
| `notebooks/04-project/my-analysis-template.ipynb` | the workbook template |
| `tests/test_slices.py` | slice definitions, metrics, error messages |
| `scripts/check_prose.py` | the plain-English gate: sentence length and a discouraged-phrase list |
| `tests/test_check_prose.py` | the gate's own tests |

**Modified**

| File | Change |
|---|---|
| `scripts/build_subsets.py` | add `first_road_class`, `first_road_number` to `COLLISION_COLUMNS`; rebuild |
| `src/cwai/checks.py` | the unattempted state; `check_slice()`; sentinel-safe `expect_*`; docstring correction |
| `scripts/build_student_notebooks.py` | executable stub; import `HINT_TIERS` from `cwai.hints`; docstring correction |
| `checks/README.md` | one implementation, not two |
| `data/stats19/collisions.parquet` | rebuilt with the two new columns |
| `tests/fixtures/stats19_collisions_sample.csv` | add a `first_road_number` column |
| `site/index.qmd`, `scripts/render_site.py` | rewrite the prose the gate flags |
| `.github/workflows/` | run the prose gate beside the licence audit |
| `tests/test_checks.py`, `tests/test_hints.py`, `tests/test_student_notebooks.py`, `tests/test_build_subsets.py`, `tests/test_run_notebooks.py`, `tests/test_site.py` | new cases per task |

---

## Task 1: The hint and reveal renderers

The design makes this first because the spike that proved the mechanism was written outside the repository and no longer exists. Everything else in stages 1–2 calls it.

**Mechanism, confirmed by spike before this plan was written:** nested native `<details>` elements emitted from a code cell render in Jupyter and survive Quarto's render into the static site with every tier intact and the answer collapsed. No JavaScript, no live kernel.

**Files:**
- Create: `src/cwai/hints.py`
- Create: `hints/01-foundations.yml`
- Test: `tests/test_hints.py` (exists — add cases; it currently imports from `build_student_notebooks`)

**Interfaces:**
- Consumes: `cwai.registry.repo_root()`
- Produces:
  - `HINT_TIERS: tuple[tuple[str, str], ...]` — `(("nudge", "Nudge"), ("method", "Method"), ("code", "Show the answer"), ("answer", "A model answer"))`. Tier **names** in order, each with its **display label**. Task 5 imports this.
  - `TIER_NAMES: tuple[str, ...]` — just the names, derived from `HINT_TIERS`.
  - `REQUIRED_TIERS: tuple[str, ...]` — `("nudge", "method")`
  - `EXCLUSIVE_TIERS: frozenset[str]` — `frozenset({"code", "answer"})`
  - `hint(exercise_id: str, path: Path | None = None) -> IPython.display.HTML`
  - `reveal(value: object, label: str = "Show the output") -> IPython.display.HTML`
  - `UnknownExerciseError(KeyError)`

- [ ] **Step 1: Write the failing tests for `hint()`**

```python
def test_hint_renders_one_disclosure_per_tier_plus_a_wrapper(tmp_path):
    path = write_hints(tmp_path, {"demo": {"nudge": "look here", "method": "do this"}})
    html = hints.hint("demo", path=path).data
    assert html.count("<details") == 3          # wrapper + two tiers
    assert "Nudge" in html and "Method" in html
    assert "look here" in html and "do this" in html


def test_hint_orders_tiers_and_labels_them_from_hint_tiers(tmp_path):
    path = write_hints(
        tmp_path,
        {"demo": {"code": "df.head()", "nudge": "n", "method": "m"}},
    )
    html = hints.hint("demo", path=path).data
    assert html.index("Nudge") < html.index("Method") < html.index("Show the answer")


def test_hint_escapes_html_in_the_hint_text(tmp_path):
    path = write_hints(tmp_path, {"demo": {"nudge": "use <b> & co", "method": "m"}})
    html = hints.hint("demo", path=path).data
    assert "use &lt;b&gt; &amp; co" in html


def test_hint_on_an_unknown_exercise_names_near_matches(tmp_path):
    path = write_hints(tmp_path, {"first-look-severity": {"nudge": "n", "method": "m"}})
    with pytest.raises(hints.UnknownExerciseError) as exc:
        hints.hint("first-look-severty", path=path)
    assert "first-look-severity" in str(exc.value)


def test_hint_renders_no_open_attribute_so_every_tier_starts_collapsed(tmp_path):
    path = write_hints(tmp_path, {"demo": {"nudge": "n", "method": "m", "code": "c"}})
    assert "open" not in hints.hint("demo", path=path).data
```

`write_hints` is a helper in the test module that writes a YAML file into `tmp_path` and returns its path.

- [ ] **Step 2: Write the failing tests for `reveal()`** — Review Focus item 4

```python
def test_reveal_wraps_a_dataframes_html_in_a_collapsed_disclosure():
    html = hints.reveal(pd.DataFrame({"a": [1, 2]})).data
    assert html.startswith("<details") and "open" not in html
    assert "<table" in html
    assert "Show the output" in html


def test_reveal_takes_a_custom_label():
    assert "What did it print?" in hints.reveal(42, label="What did it print?").data


@pytest.mark.parametrize("value", [42, "text", None, 3.5, ["a", "b"]])
def test_reveal_renders_plain_values_without_an_html_representation(value):
    html = hints.reveal(value).data
    assert "<details" in html and repr(value) in html


def test_reveal_falls_back_to_repr_when_repr_html_raises():
    class Hostile:
        def _repr_html_(self):
            raise RuntimeError("no")

        def __repr__(self):
            return "Hostile()"

    assert "Hostile()" in hints.reveal(Hostile()).data


def test_reveal_escapes_a_plain_value_that_looks_like_markup():
    assert "&lt;script&gt;" in hints.reveal("<script>").data
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `uv run pytest tests/test_hints.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'cwai.hints'` or `AttributeError`.

- [ ] **Step 4: Implement `src/cwai/hints.py`**

Define `HINT_TIERS`, `TIER_NAMES`, `REQUIRED_TIERS`, `EXCLUSIVE_TIERS` and `UnknownExerciseError` with the values in the Interfaces block above.

`hint(exercise_id, path=None)` reads the YAML (default `registry.repo_root() / "hints"`, resolved to the stage file for the exercise id's prefix — see note below), raises `UnknownExerciseError` with `difflib.get_close_matches` near matches in the style of `checks.UnknownCheckError`, and returns an `HTML` whose outer `<details>` summarises as `Hints for <code>{exercise_id}</code>` and whose inner `<details>` are the present tiers, in `HINT_TIERS` order, labelled from it. Escape every hint string with `html.escape`; render the `code` tier inside `<pre><code>`, the others inside `<p>`.

`reveal(value, label="Show the output")` returns a collapsed `<details>` whose body is `value._repr_html_()` when that attribute exists and returns without raising, and otherwise `<pre>` + `html.escape(repr(value))`.

Resolving the hints file: `hint()` takes an explicit `path` for tests. With none, it reads every `*.yml` under `hints/` and merges them, raising `ValueError` naming both files if one exercise id appears in two. One flat namespace keeps lesson authors from having to pass a path in every cell.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/test_hints.py -v`
Expected: PASS.

- [ ] **Step 6: Write the Quarto-survival test**

This is the test that would have caught the lost spike. In `tests/test_hints.py`:

```python
@pytest.mark.slow
def test_rendered_hint_survives_a_quarto_render(tmp_path):
    """All four disclosures and every tier's text reach the published HTML."""
```

Build a one-cell notebook that calls `hint()` on a fixture id with all four tiers populated, render it with `uv run quarto render` into `tmp_path`, and assert the output HTML contains four `<details` occurrences, each tier's display label, and each tier's text. Mark it `slow` and follow whatever marker registration `tests/test_site.py` already uses for its render tests.

- [ ] **Step 7: Create `hints/01-foundations.yml`**

One entry per exercise id the reference lesson will use (Task 8 fixes the ids). Start with the three the lesson needs: `first-look-row-count`, `first-look-severity-split`, `first-look-why-blank-coordinates` — the last with an `answer` tier and no `code` tier.

- [ ] **Step 8: Run the full suite and the linters**

Run: `uv run pytest -q && uv run ruff check && uv run ruff format --check`
Expected: all pass, no new warnings.

- [ ] **Step 9: Commit**

```bash
git add src/cwai/hints.py hints/01-foundations.yml tests/test_hints.py
git commit -m "feat: inline hint and reveal renderers"
```

---

## Task 2: Road columns in the collision subset

The stage-2 join needs a road identifier, and the subset has none. The raw downloads are still on disk at `raw/` (gitignored), so this is a local rebuild with no re-fetch.

**Files:**
- Modify: `scripts/build_subsets.py` (`COLLISION_COLUMNS`)
- Modify: `tests/fixtures/stats19_collisions_sample.csv` (add `first_road_number`)
- Modify: `data/stats19/collisions.parquet` (rebuilt)
- Test: `tests/test_build_subsets.py`

**Interfaces:**
- Produces: `cwai.data.load_collisions()` frames carry `first_road_class` and `first_road_number`, both `Int64`, positioned immediately after `local_authority_ons_district`.

- [ ] **Step 1: Add `first_road_number` to the collision fixture**

The fixture already has `first_road_class`. Add a `first_road_number` column covering the cases the key builder must survive: an A-road number, a motorway number, `0` (unclassified), `-1` (unknown) and an empty cell.

- [ ] **Step 2: Write the failing tests**

```python
def test_collisions_carry_the_road_identifier_columns(tmp_path):
    df = build_collisions(FIXTURE, tmp_path / "c.parquet")
    assert "first_road_class" in df.columns
    assert "first_road_number" in df.columns
    assert df.first_road_class.dtype == "Int64"
    assert df.first_road_number.dtype == "Int64"


def test_collisions_columns_exactly_match_declared_set(tmp_path):
    # already exists — it will fail until COLLISION_COLUMNS is updated
    df = build_collisions(FIXTURE, tmp_path / "c.parquet")
    assert tuple(df.columns) == COLLISION_COLUMNS + ("severity_label",)
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `uv run pytest tests/test_build_subsets.py -v`
Expected: FAIL — `first_road_class` not in columns.

- [ ] **Step 4: Add both names to `COLLISION_COLUMNS`**

Insert `"first_road_class"` and `"first_road_number"` immediately after `"local_authority_ons_district"`. They need no entry in `_TEXT`, `_FLOAT` or `_DATE`, so `_read` types them `Int64` already.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/test_build_subsets.py -v`
Expected: PASS.

- [ ] **Step 6: Rebuild the vendored subsets**

Run: `uv run python scripts/build_subsets.py raw/`
Then confirm the committed data is still within budget and unchanged in row count:

Run: `uv run pytest tests/test_vendored_data.py -q && du -sh data/`
Expected: PASS; `data/` still well under the 80 MB budget; collisions still 20,485 rows.

- [ ] **Step 7: Pin the join's teaching claim as a test** — Review Focus item 5

The stage-2 lesson rests on three facts about this data. Pin them here so the content plan can rely on them, and so a future re-vendor that changes them fails CI rather than quietly invalidating a lesson. In `tests/test_vendored_data.py`:

```python
ROAD_CLASS_PREFIX = {1: "M", 2: "A", 3: "A", 4: "B", 5: "C", 6: "U"}


def road_key(road_class, road_number):
    """'A58' from (3, 58); 'A1(M)' from (2, 1); 'U' from (6, 0)."""
```

Then assert, against the real vendored data:

```python
def test_major_road_collisions_are_the_joinable_subset():
    c = data.load_collisions()
    major = c.first_road_class.isin([1, 2, 3, 4])
    assert major.sum() == 10_060
    assert (c.first_road_class == 6).sum() == 10_422


def test_a_naive_road_name_join_matches_almost_everything():
    """97.3% matched — which is why the lesson asks whether the number is true."""
    keys = road_key_series(data.load_collisions())
    names = set(data.load_traffic_counts().road_name.dropna())
    assert keys.isin(names).mean() == pytest.approx(0.973, abs=0.001)


def test_the_unclassified_match_is_an_aggregate_bucket_not_a_road():
    """'U' matches on both sides but means 'every minor road', so the rate is void."""
    counts = data.load_traffic_counts()
    assert "U" in set(counts.road_name)
    assert set(counts.loc[counts.road_name == "U", "road_type"]) == {"Minor"}


def test_road_key_never_emits_a_sentinel_or_missing_number():
    for number in (0, -1, pd.NA):
        assert road_key(3, number) == "A"
    assert road_key(6, 0) == "U"
    assert road_key(2, 1) == "A1(M)"
```

`road_key_series` is a helper in the test module applying `road_key` across a frame. Class 2 is `A(M)`, so its key is `f"A{number}(M)"` — the traffic counts spell these `A1(M)`, `A58(M)`, `A64(M)`.

- [ ] **Step 8: Run the full suite and the linters**

Run: `uv run pytest -q && uv run ruff check && uv run ruff format --check`
Expected: all pass.

- [ ] **Step 9: Commit**

```bash
git add scripts/build_subsets.py tests/ data/stats19/collisions.parquet
git commit -m "feat: carry road class and number in the collision subset"
```

---

## Task 3: Canonical slice definitions

Eight slices means eight right answers, so a handoff check cannot look an answer up. It recomputes from the definition. The definitions are also what keeps the shortlist and the material from drifting apart.

**Files:**
- Create: `src/cwai/slices.py`
- Create: `tests/test_slices.py`

**Interfaces:**
- Consumes: `cwai.data.load_collisions()`, `cwai.data.load_casualties()`
- Produces:
  - `Slice` — frozen dataclass: `id: str`, `label: str`, `table: str` (`"collisions"` or `"casualties"`), `denominator: str | None`, `select: Callable[[pd.DataFrame], pd.Series]` (a boolean mask)
  - `SLICES: tuple[Slice, ...]` — the eight below
  - `get(slice_id: str) -> Slice`, `list_slices() -> list[str]`
  - `load(slice_id: str) -> pd.DataFrame`
  - `ksi(df: pd.DataFrame, table: str) -> pd.Series`
  - `METRICS: dict[str, SliceMetric]`, where `SliceMetric` is a frozen dataclass `name: str`, `kind: str`, `tolerance: float`, `compute: Callable[[Slice], object]`
  - `UnknownSliceError(KeyError)`, `NoDenominatorError(ValueError)`

**The eight slices, verified against the vendored data:**

| `id` | `label` | `table` | `select` | `denominator` | rows | KSI % |
|---|---|---|---|---|---|---|
| `cyclists` | Cyclists | casualties | `casualty_type == 1` | `pedal_cycles` | 2,304 | 30.9462 |
| `pedestrians` | Pedestrians | casualties | `casualty_type == 0` | `None` | 5,016 | 32.7751 |
| `leeds` | Leeds | collisions | district `E08000035` | `all_motor_vehicles` | 7,298 | 29.6383 |
| `bradford` | Bradford | collisions | district `E08000032` | `all_motor_vehicles` | 5,163 | — |
| `kirklees` | Kirklees | collisions | district `E08000034` | `all_motor_vehicles` | 3,327 | — |
| `wakefield` | Wakefield | collisions | district `E08000036` | `all_motor_vehicles` | 2,889 | — |
| `calderdale` | Calderdale | collisions | district `E08000033` | `all_motor_vehicles` | 1,808 | 29.8119 |
| `after-dark` | After dark | collisions | `light_conditions in {4, 5, 6, 7}` | `None` | 6,328 | 31.7478 |

KSI means severity Fatal or Serious: `severity_label.isin(["Fatal", "Serious"])` for collisions, `casualty_severity.isin([1, 2])` for casualties.

- [ ] **Step 1: Write the failing tests for the definitions**

```python
def test_there_are_eight_slices_with_unique_ids():
    assert len(slices.SLICES) == 8
    assert len({s.id for s in slices.SLICES}) == 8


@pytest.mark.parametrize(
    "slice_id,rows",
    [
        ("cyclists", 2304),
        ("pedestrians", 5016),
        ("leeds", 7298),
        ("bradford", 5163),
        ("kirklees", 3327),
        ("wakefield", 2889),
        ("calderdale", 1808),
        ("after-dark", 6328),
    ],
)
def test_each_slice_selects_the_expected_number_of_rows(slice_id, rows):
    assert len(slices.load(slice_id)) == rows


def test_three_slices_have_no_denominator():
    without = {s.id for s in slices.SLICES if s.denominator is None}
    assert without == {"pedestrians", "after-dark"}


def test_every_denominator_is_a_real_traffic_count_column():
    columns = set(data.load_traffic_counts().columns)
    for s in slices.SLICES:
        if s.denominator is not None:
            assert s.denominator in columns
```

Note: the design's prose says "three of the eight slices have no usable denominator". Two have none *in the data* (`pedestrians`, `after-dark`); the third case is `pedestrians`' motor-traffic proxy, which exists but is not a cyclist/pedestrian exposure measure. The test pins the structural fact — two `None` denominators — and `test_three_slices_have_no_denominator` is therefore misnamed; call it `test_two_slices_have_no_denominator_column`.

- [ ] **Step 2: Write the failing tests for the error paths** — Review Focus items 2 and 3

```python
def test_unknown_slice_id_names_near_matches():
    with pytest.raises(slices.UnknownSliceError) as exc:
        slices.get("cyclist")
    assert "cyclists" in str(exc.value)


def test_unknown_slice_id_with_no_near_match_lists_the_choices():
    with pytest.raises(slices.UnknownSliceError) as exc:
        slices.get("zzz")
    assert "cyclists" in str(exc.value) and "after-dark" in str(exc.value)


def test_asking_for_a_rate_on_a_slice_with_no_denominator_says_which():
    with pytest.raises(slices.NoDenominatorError) as exc:
        slices.denominator_column("after-dark")
    assert "after-dark" in str(exc.value)
    assert "no denominator" in str(exc.value).lower()
```

- [ ] **Step 3: Write the failing tests for the metrics**

```python
def test_row_count_metric_recomputes_per_slice():
    m = slices.METRICS["slice-row-count"]
    assert m.compute(slices.get("cyclists")) == 2304
    assert m.compute(slices.get("after-dark")) == 6328


def test_ksi_percent_metric_recomputes_per_slice():
    m = slices.METRICS["slice-ksi-percent"]
    assert m.compute(slices.get("cyclists")) == pytest.approx(30.9462, abs=0.001)
    assert m.compute(slices.get("after-dark")) == pytest.approx(31.7478, abs=0.001)


def test_ksi_percent_metric_declares_a_tolerance_and_number_kind():
    m = slices.METRICS["slice-ksi-percent"]
    assert m.kind == "number" and m.tolerance > 0


def test_row_count_metric_is_exact():
    assert slices.METRICS["slice-row-count"].tolerance == 0
```

- [ ] **Step 4: Run the tests to verify they fail**

Run: `uv run pytest tests/test_slices.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'cwai.slices'`.

- [ ] **Step 5: Implement `src/cwai/slices.py`**

Build the eight `Slice` records from the table above. `load(slice_id)` calls `cwai.data.load_collisions()` or `load_casualties()` per `table` and returns the frame masked by `select`. `ksi(df, table)` returns the boolean mask for the table's severity column. `denominator_column(slice_id)` returns the column name or raises `NoDenominatorError` naming the slice. `UnknownSliceError` follows `checks.UnknownCheckError`: near matches from `difflib.get_close_matches`, and the full id list when there are none.

`METRICS` holds the two entries the tests pin. The content plan adds more; each is a `SliceMetric` so `check_slice` needs no change to support one.

- [ ] **Step 6: Run the tests to verify they pass**

Run: `uv run pytest tests/test_slices.py -v`
Expected: PASS.

- [ ] **Step 7: Run the full suite and the linters**

Run: `uv run pytest -q && uv run ruff check && uv run ruff format --check`
Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add src/cwai/slices.py tests/test_slices.py
git commit -m "feat: canonical slice definitions and recomputed metrics"
```

---

## Task 4: The unattempted check state, and `check_slice`

The module lead's call: the published site shows exercises as unattempted, not wrong. This is where that happens.

**Files:**
- Modify: `src/cwai/checks.py`
- Modify: `checks/README.md`
- Test: `tests/test_checks.py`

**Interfaces:**
- Consumes: `cwai.slices.get`, `cwai.slices.METRICS`, `cwai.slices.UnknownSliceError`
- Produces:
  - `UNATTEMPTED` — the sentinel, `Ellipsis`. Exported by name so a notebook or test never spells `...` itself.
  - `CheckResult` gains `attempted: bool = True`; `__bool__` stays `self.passed`; `__repr__` renders the three states.
  - `check(name, value) -> CheckResult` returns an unattempted result when `value is UNATTEMPTED`.
  - `check_slice(name: str, value: object, slice_id: str) -> CheckResult`
  - `expect_columns` / `expect_shape` return without raising when handed `UNATTEMPTED`.

- [ ] **Step 1: Write the failing tests for the unattempted state**

```python
def test_an_untouched_stub_reads_as_unattempted_not_failed():
    result = checks.check("fixture-number", checks.UNATTEMPTED)
    assert result.attempted is False
    assert result.passed is False
    assert "✗" not in repr(result)
    assert "not attempted yet" in repr(result)


def test_a_wrong_answer_still_reads_as_wrong():
    result = checks.check("fixture-number", 999)
    assert result.attempted is True and result.passed is False
    assert "✗" in repr(result)


def test_a_right_answer_still_reads_as_right():
    result = checks.check("fixture-number", 42)
    assert result.attempted is True and result.passed is True
    assert "✓" in repr(result)


def test_an_unattempted_result_is_still_falsey():
    assert not checks.check("fixture-number", checks.UNATTEMPTED)


def test_an_unknown_check_name_still_raises_even_when_unattempted():
    """A typo in the check name is an authoring bug, not an unanswered exercise."""
    with pytest.raises(checks.UnknownCheckError):
        checks.check("no-such-check", checks.UNATTEMPTED)
```

Use the existing `tests/fixtures_expected.json` entries; add a `fixture-number` entry with value `42` if none fits.

- [ ] **Step 2: Write the failing tests for sentinel-safe `expect_*`** — Review Focus item 1

```python
def test_expect_columns_treats_the_sentinel_as_unattempted():
    checks.expect_columns(checks.UNATTEMPTED, ["a", "b"])  # must not raise


def test_expect_shape_treats_the_sentinel_as_unattempted():
    checks.expect_shape(checks.UNATTEMPTED, rows=3)  # must not raise


def test_expect_shape_still_rejects_nothing_to_check_when_unattempted():
    """The authoring bug is still a bug; only the student's blank is excused."""
    with pytest.raises(ValueError):
        checks.expect_shape(checks.UNATTEMPTED)
```

- [ ] **Step 3: Write the failing tests for `check_slice`**

```python
def test_check_slice_passes_the_right_answer_for_that_slice():
    assert checks.check_slice("slice-row-count", 2304, "cyclists").passed


def test_check_slice_rejects_another_slices_right_answer():
    result = checks.check_slice("slice-row-count", 6328, "cyclists")
    assert not result.passed
    assert "2304" in result.message


def test_check_slice_applies_the_metrics_tolerance():
    assert checks.check_slice("slice-ksi-percent", 30.946, "cyclists").passed
    assert not checks.check_slice("slice-ksi-percent", 31.5, "cyclists").passed


def test_check_slice_reads_an_untouched_stub_as_unattempted():
    result = checks.check_slice("slice-row-count", checks.UNATTEMPTED, "cyclists")
    assert result.attempted is False and "not attempted yet" in repr(result)


def test_check_slice_on_an_unknown_slice_raises_the_slice_error():
    with pytest.raises(slices.UnknownSliceError):
        checks.check_slice("slice-row-count", 1, "cyclist")


def test_check_slice_on_an_unknown_metric_names_near_matches():
    with pytest.raises(checks.UnknownCheckError) as exc:
        checks.check_slice("slice-row-counts", 1, "cyclists")
    assert "slice-row-count" in str(exc.value)
```

- [ ] **Step 4: Run the tests to verify they fail**

Run: `uv run pytest tests/test_checks.py -v`
Expected: FAIL — `AttributeError: module 'cwai.checks' has no attribute 'UNATTEMPTED'`.

- [ ] **Step 5: Implement the changes in `src/cwai/checks.py`**

Add `UNATTEMPTED = Ellipsis`. Give `CheckResult` an `attempted: bool = True` field and make `__repr__` render `✓ name: message`, `✗ name: message`, or — when `attempted` is false — a neutral line with no cross, reading `— {name}: not attempted yet`. The exact wording and markup are the implementer's within the design's accessibility constraint; it must not use a cross or the word "failed", and the three states must be distinguishable without colour.

In `check()`, return the unattempted result **after** the unknown-name lookup, so an authoring typo still raises. Guard `expect_columns` and `expect_shape` with an early return on the sentinel, placed after `expect_shape`'s "nothing to check" `ValueError`.

`check_slice(name, value, slice_id)` resolves the slice via `slices.get` (letting `UnknownSliceError` propagate), looks `name` up in `slices.METRICS` and raises `UnknownCheckError` with near matches if absent, computes the expected value, and reuses `_compare` with the metric's `kind` and `tolerance`.

- [ ] **Step 6: Run the tests to verify they pass**

Run: `uv run pytest tests/test_checks.py tests/test_slices.py -v`
Expected: PASS.

- [ ] **Step 7: Correct the two-implementation contract**

The design rules that the site shows the notebook's own rendered check output, so there is no JavaScript implementation. Rewrite the "**Two implementations read this file**" paragraph in `checks/README.md` to describe one, and keep the comparison contract — it is still the specification of `_compare`. Delete the JavaScript-facing asides ("Do the same in JavaScript", "a JavaScript implementation that insisted on…") and the parenthetical about having no JavaScript equivalent. Correct the first paragraph of the `src/cwai/checks.py` module docstring, which says the file is read by "the website's JavaScript too". Document `UNATTEMPTED` and the three states in the README, since that file is the contract.

- [ ] **Step 8: Run the full suite and the linters**

Run: `uv run pytest -q && uv run ruff check && uv run ruff format --check`
Expected: all pass.

- [ ] **Step 9: Commit**

```bash
git add src/cwai/checks.py checks/README.md tests/
git commit -m "feat: unattempted check state and per-slice handoff checks"
```

---

## Task 5: Executable stubs and the fourth hint tier

A stub of `# your code here` is a comment, so a stripped notebook raises `NameError` the moment a later cell uses a name an exercise defined. That silently forbids any exercise from defining anything.

**Files:**
- Modify: `scripts/build_student_notebooks.py`
- Test: `tests/test_student_notebooks.py`, `tests/test_hints.py`

**Interfaces:**
- Consumes: `cwai.hints.HINT_TIERS`, `TIER_NAMES`, `REQUIRED_TIERS`, `EXCLUSIVE_TIERS`
- Produces: `STUB_MARKER = "answer = ...  # your code here"`; `HINT_TIERS`/`REQUIRED_TIERS` re-exported from `cwai.hints` so existing importers keep working.

- [ ] **Step 1: Write the failing tests for the executable stub**

```python
def test_a_stripped_solution_cell_still_binds_a_name():
    nb = notebook_with_solution("answer = c.groupby('severity_label').size()")
    stripped = strip_solutions(nb)
    assert "answer = ..." in stripped.cells[-1].source


def test_a_stripped_notebook_executes_end_to_end():
    """The site renders student/, so an unanswered exercise must not break it."""
```

The second test builds a notebook whose solution cell binds `answer`, whose next cell uses `answer`, strips it, executes it through `run_notebooks.run`, and asserts `result.passed`. This is the test that pins the whole reason for the change.

```python
def test_a_markdown_solution_cell_still_becomes_a_prose_stub():
    assert TEXT_STUB in strip_solutions(notebook_with_markdown_solution()).cells[-1].source
```

- [ ] **Step 2: Write the failing tests for the fourth tier**

```python
def test_an_answer_tier_is_accepted():
    validate_hints({"demo": {"nudge": "n", "method": "m", "answer": "because..."}}, ["demo"], Path("x.yml"))


def test_code_and_answer_together_are_rejected():
    with pytest.raises(MissingHintError) as exc:
        validate_hints(
            {"demo": {"nudge": "n", "method": "m", "code": "c", "answer": "a"}},
            ["demo"],
            Path("x.yml"),
        )
    assert "code" in str(exc.value) and "answer" in str(exc.value)


def test_an_unrecognised_tier_is_still_rejected():
    with pytest.raises(MissingHintError):
        validate_hints({"demo": {"nudge": "n", "method": "m", "hint": "x"}}, ["demo"], Path("x.yml"))


def test_tier_names_come_from_cwai_hints():
    import cwai.hints
    assert build_student_notebooks.HINT_TIERS is cwai.hints.HINT_TIERS
```

Match `validate_hints`' real signature, which the existing tests in `tests/test_hints.py` already use.

- [ ] **Step 3: Run the tests to verify they fail**

Run: `uv run pytest tests/test_student_notebooks.py tests/test_hints.py -v`
Expected: FAIL — stub is a bare comment; `answer` is an unrecognised tier.

- [ ] **Step 4: Make the changes in `scripts/build_student_notebooks.py`**

Set `STUB_MARKER = "answer = ...  # your code here"`. Delete the local `HINT_TIERS` and `REQUIRED_TIERS` definitions and import them from `cwai.hints` instead, re-exporting both names so `tests/test_hints.py` and any other importer keep working. Extend `validate_hints` to reject a tier set containing both members of `EXCLUSIVE_TIERS`, with a message naming both. Correct the module docstring: hints are reachable inline in the notebook, not "on the site once that interface is built".

Authoring note for the lesson tasks, to go in that docstring: a solution cell must bind `answer`, because that is the name the stub binds.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/test_student_notebooks.py tests/test_hints.py -v`
Expected: PASS.

- [ ] **Step 6: Regenerate the student notebooks and confirm they are not stale**

Run: `uv run python scripts/build_student_notebooks.py && uv run python scripts/build_student_notebooks.py --check`
Expected: the second run reports nothing stale.

- [ ] **Step 7: Run the full suite and the linters**

Run: `uv run pytest -q && uv run ruff check && uv run ruff format --check`
Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add scripts/build_student_notebooks.py student/ tests/
git commit -m "feat: executable exercise stubs and an answer hint tier"
```

---

## Task 6: Traceback cells that survive both runners

Stage 1 teaches reading a traceback, which needs a cell that really raises. The design named the `raises-exception` tag. **A spike run before this plan found that is only half the answer:** `nbclient`, and so `scripts/run_notebooks.py`, honours the tag — but **Quarto ignores it and fails the render**, producing no HTML. Quarto's own mechanism is the cell option `#| error: true`, as the first line of the cell source. Both are needed, and the pair was confirmed to work together: the render succeeds, the traceback appears in the HTML, and execution continues to the following cell.

This task makes that contract explicit and tested, so a lesson author cannot get it half-right.

**Files:**
- Create: `tests/fixtures/raises_exception.ipynb`
- Test: `tests/test_run_notebooks.py`, `tests/test_site.py`

**Interfaces:**
- Produces: a documented authoring contract — a deliberately-failing cell carries **both** the `raises-exception` tag and `#| error: true` as its first source line.

- [ ] **Step 1: Create the fixture notebook**

`tests/fixtures/raises_exception.ipynb`: a markdown cell, a cell that succeeds, a cell carrying both the `raises-exception` tag and the `#| error: true` first line whose body raises `ValueError`, and a final cell that prints a sentinel string proving execution continued.

- [ ] **Step 2: Write the failing test for the nbclient path**

```python
def test_a_tagged_raising_cell_does_not_fail_the_notebook_runner():
    result = run_notebooks.run(FIXTURES / "raises_exception.ipynb")
    assert result.passed, result.error
```

- [ ] **Step 3: Write the failing test for the Quarto path**

In `tests/test_site.py`, alongside its existing render tests and using the same marker and helpers:

```python
def test_a_raising_cell_renders_its_traceback_instead_of_failing_the_render():
    """Quarto ignores raises-exception; the cell option is what saves the render."""
```

Render the fixture through the real site render path and assert the output HTML contains `ValueError`, the exception's message, and the sentinel from the cell after it.

- [ ] **Step 4: Write the test that pins the pair as a contract**

```python
def test_every_raising_cell_carries_both_mechanisms():
    """One without the other breaks either CI or the published page."""
```

Walk every notebook under `notebooks/`, and for each code cell assert that the `raises-exception` tag and a leading `#| error: true` are either both present or both absent, naming the notebook and cell index on failure. This is the test that stops a lesson author shipping half the contract.

- [ ] **Step 5: Run the tests to verify they fail or pass as expected**

Run: `uv run pytest tests/test_run_notebooks.py tests/test_site.py -v`
Expected: the nbclient test and the contract test PASS without production changes — nbclient already honours the tag, and no notebook yet has a raising cell. The Quarto test FAILS if the fixture omits `#| error: true`; confirm that by deleting the line, watching it fail, and restoring it. Record that confirmation in the task report: it is the only evidence that the test tests anything.

- [ ] **Step 6: Document the contract**

Add it to `student/README.md` — where a lesson author looks — and reference it from the `scripts/run_notebooks.py` module docstring. Two sentences: both mechanisms, and what each one is for.

- [ ] **Step 7: Run the full suite and the linters**

Run: `uv run pytest -q && uv run ruff check && uv run ruff format --check`
Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add tests/ student/README.md scripts/run_notebooks.py
git commit -m "test: pin the dual mechanism for deliberately-failing cells"
```

---

## Task 7: The prose gate

The language constraint binds every string a student reads, and most of the material will be written by someone who never read the design. A stated rule is not enough; this makes it mechanical.

The gate is a floor, not the goal. It cannot tell whether prose is *good* for these readers — only whether it has drifted back towards the dense register of the documents that specify the course.

**Files:**
- Create: `scripts/check_prose.py`
- Create: `tests/test_check_prose.py`
- Modify: `site/index.qmd`, `scripts/render_site.py` (the stage-page strings) — whatever the gate flags
- Modify: `.github/workflows/` — add the gate to the job that already runs `check_licences.py`

**Interfaces:**
- Produces:
  - `MAX_SENTENCE_WORDS = 25`, `MAX_MEAN_SENTENCE_WORDS = 18`
  - `PLAIN_ALTERNATIVES: dict[str, str]` — a discouraged phrase to its plain replacement
  - `Finding` — frozen dataclass: `source: str`, `line: int`, `rule: str`, `detail: str`
  - `sentences(text: str) -> list[str]`
  - `check_text(text: str, source: str) -> list[Finding]`
  - `check_notebook(path: Path) -> list[Finding]` — markdown cells only
  - `check_qmd(path: Path) -> list[Finding]`
  - `check_hints(path: Path) -> list[Finding]`
  - `main(argv) -> int` — non-zero when any finding is returned, printing each as `source:line: rule — detail`

**Scope, and the two exemptions.** The gate covers notebook markdown cells, the values in `hints/*.yml`, `site/index.qmd`, and the stage-page prose built in `scripts/render_site.py`. It skips:

- `site/accessibility.qmd` — a legal statement whose precision is the point, and which cites regulations in their own words.
- `site/glossary.qmd` — a term list, not prose.

Both exemptions are named in the script with the reason beside them, so a future reader sees a decision rather than an oversight. Nothing else is exempt, including this plan's own reference lesson.

- [ ] **Step 1: Write the failing tests for sentence splitting**

Code is not prose, so it must not be measured as prose.

```python
def test_sentences_splits_on_terminators():
    assert sentences("One idea. Then another! A third?") == ["One idea.", "Then another!", "A third?"]


def test_sentences_ignores_fenced_code():
    text = "Read it.\n\n```python\nx = 1; y = 2; z = 3\n```\n\nThen run it."
    assert sentences(text) == ["Read it.", "Then run it."]


def test_sentences_ignores_inline_code_but_keeps_the_sentence():
    assert len(sentences("Call `df.groupby('a').size()` on it.")) == 1


def test_sentences_does_not_split_on_a_decimal_or_an_abbreviation():
    assert len(sentences("The rate is 31.75 per cent.")) == 1
    assert len(sentences("Use e.g. a filter.")) == 1


def test_sentences_ignores_markdown_tables_and_urls():
    assert sentences("| a | b |\n|---|---|\n| 1 | 2 |\n\nSee https://example.com/a.b.c now.") == [
        "See https://example.com/a.b.c now."
    ]
```

- [ ] **Step 2: Write the failing tests for the rules**

```python
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
    assert check_text("The autobus is late.", "x.md") == []  # 'bus' must not match inside a word


def test_findings_carry_the_line_number_they_were_found_on():
    findings = check_text("Fine.\n\nWe utilise it.", "x.md")
    assert findings[0].line == 3
```

- [ ] **Step 3: Write the failing tests for the file readers and the exemptions**

```python
def test_check_notebook_reads_markdown_cells_and_not_code_cells():
    """A code cell's comments are for the author, not the student."""


def test_check_hints_flags_a_hint_string():
    """Hint wording is student-facing prose and gets the same gate."""


def test_the_two_exemptions_are_skipped_and_say_why():
    assert "accessibility.qmd" in EXEMPT
    assert all(reason for reason in EXEMPT.values())


def test_main_returns_non_zero_when_a_finding_is_found(tmp_path, capsys):
    ...
    assert main([str(path)]) == 1
    assert "sentence-too-long" in capsys.readouterr().out
```

- [ ] **Step 4: Run the tests to verify they fail**

Run: `uv run pytest tests/test_check_prose.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'check_prose'`.

- [ ] **Step 5: Implement `scripts/check_prose.py`**

Strip fenced code, inline code, markdown tables and URLs before splitting. Split on `.`, `!`, `?` followed by whitespace and a capital, guarding decimals and a short abbreviation list.

`PLAIN_ALTERNATIVES` starts with the phrases the design names and the ones this plan's own author reached for. Seed it with at least these, each mapped to its plain replacement: `utilise`→`use`, `regarding`→`about`, `prior to`→`before`, `in order to`→`to`, `bear in mind`→`remember`, `a number of`→`some`, `in the event that`→`if`, `commence`→`start`, `terminate`→`stop`, `endeavour`→`try`, `facilitate`→`help`, `subsequently`→`then`, `nevertheless`→`but`, `call off`→`cancel`, `cut down on`→`reduce`, `carry out`→`do`, `down the line`→`later`, `on the fly`→`while it runs`. Match case-insensitively on word boundaries.

The list will grow. It is a seed, not a specification, and adding to it is ordinary maintenance rather than a change of policy.

- [ ] **Step 6: Run the tests to verify they pass**

Run: `uv run pytest tests/test_check_prose.py -v`
Expected: PASS.

- [ ] **Step 7: Run the gate over the existing student-facing pages and fix what it flags**

Run: `uv run python scripts/check_prose.py site/index.qmd scripts/render_site.py hints/`
Expected: findings. These pages were written before the constraint existed, in the register the gate is meant to prevent, so fixing them is part of this task. Rewrite the flagged prose rather than widening the thresholds or the exemptions. The home page's subtitle and its "Two ways through the material" section are the likely offenders.

Then confirm nothing regressed:

Run: `uv run pytest tests/test_site.py -q`
Expected: PASS.

- [ ] **Step 8: Add the gate to CI**

Add `uv run python scripts/check_prose.py` to the workflow job that already runs `scripts/check_licences.py`, with the student-facing paths as arguments. Run `actionlint` on the changed workflow.

- [ ] **Step 9: Run the full suite and the linters**

Run: `uv run pytest -q && uv run ruff check && uv run ruff format --check && uv run python scripts/check_prose.py site/index.qmd scripts/render_site.py hints/ notebooks/`
Expected: all pass.

- [ ] **Step 10: Commit**

```bash
git add scripts/check_prose.py tests/test_check_prose.py site/index.qmd scripts/render_site.py hints/ .github/
git commit -m "feat: a prose gate for plain English in student-facing material"
```

---

## Task 8: The workbook template

The thing a student grows all week, and the artefact stage 4 continues.

**Files:**
- Create: `notebooks/04-project/my-analysis-template.ipynb`
- Test: `tests/test_site.py` (or a new `tests/test_workbook.py` if that file is already crowded)

**Interfaces:**
- Consumes: `cwai.slices.list_slices()`, `cwai.data`
- Produces: a template a student copies to `my-analysis.ipynb`.

**Sections, from the design:** the slice and why; first look; cleaning; description; the join; rates; what this does not show. Each is a markdown heading with a prompt, and an empty code cell beneath.

- [ ] **Step 1: Write the failing tests**

```python
def test_the_template_has_every_section_the_design_names():
    headings = markdown_headings(TEMPLATE)
    for section in ("slice", "first look", "cleaning", "description", "join", "rate", "not show"):
        assert any(section in h.lower() for h in headings)


def test_the_template_runs_on_a_fresh_kernel():
    """It must work the moment a student copies it, before they write anything."""
    assert run_notebooks.run(TEMPLATE).passed


def test_the_template_names_every_slice_so_a_student_can_choose():
    source = all_source(TEMPLATE)
    for slice_id in slices.list_slices():
        assert slice_id in source


def test_the_template_is_not_stripped_or_executed_as_a_lesson():
    """It is the student's file: no solution tags, no exercise tags, no checks."""
    assert not any(tags(cell) & {"solution", "exercise"} for cell in TEMPLATE_CELLS)


def test_the_templates_prompts_pass_the_prose_gate():
    """Its prompts are the first English a student reads in their own file."""
    assert check_prose.check_notebook(TEMPLATE) == []
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest -k workbook -v`
Expected: FAIL — the template does not exist.

- [ ] **Step 3: Build the template**

Seven sections as above. The first carries the slice shortlist, generated from `slices.list_slices()` with each slice's label and whether it has a denominator, so the template cannot drift from the definitions. Prompts are written for a student with four days of Python, in the module's plain register.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest -k workbook -v`
Expected: PASS.

- [ ] **Step 5: Confirm the template is excluded from the student build**

The template lives under `notebooks/` so CI runs it, but it must not be stripped into `student/` as a lesson. Confirm what `scripts/build_student_notebooks.py` does with it and, if it copies it, exclude it by name with a test that pins the exclusion.

- [ ] **Step 6: Run the full suite, the linters and the prose gate**

Run: `uv run pytest -q && uv run ruff check && uv run ruff format --check && uv run python scripts/check_prose.py notebooks/04-project/`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add notebooks/04-project/my-analysis-template.ipynb tests/
git commit -m "feat: the companion workbook template"
```

---

## Task 9: The reference lesson

One complete lesson that exercises every mechanism this plan built. It is the pattern the content plan follows, and the only proof that the machinery works together.

**Files:**
- Create: `notebooks/01-foundations/01-first-look.ipynb`
- Modify: `hints/01-foundations.yml`, `checks/expected.json`
- Test: `tests/test_site.py`, `tests/test_notebooks_content.py` (new)

**Interfaces:**
- Consumes: everything above — `hints.hint`, `hints.reveal`, `checks.check`, `checks.check_slice`, `checks.UNATTEMPTED`, `slices.list_slices`, `cwai.data`

**What the lesson must contain,** one of each so every mechanism is exercised:

| Mechanism | How it appears |
|---|---|
| Teaching on the demo slice | all of West Yorkshire, never a student's slice |
| A `check()` exercise | solution cell binds `answer`; stub is executable |
| A `check_slice()` handoff | "now do this for your slice", recomputed |
| Three hint tiers | `hint("first-look-row-count")` |
| The `answer` tier | an "explain why" exercise with a prose model answer |
| Predict before you run | `reveal()` around the output being predicted |
| A real traceback | a cell with both the tag and `#| error: true` |
| A planted fault | working-looking code with a real error |

**Subject:** read the collisions table, describe it, and meet one way it lies to you — the design names the casualty-type code read one position out, which turned cyclists into pedestrians. That is the planted fault, and it is a real mistake from the module lead's own session.

- [ ] **Step 1: Write the failing tests**

```python
def test_the_reference_lesson_runs_standalone_within_the_time_limit():
    result = run_notebooks.run(LESSON)
    assert result.passed, result.error
    assert result.seconds < run_notebooks.TIMEOUT_SECONDS


def test_the_stripped_lesson_also_runs_standalone():
    """What the site executes is the stripped copy, so that is what must run."""
    assert run_notebooks.run(STUDENT_LESSON).passed


def test_every_exercise_in_the_lesson_has_its_hints():
    check_notebook_hints(LESSON)  # raises MissingHintError if not


def test_every_check_name_the_lesson_uses_resolves():
    for name in check_names_called(LESSON):
        assert name in checks.load_expected() or name in slices.METRICS


def test_the_lesson_exercises_each_mechanism_once():
    source = all_source(LESSON)
    for call in ("hint(", "reveal(", "check(", "check_slice("):
        assert call in source


def test_the_lesson_teaches_on_the_demo_slice_not_a_students_slice():
    """No student's chosen slice may be worked through for them."""
    source = all_source(LESSON)
    for slice_id in slices.list_slices():
        assert f'load("{slice_id}")' not in source


def test_the_lessons_prose_and_hints_pass_the_prose_gate():
    assert check_prose.check_notebook(LESSON) == []
    assert check_prose.check_hints(HINTS_FILE) == []
```

`check_names_called` and `all_source` are helpers in the new test module; `check_notebook_hints` already exists in `scripts/build_student_notebooks.py`.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_notebooks_content.py -v`
Expected: FAIL — the lesson does not exist.

- [ ] **Step 3: Write the lesson**

The eight mechanisms above, on the subject named above, for a student whose first cell this is. Pagination and the exact exercise wording are the author's. Every solution cell is tagged `solution`, wrapped with `wrap_solution`, and binds `answer`. Every exercise cell is tagged `exercise` with its id in `metadata.cwai.id`.

- [ ] **Step 4: Add the hint entries and the expected answers**

Extend `hints/01-foundations.yml` with every exercise id the lesson uses, and `checks/expected.json` with the fixed answers. Handoff answers do **not** go in `expected.json` — they come from `slices.METRICS`.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/test_notebooks_content.py -v`
Expected: PASS.

- [ ] **Step 6: Regenerate the student copy and render the site**

Run: `uv run python scripts/build_student_notebooks.py && uv run python scripts/render_site.py`
Expected: both succeed. Then confirm by eye in the rendered HTML that the lesson's exercises read as unattempted rather than wrong, and that every hint tier is present and collapsed.

- [ ] **Step 7: Run the full suite, the linters, the whole-notebook run and the prose gate**

Run: `uv run pytest -q && uv run ruff check && uv run ruff format --check && uv run python scripts/run_notebooks.py notebooks/ && uv run python scripts/check_prose.py notebooks/ hints/ site/index.qmd scripts/render_site.py`
Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add notebooks/ student/ hints/ checks/expected.json tests/
git commit -m "feat: the stage 1 reference lesson"
```

---

## Self-review

**1. Spec coverage.** Every section of the design maps to a task:

| Design | Task |
|---|---|
| §7.1 slice shortlist, canonical definitions | 3 |
| §7.2 inline hints, lost spike, fourth tier, one implementation | 1, 4, 5 |
| §7.3 exercise types, `reveal()` | 1, 9 |
| §7.4 executable stub, unattempted state, `raises-exception`, `check_slice` | 4, 5, 6 |
| §7.5 stage 1 content | 9 (reference lesson); rest → content plan |
| §7.6 stage 2 join, road columns, authority-level join | 2 (data + pinned facts); content → content plan |
| §7.7 the workbook | 8 |
| §7.8 language and register, the prose gate | 7 |
| §7.9 repository shape, the five foundation changes | 1–6 |
| Decisions 1–16 | all except 10 and 13, which are content-plan rulings recorded in the design |

Gaps, stated rather than hidden: stage 2's lesson content, the rest of stage 1's lessons, and decision 10's authority-level join material all belong to the content plan. §9's items are the module lead's, not a builder's.

**2. Step scan.** Every step names a file, a command, or a test with its assertions. No step says "handle edge cases" or "add validation". Task 6 step 5 is unusual — it asks the implementer to break a test to prove it fails — and that is deliberate: a test that passes before the code exists is the one failure mode a TDD plan cannot otherwise catch, and this task's production change is zero.

Task 7 is the one task whose step 7 does open-ended work — "fix what the gate flags" — because the findings cannot be known before the gate exists. It is bounded: three files, and the rule is to rewrite the prose rather than widen the threshold.

**3. Type consistency.** `HINT_TIERS` is defined once in Task 1 as `tuple[tuple[str, str], ...]` and imported in Task 5. `UNATTEMPTED` is `Ellipsis` throughout. `CheckResult.attempted` is used in Tasks 4 and 9. `Slice.select` returns a mask, not a frame — `load()` applies it. `check_slice(name, value, slice_id)` has the same argument order in Tasks 3, 4 and 9.

**4. Review Focus.** All five items have tests: 1 → Task 4 step 2; 2 → Task 3 step 2 and Task 4 step 3; 3 → Task 3 step 2; 4 → Task 1 step 2; 5 → Task 2 step 7.

**5. Proportion.** Measured: 1,170 lines against the design's 309, of which 500 are inside code fences. Those fences hold test assertions and shell commands — no function bodies, and the one place a body was tempting (the `road_key` helper in Task 2) is a signature and a docstring with its cases as assertions. The prose is 670 lines for nine tasks, about 75 per task. The two places that carry exact values — the slice table in Task 3 and the join facts in Task 2 — carry them because they were measured against the real data and an implementer cannot derive them. I judged this proportionate rather than a transcript, but it is near the limit: a tenth task would be a signal to split again.
