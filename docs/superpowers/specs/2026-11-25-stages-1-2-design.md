# Stages 1 and 2 — teaching material design

**Date:** 2026-11-25
**Status:** Draft for approval
**Builds on:** `2026-11-25-computing-with-ai-design.md` (module design) and the foundation branch now on `main`

---

## 1. Intent and why

The foundation ships the machinery: real data, loaders whose errors a beginner can act on, a self-check layer, three tiers of hints, solution stripping, a site that works offline. It ships one notebook, a smoke test. This design covers the first two stages of actual teaching material — Python from nothing, then working with an AI agent.

The organising decision, taken by the module lead, is that **a student finishes the week with one piece of analysis they grew, not a folder of completed exercises.** Everything below follows from that. Lessons are scaffolding; the student's own workbook is the building.

This also answers a failure the module design named: projects that are all the same. If a student's analysis is shaped by a choice made in their first hour, twenty students arrive at Thursday's studio with twenty different pieces of work, and stage 4 is not a cold start on a blank project but finishing something they have lived with all week.

### What success looks like

- A student with no programming experience has, by Friday, an analysis of a road-safety question about one slice of West Yorkshire that they can run, explain and defend.
- They can say what is wrong with it — which numbers they trust, which they do not, and why.
- They reach for an agent and then check what it produced, rather than either avoiding it or believing it.
- A student who falls behind discovers it on Tuesday, not Thursday.

---

## 2. Goals

1. **Zero-prerequisite entry.** The first cell a student runs assumes nothing.
2. **One growing artefact.** Every lesson ends by advancing the student's own analysis.
3. **Divergence by construction.** The slice choice in hour one makes each student's work different.
4. **Engineering practice from the start**, not as an advanced topic: reading a traceback, `assert`, the debugger, `pytest`.
5. **AI as a verification skill.** Stage 2 assesses finding the fault, not producing the code.
7. **Unstuck without leaving the page.** Hints and answers reach the student where they are working.
8. **Lessons stay standalone**, so CI keeps running them and a student returning in six months finds them working.
9. **Honest about the data.** Students meet real coding errors, missing values and absent denominators, and learn to say so.

## 3. Non-goals

- Stages 3 and 4 (PyTorch, Keras, the project, stretch material) — a later plan.
- The interactive widgets — a later plan.
- Comprehensive Python. No OOP beyond "a class is a thing with data and methods", no decorators, no async.
- **Teaching git.** The foundation's README covers clone and commit, and that is all the module teaches. The module design's §7.8 git notebook is therefore *not* in stages 1–2 and needs either a home in a later plan or deletion. Stage 2 does teach **reading a diff**, but an agent's diff, which is where the skill earns its place.
- Marking. The self-check layer tells a student whether they are right; it records nothing and reports to nobody.

## 4. Anti-goals

Things that would make this a failure even if it technically worked:

1. **A student who can prompt but not read.** Solutions are open, so this cannot be prevented by scarcity. It is prevented by exercise design or not at all.
2. **Skipped handoffs discovered on Thursday.** The workbook is the deliverable; a student who never starts it has nothing, and must find that out early.
3. **Lessons that only work with a tutor in the room.** The common case is a student alone, late, with nobody to ask.
4. **A workbook that is a pile of disconnected cells.** It has to read as one analysis by Friday, not as seven pasted answers.
5. **Exercises whose answer is a web search away and whose point is the typing.** With open solutions, "write code that outputs X" teaches nothing.
6. **A published site that looks broken.** The site renders stripped notebooks, so every exercise on it is unanswered. If that reads as *failed* rather than *not yet attempted*, the course's public face is a column of crosses.

---

## 5. Constraints

Inherited from the module design and the built foundation:

| Constraint | Detail |
|---|---|
| Time | Stages 1–2 get **tutorials 1 and 2** (2 hours each) plus roughly **10 hours** of the block's self-study. Everything below must fit that. |
| Entry | Zero Python. No pre-block work can be assumed. |
| Lessons | Every lesson notebook runs standalone on a fresh kernel, under 120 seconds, on a 2-core machine. CI enforces all three. |
| Solutions | Open. Stripped to a stub in `student/`, present in `notebooks/`, reachable inline. |
| Hints | Tiers come from `hints/*.yml`; `HINT_TIERS` is currently `nudge`/`method`/`code`, with `nudge` and `method` required. |
| Self-check | `cwai.checks.check(name, value)` returns a non-raising `CheckResult`; `expect_columns` / `expect_shape` raise. |
| Data | Vendored and real: 20,485 collisions 2021–2025, 26,436 casualties, 37,152 vehicles, traffic counts 2000–2025, two city networks. |
| Network | No external fetches from the site. Students may be on a poor connection from Chengdu. |
| Accessibility | WCAG 2.2 AA. Anything rendered into a page is keyboard-reachable and screen-reader sane. |
| Language | **Plain English, written to be understood in English by a reader whose first language is not English** (§7.8). Chinese appears in the glossary and nowhere else. |

---

## 6. Approaches considered

How the growing analysis is carried.

### Option 1 — A companion workbook *(chosen)*

Lesson notebooks teach on a shared demo slice. Each ends with a handoff section: "now do this for your slice", done in `my-analysis.ipynb`, created from a template in the first hour.

- **For:** lesson notebooks stay standalone, so CI and the six-months-later guarantee hold. The student ends with one artefact they can explain. Stage 4 is that file continued.
- **Against:** two notebooks open, and nothing structurally prevents a student skipping every handoff.

### Option 2 — Lessons write the workbook

Each lesson appends the student's result to a growing document programmatically.

- **For:** no switching.
- **Against:** makes lesson notebooks stateful across runs, which fights the standalone rule and means CI writes a workbook weekly. The student cannot see their analysis whole, and the assembly is machinery they did not write and cannot debug. Rejected.

### Option 3 — Fork the lesson

Each lesson is a template the student copies and personalises.

- **For:** one file at a time, nothing to switch between.
- **Against:** seven personalised files rather than one analysis; stage 4 has nothing single to continue; copies drift from originals so the standalone guarantee goes. Rejected.

### Decision

**Option 1.** Its weakness — the skipped handoff — is addressed directly rather than designed around: handoff sections carry self-checks of their own (§7.4), so a student can tell whether their own slice work is right, and Thursday's studio opens with each student showing their workbook. Falling behind becomes visible on Tuesday.

---

## 7. The design

### 7.1 The slice shortlist

A student picks one in the first hour, from a vetted list. All were checked against the real data; the variation in whether an exposure denominator exists is deliberate and is itself teaching material.

| Slice | Size | Denominator in the traffic counts |
|---|---|---|
| Cyclists | 2,304 casualties | `pedal_cycles` — a real one |
| Pedestrians | 5,016 casualties | none; motor traffic is a proxy they must argue for |
| Leeds | 7,298 collisions | `all_motor_vehicles` for the authority |
| Bradford | 5,163 collisions | as above |
| Kirklees | 3,327 collisions | as above |
| Wakefield | 2,889 collisions | as above |
| Calderdale | 1,808 collisions | as above |
| After dark | 6,328 collisions | **none at all** |

Severity is nearly flat across districts (27.7%–29.8% killed or seriously injured), so a district choice changes the volume a student handles rather than what they find. After dark does change it: **31.75% after dark against 27.75% in daylight** (the all-collisions figure, 28.99%, is the wrong comparison, because it already contains the dark collisions).

Rejected as slices: motorcyclists (~1,500, no clean denominator) and wet roads (behaves like the baseline, nothing to find).

**The demo slice used in lesson examples is all of West Yorkshire**, so no student's chosen slice is worked through for them.

**The slices get canonical definitions in code**, in a new `cwai.slices` module: an id, a human label, the filter that produces the slice from the loaded frames, and which denominator column (if any) applies. This is needed for three separate reasons — the handoff self-checks (§7.4), the stage-2 denominator split (§7.6), and keeping the shortlist and the material from drifting apart — so it is one module, not three ad-hoc copies.

### 7.2 Inline hints — mechanism

A call in the notebook renders the tiers as nested HTML disclosures:

```
hint("collisions-by-severity")
  ▸ Nudge             →  which column holds severity?
  ▸ Method            →  group by it, then count the rows in each group
  ▸ Show the answer   →  c.groupby("severity_label").size()
```

Plain `<details>` elements, no JavaScript and no live kernel. A spike confirmed that a cell emitting this renders in Jupyter and that the same output survives Quarto's render into the static site with all tiers intact and the answer collapsed. So a Codespace student never leaves the editor, a site-first student sees the identical thing, and it is keyboard-accessible by default.

**The spike artefact no longer exists** — it was written outside the repository and has been cleaned up. Re-establishing it as `src/cwai/hints.py`, with a test that asserts the rendered HTML survives the site render, is therefore the first task of the plan and a prerequisite for every lesson.

This supersedes the module design's plan for a site-side hint interface, and makes a second, JavaScript implementation of the self-check unnecessary: the site shows the notebook's own rendered check output. `checks/README.md` currently promises two implementations and must be corrected to one. The docstring of `scripts/build_student_notebooks.py` says hints are reachable "on the site once that interface is built", which is likewise now wrong.

**A fourth tier, `answer`, is added** for the "explain why" exercises. Those have no code solution, and `strip_solutions` replaces a markdown solution cell with `*Write your answer here.*`, so today a model prose answer reaches nobody. `HINT_TIERS` becomes `nudge`/`method`/`code`/`answer`, with `code` and `answer` mutually exclusive for any one exercise: `code` for a coding exercise, `answer` for a written one. Doing this now, while there are no exercises, is far cheaper than doing it at fifty.

### 7.3 Exercise types

Because solutions are open, "write code that produces X" is not an exercise. The material uses four shapes:

- **Predict before you run.** The cell asks what the output will be; running it reveals the answer. The answer being available is the point.
- **Find the planted fault.** Working-looking code with a real error. Knowing where it was is only useful after looking.
- **Explain why.** A short written answer compared against a model answer (the `answer` hint tier).
- **Verify someone else's.** Given an analysis and the claim drawn from it, decide whether the claim holds.

**Predict exercises need a reveal.** On the site every cell's output is printed above the next cell, so the thing the student is meant to predict is already visible. A `reveal()` helper — the same `<details>` machinery as `hint()`, so it costs almost nothing once §7.2 exists — wraps the output being predicted so it is collapsed until the reader opens it. In the Codespace the student can of course just run the cell, which is the intended behaviour there.

### 7.4 Exercise cells, self-checks, and what the site shows

This is the mechanical core, and the published appearance follows from it.

**The site renders the stripped student notebooks and executes them.** So every exercise on the public site is unanswered. Two consequences had to be designed for.

**A stub must still execute.** `STUB_MARKER` is currently `# your code here` — a bare comment. A later cell referring to the name the solution defined raises `NameError`, which fails the render and CI. The stub becomes an assignment to a sentinel:

```python
answer = ...  # your code here
check("collisions-by-severity", answer)
```

The exercise cell carries both the stub and its check, so the two are never separated. `Ellipsis` is a legitimate value, so the notebook runs end to end whether or not the exercise was attempted.

**An unattempted check reads as unattempted, not failed.** This was the module lead's call. `CheckResult` currently renders `✓` or `✗`. It gains a third state: when the value handed to `check()` is the stub sentinel, it renders as *not attempted yet* with neutral wording and no cross. A wrong answer still gets `✗`; only an untouched stub gets the neutral state. So a visitor to the site sees a complete, working lesson with its exercises visibly waiting, and a student who answers wrongly is still told plainly.

**Deliberately-failing cells** — the traceback-reading material in stage 1, where the whole point is that the student sees a real exception — need **two** mechanisms, not one. A spike established this after the design was first written, and it corrects what this section originally claimed:

- `scripts/run_notebooks.py` runs on nbclient, which honours the **`raises-exception` cell tag**. Confirmed working as-is: a tagged raising cell passes the runner.
- **Quarto ignores that tag** and fails the whole render, producing no page at all. Its own mechanism is the cell option **`#| error: true`**, as the first line of the cell's source.

With both in place the runner passes, the render succeeds, the traceback appears on the page, and execution continues to the next cell — all confirmed. Either one alone breaks something: the tag alone breaks the published site, the cell option alone breaks CI. This keeps the global "notebooks must run clean" guarantee intact rather than relaxing it, and because getting it half-right is so easy, a test asserts that the two always appear together.

**Handoff checks recompute rather than look up.** A handoff asks the student to do something for *their* slice, so there are eight right answers, and `checks/expected.json` holds one value per name. Instead, a handoff check derives the expected value at run time from the canonical slice definition (§7.1) — `check_slice(name, value, slice_id)` — so every slice is covered by one definition, and a student whose filter does not match the canonical one is told so rather than silently passing.

### 7.5 Stage 1 — Programming from first principles

Python through the collision data from the first cell. Variables, types, collections, loops, conditionals, functions; then modules and imports; then `pandas`. Engineering practice woven in: reading a traceback, `assert`, the debugger, `pytest` on the student's own functions.

The thread: **read one dataset, describe it, and learn where it lies to you.** Missing values, implausible coordinates, a severity field that is a code needing a lookup. The module lead's own session produced a live example worth using — a casualty-type code read one position out, turning cyclists into pedestrians, caught only because a number looked wrong.

Handoffs build the first half of the workbook: the slice chosen and justified, a first look at it, what was cleaned and why, a description of what is in it.

*Tutorial 1 (2h):* live debugging of errors the cohort actually hit, harvested from their notebooks beforehand, plus the ideas that do not survive silent reading.

### 7.6 Stage 2 — AI-accelerated and agentic workflows

Autocomplete first, then agentic coding with GitHub Copilot inside the Codespace. Framed throughout as **generate, then interrogate**: predict what the code will do before running it, read the diff rather than the summary, write the test that would catch it being wrong.

The vehicle is the linking task — join collisions to traffic counts to get **rates rather than counts**.

**The join, as verified against the data.** The collision subset as currently built has no road identifier at all, so the intended failure mode did not exist. Adding `first_road_class` and `first_road_number` to the subset — a change to `scripts/build_subsets.py` and a rebuild from the raw downloads, which are still on disk — creates a join that fails in exactly the right way:

- The student must build the key from two columns and a code lookup (`3` + `58` → `A58`, `1` + `62` → `M62`, `2` + `1` → `A1(M)`), which is fiddly, and which an agent does well.
- Joined naively on road name, **97.3% of the 20,485 collisions match**. The join looks like a complete success.
- But 10,422 of those matches are unclassified roads, where the collision's key is `U` and the traffic counts also carry `U` — as a *bucket label for all minor roads*, not a road. Half the matched rows are joined to an aggregate, and the resulting rate is meaningless.
- The honest join is to major roads only: 10,060 collisions on motorways, A, A(M) and B roads, where the key names a real road.

So the exercise is not "get the join to work" — it works immediately. It is "the join reports 97% matched; is the number it produces true?" That is the stage's whole thesis, on real data, with a real answer.

**Everyone does a join.** Three of the eight slices have no usable denominator, which would have left those students with a third of the stage-2 work. Instead every student joins at **authority level**, which is always possible because every collision carries a local authority code, and the traffic counts carry authority totals. Students whose slice has a finer denominator — cyclists to `pedal_cycles`, a district to `all_motor_vehicles` — then compute the specific rate as well. Everyone meets the join and its silent failure; some get a better denominator out of it. Students on the slices with none reach a conclusion that is equally real: they can compare severity but cannot compute a rate they would defend, and must say so.

Handoffs build the second half: the join, the rate, and an honest paragraph on what the denominator does and does not support.

*Tutorial 2 (2h):* students complete a real task with an agent, then swap workbooks and break each other's analysis. The competence being built is finding the planted fault, not producing the code. Formative; the project remains the only assessed artefact.

### 7.7 The workbook

`my-analysis.ipynb`, created from a template in lesson 1, committed to the student's own repository, and the thing they demonstrate in stage 4.

Its sections appear as the week proceeds, each added by a handoff: the slice and why; first look; cleaning; description; the join; rates; what this does not show. It is theirs — not executed by CI, not stripped, not graded.

### 7.8 Language and register

Taken by the module lead. Every student reads this material in English, and for most of them English is a second language. **The course is to be understood in English first.** A Chinese glossary helps a reader past a word they do not know; it is not a parallel translation, and Chinese appears nowhere else in the module.

That makes the prose a design constraint, not a matter of taste. It binds lesson text, hint wording, check messages, the workbook template's prompts, and the site's pages:

- **One idea per sentence.** Short sentences. If a sentence needs a comma to hold two clauses together, it is usually two sentences.
- **Plain words over precise-sounding ones.** "Use" not "utilise", "about" not "regarding", "before" not "prior to".
- **Active voice**, and name who does the thing: "you filter the table", not "the table is filtered".
- **No idioms, no metaphors, no humour that depends on English.** "Bear in mind", "a stab at it", "down the line" all have to go.
- **Plain verbs over phrasal verbs** where one exists: "cancel" not "call off", "reduce" not "cut down on".
- **Every technical term is defined the first time it appears**, in one short sentence, and added to the glossary. A term is not optional vocabulary — `DataFrame`, `index`, `traceback` and `kernel` all need this.
- **No unexplained abbreviations.** Write it out once, then abbreviate.

This is a constraint a careful author meets and a hurried one does not, and most of the material will be written by someone who never read this page. So it is enforced mechanically as well as stated: a prose gate measures sentence length across lesson markdown and fails CI when the material drifts back towards this document's own register, which is too dense for the audience. The gate is a floor, not the goal — passing it is not the same as writing well for these readers.

### 7.9 Repository shape

```
notebooks/01-foundations/     lesson notebooks, standalone, CI-run
notebooks/02-ai-accelerated/  as above
notebooks/04-project/         my-analysis-template.ipynb
hints/01-foundations.yml      nudge / method / code | answer per exercise id
hints/02-ai-accelerated.yml
checks/expected.json          fixed answers for cwai.checks
src/cwai/hints.py             the hint() and reveal() renderers        (new)
src/cwai/slices.py            the eight canonical slice definitions    (new)
```

Changes to existing foundation code, all of them small and all best made before any lesson exists:

| File | Change |
|---|---|
| `scripts/build_subsets.py` | carry `first_road_class`, `first_road_number`; rebuild from `raw/` |
| `scripts/build_student_notebooks.py` | executable stub; fourth hint tier; corrected docstring |
| `src/cwai/checks.py` | the unattempted state; `check_slice()` |
| `scripts/run_notebooks.py` | confirm `raises-exception` is honoured |
| `checks/README.md` | one implementation, not two |

---

## 8. What is left to the builder

- Exact lesson count and pagination within each stage. The stage boundaries, the thread and the time budget are fixed; where the breaks fall is not.
- The specific exercises, their planted faults, and their hint wording.
- The order in which Python concepts are introduced, provided the first cell assumes nothing and `pandas` arrives only after functions.
- The workbook template's exact sections and prompts.
- Whether the slice choice is a notebook cell, a prompt in the template, or both.
- How the cohort's errors are harvested before tutorial 1.
- The exact wording and markup of the unattempted state, subject to §5's accessibility constraint.

## 9. Requires the module lead

- Confirmation that Copilot seats exist for both cohorts before stage 2 runs.
- Whether tutorial 2's workbook swap is acceptable given students work on different slices.
- Still outstanding from the foundation and now blocking the site deploy: the **accessibility contact**, and the **institution name** for the accessibility statement.

---

## 10. Decisions recorded on this design

Taken by the module lead:

1. One piece of analysis grown across the week, not standalone exercises.
2. Hints cycle in tiers in one place, with a reveal for the answer.
3. A shortlist of pre-vetted slices rather than a free choice.
4. The companion-workbook approach (§6, option 1).
5. The published site shows exercises as **unattempted, not wrong**.
6. **Plain English, understood in English first** (§7.8). Chinese stays in the glossary.

Taken by me, as the design's author, in response to the builder check:

7. Road-level join, with the two road columns added to the subset and the data rebuilt (§7.6).
8. Handoff checks recompute from canonical slice definitions in `cwai.slices` (§7.1, §7.4).
9. Executable stubs — `answer = ...` — and the dual mechanism for deliberately-failing cells (§7.4).
10. Everyone joins at authority level; finer denominators are a bonus (§7.6).
11. A fourth hint tier, `answer`, for prose model answers (§7.2).
12. No second, JavaScript implementation of the self-check (§7.2).
13. Git stays out; stage 2 teaches diff-reading from the agent's output (§3).
14. A `reveal()` helper so predict-before-you-run works on the site (§7.3).
15. `src/cwai/hints.py` and its render test are the plan's first task, because the spike artefact is gone (§7.2).
16. The language constraint is enforced by a prose gate in CI, not by a note (§7.8).

Corrected on this revision: the after-dark comparison is 31.75% against 27.75% in daylight, not against a "28.5% baseline", which does not reproduce.
