# Follow-ups from the stages 1–2 machinery branch

Findings that were deliberately not fixed, kept because the plan's working
directory is deleted when the plan ends and these would otherwise be lost.

Each task's review raised Minor findings that were deferred rather than fixed,
so that fix rounds stayed small. The whole-branch review then triaged all 53 into
three buckets. Four were promoted and fixed; the rest are below, as it bucketed
them. **Nothing here is wrong to ship** — that was the whole-branch review's
explicit finding, and the branch merges with all of it outstanding.

For the decisions that produced the branch, see
`2026-11-26-stages-1-2-decisions.md`. For the material itself, see
`2026-11-25-stages-1-2-design.md`.

## Parked after the single fix wave

The fix wave is closed and gets no second round, so these five were parked with
rulings rather than fixed. The first is the one the final reviewer named as
belonging on the next branch.

1. **The lesson makes four falsifiable claims about pandas' traceback shape and
   nothing pins any of them.** Lesson 1 now describes the chained traceback in
   detail — two halves, `KeyError` twice, one arrow per frame, about fifty lines.
   All four are verified true today on both the Codespace and published routes. A
   pandas release that stopped raising `from err` would silently falsify the
   paragraph for every student. The cheap pin is one assertion on the rendered
   lesson for `The above exception was the direct cause`. This is the same class
   of risk the branch fixed elsewhere, left half-done by its own standard.
2. **`slices.ksi()`'s two-entry assumption on `_LOADERS` is implicit.** Adding
   `"vehicles"` to `_LOADERS` later would route vehicles into the casualty
   branch. It raises a noisy pandas `KeyError` rather than returning a wrong
   answer, so it is not the bug class that was fixed — but the old explicit
   `if table == "casualties"` documented the invariant and the new code does not.
3. **The glossary's slash split happens after the backtick strip**, so a future
   row written `` | `axis` / `axes` | `` would yield a term with a stray
   backtick. Latent: no row uses backticks in the English column today.
4. **`_authored_pages()` is narrower than its docstring claims.** It globs
   `site/*.qmd` and `site/_stages/*.qmd`; the docstring says every authored page.
   A page under a new `site/<dir>/` escapes both the gate and the test that is
   supposed to notice. Not a false guarantee in the dangerous direction, but the
   wording overstates the reach.
5. **"A person who was hurt"** in the lesson's `slices-intro` and the template's
   `slice-prompt` describes a casualty row that may be a fatality. The glossary's
   own wording, "hurt or killed", is the precise form.

## Should fix soon

The whole-branch review's middle bucket, 23 items. Grouped by where they live.

### The prose gate and the glossary
- The `JARGON` seed is 17 words and has now missed `join`, `authority`, `axes`
  and `baseline` — each found by a different agent while writing student prose.
  **A systematic pass over every term the lessons introduce, feeding both
  `JARGON` and the glossary, is cheaper done once than discovered per lesson.**
- `traceback`, `DataFrame`, `index` and `missing value` are glossary rows that
  `JARGON` does not gate, so the gate would not stop a future author using them
  undefined.
- A `None` hint tier value renders the word "None" to a student;
  `validate_hints` type-checks only `nudge` and `method`.
- `build_student_notebooks.load_hints()` validates that the hints YAML is a
  mapping of mappings and `cwai.hints._load()` does not, so the two readers of
  the same file disagree about what a valid file is.
- Two hint namespaces: the builder resolves `hints/<stage>.yml` per stage while
  `cwai.hints` merges every `hints/*.yml` into one flat namespace. One duplicated
  id anywhere breaks every `hint()` call in the course, and nothing looks for it.
- A whitespace-only line is not a paragraph break; an empty tier renders as `""`.
- `.md` is a readable suffix but not a walked one, so `hints/README.md` is
  skipped though it has five findings. Fix the asymmetry, not the coverage — that
  file is author-facing and correctly out of scope.
- `EXEMPT` matches on basename anywhere, so any file called `glossary.qmd` is
  exempt. Worth knowing before per-stage glossaries exist.
- The mean-sentence rule is measured per notebook cell, so prose split into
  two-sentence cells escapes the only rule that catches cumulative density.

### Tests whose cover is narrower than their name
- The shipped-hints test renders each entry but never calls `validate_hints`, so
  a shipped entry carrying both `code` and `answer` would pass. Narrow today;
  wide as soon as a hints file carries an id ahead of its lesson, which is how
  the content plan will work.
- No test covers `UnknownCheckError.__str__`; the tests pass without the
  override because `str(KeyError)` contains the name in quotes.
- The exclusivity assertion would pass on any message naming both tiers.
- The `check`/`check_slice` parity test covers only a string typed against a
  number.
- No numpy array or DataFrame reaches `check`/`check_slice`, so an `is`→`==`
  regression would not be caught there (it would be caught in `expect_*`).
- The stored-answer test keys results by check name, so a name called twice would
  let a later ✓ hide an earlier ✗. Key by position.
- The message-distinctness tests do not cover every direction.
- `test_the_shortlist_shows_which_slices_have_no_denominator` reads the rendered
  DataFrame via `row.split()[-2:]`, so it is coupled to pandas' repr width and
  column order; a new `shortlist()` column breaks it unhelpfully.
- The hand-typed shortlist check and the lesson's demo-slice test both miss a
  list written with single quotes. One regex fixes both.
- An indented `#| error: true` passes the dual-mechanism contract test though
  Quarto may not accept it; and the contract allows only one `#|` line, so a
  `#| label:` line before the error option trips the first-line rule. The content
  plan writes more raising cells than this branch did.
- Section 7's example guard hard-codes the set of no-denominator slices as well
  as their columns. The set is derivable from `slices.SLICES`; only the columns
  are not. A ninth such slice would get no example and fail no test.

### Student-facing wording
- The pairing prompt says "You already know one thing" about a fact nothing
  earlier supplied. It is supplied in the prompt itself, so nobody is stuck.
- The `○` message says "Replace the ... with your answer". This is the most-read
  string in the course and a screen reader may mangle the ellipsis. "Replace the
  three dots (`...`)" costs nothing.
- The workbook cell gives the template path and the copy's name but no
  destination folder. Worth a half-sentence when the Codespace setup material is
  written, which is where "your own repository" gets a shape.
- The template names no variable for the chosen slice while the lesson uses
  `my_slice`; reconcile when the lessons are written.
- Exercise 1 points at a marker only the generated copy contains; exercises 2
  and 4 omit the location entirely.
- Exercise 2 is close to pre-answered by a cell two above it.
- A student sees the check name `slice-row-count` while the exercise id is
  `first-look-your-slice-rows`.

## Measured facts the content plan needs

Found while verifying this branch and not written down anywhere else.

- **The honest major-road join loses 385 rows.** The naive key matches 98.12% of
  all collisions, but the major-road join matches only **9,675 of 10,060
  (96.2%)** — 384 B-roads and 1 A-road have no count point at all. A student will
  lose those rows and needs telling why *before* they think they broke it.
- `road_name` spells the same road both `A58(M)` and `A58M`, and carries `A1(T)`.
- **`C` is a second aggregate bucket exactly like `U`** (3 collisions), so the
  `U` lesson has a sibling.
- The counts hold **72 to 369 count points per authority-year** (mean 142), so an
  authority denominator is a `groupby` and a sum, not a lookup.
- **There are no blank or `NaN` values in any of the four datasets.** DfT encodes
  unknown as a number, usually `-1`: `age_of_vehicle` in 34.0% of rows,
  `age_of_driver` in 19.5%, `vehicle_manoeuvre` in 8.2%, plus
  `weather_conditions` code 9 in 339 rows and `road_type` in 607. The mean of
  `age_of_driver` is **32.23** trusting the column and **40.31** dropping the -1
  rows — eight years wrong, nothing blank, no warning.
- `road_key` lives only in `tests/test_vendored_data.py`, so the 98.1% pin
  constrains a test-local implementation. If the lesson teaches students to build
  the key themselves, say so in that test's docstring.

## Process note for the next plan

Every defect the per-task reviews structurally could not find sat **at a seam
between tasks, and all of them were prose rather than code**: one task's cell
option leaking into another's teaching surface; a claim corrected in two files
while a third kept the old wording; and one task's return shape being right for
a second task and wrong for a third.

**Add one explicit cross-task step: re-read every sentence that describes the
behaviour of another task's code.** Six of the whole-branch review's eight
Important findings would have been caught by that one step.

Second: per-task reviews flag a test in isolation, and the answer is usually in
the test beside it. Of seven findings flagged as merge-blocking during execution,
three stood and four were over-called — three of those because the cover being
doubted already existed in a sibling test. A final pass that reads each flag
against its siblings is worth having.
