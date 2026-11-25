# Foundation branch — decisions taken on the module lead's behalf

Every call made during execution of `2026-11-25-computing-with-ai-foundation.md`
that the module lead did not make themselves, with what it costs if wrong.
Recorded here because the execution workspace is deleted on completion and a
decision that dies with it was made in secret.

Two decisions were the module lead's own and are **not** in this list: the
2021–2025 collision span with all-years traffic counts, and authorising the
DfT and Geofabrik downloads.

---

## A. Decisions that shape the teaching material

**Years are 2021–2025 for collisions, every published year for counts.**
DfT publishes per-year STATS19 only from 2021; earlier years sit inside
multi-gigabyte bundles. Proposed 2021–2025 provisionally (R23) so work could
continue, then the module lead chose it with all-years counts carrying the
pre-COVID baseline. `build_counts` had to stop filtering by year or the choice
would have been silently undone (R32). *If wrong:* one constant, some
description copy, one builder re-run.

**The study area is the five West Yorkshire ONS districts** — Bradford,
Calderdale, Kirklees, Leeds, Wakefield. The spec left area to the builder.
*If wrong:* re-run the subset builder against different codes.

**The site renders `student/`, not `notebooks/`.** Solutions stay open and
plainly in the repository; the stripped tree is what the site publishes, and
the worked-answer hint tier reaches the site in a later plan. *If wrong:* the
site's first release shows exercises rather than answers.

**The smoke notebook loads synthetic sensor data, with a collisions cell added
once real data landed** (R28). The first notebook a student runs proves the
whole stack on data guaranteed present in a fresh clone. *If wrong:* the first
notebook exercises synthetic rather than real data, labelled as such.

**Dataset paths and licence metadata are fixed in `cwai.registry`** (R13, R5,
R14), and nothing anywhere hardcodes a path or an attribution string. The data
README and the site's data page are generated from it. *If wrong:* a rename
touching several modules, which the licence audit catches.

**`ATTRIBUTION.txt` is audited, not excluded** (R26, as revised after a
reviewer overruled my first version). The ODbL notice beside a registered
dataset is permitted only when its contents equal the registry's attribution
string; a stray notice elsewhere is still reported. *If wrong:* an auditor that
ignores one filename.

**The fetch script documents that it needs the Codespace** (R27). Its two hosts
are `data.dft.gov.uk` and `storage.googleapis.com`, and Google Cloud Storage is
unreliable from mainland China. We cannot change where DfT hosts, so the
constraint is written where a tutor will meet it. *If wrong:* a tutor in Chengdu
hits an undiagnosed failure.

**`expected.json`'s schema constrains `value` by `type`, and tolerance applies
to numbers only** (R24, escalated against a reviewer's Minor grading). A
malformed answer fails CI rather than reaching the website. `checks/README.md`
states the contract a later JavaScript implementation must match. *If wrong:*
one fix round on a schema nobody has stressed.

**The weekly drift run is allowed to fail.** `continue-on-error` was suppressing
the only signal that reaches a human. *If wrong:* a red Monday run someone has
to look at, which is the point.

**Attribution copy for the generated datasets** was unspecified; the
implementer's wording stands (R15). *If wrong:* a string edit.

---

## B. Parked residuals — real, deferred, your call

1. **The accessibility statement's three manual-measurement sentences cannot be
   evidenced from the repository.** Contrast on five pages, the tab-order walk,
   and reflow at 640 and 320 pixels were genuinely performed and recorded in a
   task report, but only the position they hedge to is in the repo. Making them
   reproducible is the axe-in-CI work triaged to a later plan. *If wrong:* a
   conformance statement an auditor cannot reproduce from the repository.
2. **The SCSS-to-CSS token guard only matches 6-digit hex.** Correct for today's
   six variables; a named colour or `darken()` would be skipped.
3. **`tests.yml` inherits a 60-minute timeout** instead of its old 20. Longer,
   not absent.
4. **`README.md` is loose** about which workflows call the shared check list and
   when `fresh-resolve` runs. Cosmetic.

Plus the shippable minors the whole-branch review triaged explicitly: loose
fault-shape tests (the drift guard covers the regression they would catch),
beginner-facing errors in `scripts/` a student cannot reach, `years=True`
becoming year 1, and others listed in that review.

---

## C. Process and environment calls

These shaped how the work ran rather than what it produced.

- **R1** `uv` installed via pip and used to provision Python 3.12 alongside the
  system 3.13, rather than touching system Python.
- **R2, R8** Quarto comes from the `quarto-cli` PyPI package rather than a
  system install, so the same version runs locally, in a Codespace and in CI.
- **R3, R12** No git remote and no Docker, so CI, Pages deployment, the cron,
  the publish gate and `postCreate.sh` are verified by linting and parsing only.
  **First push and first Codespace launch are the real tests.**
- **R11** PEP 735 `[dependency-groups]` supersedes the plan's `[tool.uv]` wording.
- **R4, R18, R25, R29** Sequencing around the unauthorised download: the audit
  was scoped with a visible `--allow-missing` flag rather than a silent skip,
  and the flag was **deleted** once all eight datasets landed.
- **R16** Lint and formatting debt consolidated into the task that installs the
  CI gate, rather than resuming finished implementers.
- **R17, R19** Fetchers built and tested offline; filenames established by
  reading published pages, not by downloading.
- **R20, R21** Task 4's review held while the year span was open, and Task 7
  dispatched in its place rather than idling.
- **R22** Controller verification runs `ruff check` as well as the suite, after
  three tasks passed through an unwatched gate.
- **R30** Generating the review package is part of dispatching a review — I once
  dispatched one citing a diff file I had never created.
- **R33** The two Geofabrik extracts added to `fetch.SOURCES` so a tutor
  refreshing OSM data gets the same atomic write, timeout and provenance.
- **R6, R7, R9, R10, R31** Smaller calls on fault generation, non-vacuous test
  fixtures, licence-text fallbacks, fixture ordering, and the solution-marker
  contract between the stripper and the site test.
