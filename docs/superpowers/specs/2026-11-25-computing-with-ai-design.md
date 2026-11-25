# Computing with AI — module design

**Date:** 2026-11-25
**Status:** Draft for approval
**Context:** Joint module, Southwest Jiaotong University (Chengdu) and the University of Leeds Institute for Transport Studies

---

## 1. Intent and why

Transport research is now substantially a computational discipline, and the students arriving into it increasingly have neither a programming background nor a realistic path to acquiring one inside a crowded curriculum. At the same time, AI coding tools have changed what "learning to program" has to mean: a student who cannot write a `for` loop from memory can nonetheless produce working analysis code, and a student who cannot *read* code carefully will produce confidently wrong analysis without noticing.

This module exists to take transport students from no Python at all to a position where they can carry out a credible piece of computational transport work and, critically, know when it is wrong. It treats AI assistance as a core skill rather than a concession, and it treats verification as the discipline that makes AI assistance safe.

The deeper goal is epistemic rather than technical. By the end, a student should have the reflex of asking "how would I know if this were wrong?" before trusting a number — whether that number came from their own code, from an agent, or from a neural network. That reflex is what makes the stretch topics (reinforcement learning, computer vision, vision-based safety models) approachable later rather than mystifying.

### Why now

The module is part of an active SWJTU–Leeds ITS collaboration and must be deliverable to a mixed cohort in an intensive block. Students retain perpetual access to the Codespace afterwards, so the material has a second life as a reference the cohort returns to during dissertations and projects.

### What success looks like

- A student with no prior programming experience finishes the block with a working notebook they wrote, understand, and can defend in a short presentation.
- That student can read a traceback, write a test, and explain what their model is actually doing.
- A student who returns to the Codespace six months later can still run everything.
- The teaching team can hand the material to a different tutor without a handover conversation.

---

## 2. Goals

1. **Zero-prerequisite entry.** No prior programming, no local environment setup, no assumption of pre-block preparation.
2. **Genuine engineering practice, early.** Debugging, assertions, `pytest`, modules and imports are introduced as part of learning to program, not as an advanced topic.
3. **AI assistance as verification skill.** Autocomplete and agentic coding are taught as generate-then-interrogate, with the interrogation as the assessed competence.
4. **Direct contact with the frameworks.** Students write a training loop in PyTorch and see the equivalent in Keras/TensorFlow. Not a wrapper library, not pseudocode.
5. **Two complementary surfaces, one source.** Notebooks in the Codespace for doing; the website for intuition, hints and self-checking. Neither can drift from the other.
6. **Two viable routes through the material.** A confident student lives in the Codespace and uses the site as reference. A less confident student works through the site and uses the Codespace as somewhere to type.
7. **Offline-survivable.** Everything needed is vendored in the repo. Network loss during the block costs a student minutes, not a session.
8. **Reachable from Chengdu.** No dependency on a service likely to be slow or blocked from mainland China.
9. **Open at the end.** Students finish pointed at reinforcement learning, computer vision and safety modelling, with one runnable taster each.

## 3. Non-goals

- Comprehensive Python coverage. Decorators, metaclasses, async, OOP beyond "a class is a thing with data and methods", and most of the standard library are out.
- Teaching the mathematics of deep learning. Intuition and vocabulary, yes; derivations, no.
- Depth in reinforcement learning or computer vision. These are destinations the module points at, not territory it covers.
- GPU training. Everything must run on Codespace CPU in minutes.
- Local installation support. The Codespace is the environment. Local setup is documented as unsupported.
- Chinese-language delivery. Material is in English; a bilingual glossary addresses technical vocabulary only.

## 4. Anti-goals

Things that would make this a failure even if it technically worked:

1. **Students who can prompt but not read.** A cohort that produces working code by delegation and cannot evaluate it has learned the dangerous half of the skill. This is the single most important failure to avoid.
2. **A notebook that only works with a tutor in the room.** The notebooks carry the teaching; a student working alone at 22:00 must be able to get unstuck.
3. **Widgets as decoration.** An interactive element that is fun but teaches nothing costs build time and student attention, and makes the site feel like a toy.
4. **A site and notebooks that disagree.** In a block with no slack, contradictory material on day three is unrecoverable.
5. **A deep-learning session that becomes a typing exercise.** Copying a training loop without understanding any of it is worse than not reaching PyTorch at all.
6. **Projects that are all the same.** If the studios produce twenty variations of the worked example, the open-ended framing has failed.

---

## 5. Constraints

### Hard constraints

| Constraint | Detail |
|---|---|
| Contact time | 3 tutorials × 2 hours, 2 studios × 3 hours. **12 hours total.** |
| Format | Intensive block. All sessions within one or two weeks. |
| Prior knowledge | None. Zero Python assumed. |
| Pre-block work | **Cannot be relied upon.** Any warm-up material is optional. |
| Self-study | Students have full days during the block; budget ~20–25 hours. Total module ~35 hours. |
| Delivery surfaces | GitHub Pages site; GitHub Codespace with perpetual student access. |
| Language | English. |
| Data | Vendored in the repository. Licences must permit redistribution. |
| Compute | Codespace CPU only. |
| Assessment | Project: a working notebook demonstrated live, plus a short presentation. |
| AI tooling | **GitHub Copilot.** Anthropic services are not available in mainland China, so Claude-based agents are out. Supported path is Copilot inside the Codespace. |
| Release model | **Everything released at once.** No phased rollout. Students progress at their own pace and revisit afterwards. |
| Availability | Always-on is a stated preference: material must work outside the block, indefinitely. |

### Consequences of 12 contact hours

Two hours cannot teach Python fundamentals and will not try. The tutorials are **not** where learning happens. Students arrive having worked through notebooks; sessions are diagnosis, live debugging of the cohort's actual errors, and the small number of ideas that do not survive being read silently.

This inverts the usual authoring priority. Notebook quality is the primary determinant of whether the module works. Tutorial plans are thin by design.

### Soft constraints and known risks

- **Network reachability.** A Codespace container runs outside mainland China, so from inside it PyPI, Hugging Face and Google-hosted weights behave roughly as they would in Leeds. The fragile links are what students reach *from* Chengdu: `github.io` Pages and the Codespace connection itself. Hence vendored data and a site that works degraded.
- **Codespaces quota.** Free personal accounts receive limited core-hours per month. "Perpetual access" needs GitHub Education benefits or organisation-paid Codespaces. **Flagged for the teaching team to confirm; the design assumes it is resolved.**
- **No open Chinese transport data.** There is no Chengdu open data portal publishing transport feeds, no public GTFS, and the DiDi GAIA Chengdu trajectories require application under unclear terms. UK data is the fallback spine. SWJTU colleagues may supply Chinese data later, so the data layer is built to accept a drop-in dataset behind the same loader interface.
- **Intensive block has no recovery slack.** A student who falls behind on day two is behind for the block. Every notebook must be self-checking, and every session must begin with a way back in.

---

## 6. Approaches considered

### Option 1 — One source, rendered twice *(chosen)*

Notebooks are canonical. The website is generated from them, with interactive widgets and support material layered at chosen points.

- **For:** Drift is structurally impossible. The site doubles as a readable fallback when the Codespace is unreachable. Lowest maintenance burden for a small teaching team.
- **Against:** Risks a site that reads like a notebook dump with widgets bolted on.

### Option 2 — Two deliberate surfaces

A hand-built site teaching concepts and intuition, with widgets as the centrepiece; notebooks as pure practice with no exposition.

- **For:** Best pedagogy if both artefacts are excellent. Genuinely complementary by construction.
- **Against:** Double authoring, and the two will drift. In a block with no slack, a notebook that contradicts the site is expensive. Rejected on maintenance risk.

### Option 3 — Browser-executable site

JupyterLite/Pyodide so the site runs real Python; the Codespace reserved for deep-learning sessions.

- **For:** Strongest network resilience — a student with a failing Codespace connection still writes code.
- **Against:** PyTorch and TensorFlow do not run in Pyodide, so two runtimes would need explaining. First page load is tens of megabytes, which is the worst possible property for Chengdu. Rejected.

### Decision

**Option 1 as the backbone, with Option 2's discipline about widgets.** Single source for consistency and offline fallback, but widgets authored as real interactive pieces placed only where intuition is the demonstrable bottleneck — roughly eight to ten across the module, not one per page.

The division of labour: **site for why and what it feels like; notebooks for doing it and getting it wrong.** Each points at the other at specific moments rather than in general.

Crucially, the site also carries what is awkward in a notebook: **progressive hints, worked solutions and answer-checking.** This keeps notebooks uncluttered and gives the two surfaces a pedagogical reason to both exist.

---

## 7. The design

### 7.1 Tooling decisions

These were made by the author rather than chosen by the module lead, and are recorded as such.

| Choice | Decision | Why |
|---|---|---|
| Site generator | **Quarto** | Native notebook rendering, clean HTML widget embedding, mature GitHub Pages deployment. |
| Widget implementation | **Plain client-side JavaScript** (vanilla + Canvas/SVG; `d3` only where it earns it) | GitHub Pages is static. `ipywidgets` need a live kernel, which the site does not have. |
| Environment | **devcontainer + `uv`** | Reproducible; resolves in seconds rather than minutes if ever rebuilt. |
| Python | **3.12** | Current, well-supported by PyTorch and TensorFlow at time of writing; builder should confirm. |
| DL frameworks | **PyTorch primary, Keras 3 / TensorFlow secondary** | PyTorch for the hand-written training loop; Keras for the contrast of the same model in fewer lines. |
| Testing | **`pytest`** | Introduced in stage 1 as a normal part of writing code. |
| Teaching package | **`src/cwai/`** installed editable | Gives students a real module to import, so "writing a module" is demonstrated rather than described. |
| Geospatial | **`geopandas` + `networkx`**; `osmnx` optional | Keep the dependency tree small enough to rebuild reliably. |
| Hint/check mechanism | **Client-side, site-only** | No server. Checks compare normalised student output against stored expected values. |
| Agentic coding tool | **GitHub Copilot, agent mode, inside the Codespace** | Module lead's call. Claude Code is unavailable in mainland China. Copilot is reachable and provisionable through GitHub Education. |

### 7.2 The data spine

The thread the module lead identified, and the organising principle of the whole module: **one dataset understood properly → datasets linked → a network and a model on top.**

| Dataset | Licence | Role |
|---|---|---|
| **DfT GB Road Traffic Counts** | OGL v3.0 | Traffic volume. Exposure denominator. Tabular fundamentals. |
| **STATS19 road safety data** | OGL v3.0 | Collisions, casualties, vehicles with location and severity. The module's spine. |
| **OpenStreetMap extracts** (Chengdu, Leeds) | ODbL | Road network and metro. Spatial and graph work. Repo carries ODbL terms. |
| **Seeded synthetic data** | Generated in-repo | Sensor time series, trajectories. See below. |
| **Street-level imagery** (small curated set) | CC BY-SA, Mapillary-sourced | Vision taster only. Builder to verify per-image licensing. |

**Rejected on licensing:** METR-LA and PEMS-BAY (no clear licence on original release); GTSRB (mirrors claim GPL-3.0 the original authors never stated); KITTI (CC BY-NC-SA 3.0 plus an academic-use-only note that does not cleanly reconcile — permissible in an isolated, separately-licensed subdirectory if a later need arises, but not used by default).

**Synthetic data is a feature, not a fallback.** Real data supplies whatever bugs it happens to contain. Seeded generators let the material plant the exact failure a lesson needs at the exact moment it is needed: a sensor that silently fails overnight, a test set deliberately contaminated, a distribution that shifts halfway through the year. In a block with no recovery slack, the student must hit a specific wall on cue.

**Data layer requirements:**
- All loading goes through `cwai.data` with a consistent signature, so a dataset supplied later by SWJTU colleagues drops in without rewriting notebooks.
- `data/README.md` documents provenance, licence and attribution per source. This doubles as teaching material: licence hygiene is a competence transport researchers need.
- Subsets sized so a full clone stays comfortably fast on a poor connection. Target total vendored data well under 100 MB; builder to set the exact budget.

### 7.3 Module structure

Four stages. Notebooks carry the teaching; sessions carry the confidence.

#### Stage 1 — Programming from first principles → **Tutorial 1**

Python through transport data from the first cell. Variables, types, collections, loops, conditionals, functions; then modules and imports; then `pandas`. Engineering practice woven in rather than appended: reading a traceback, `assert`, the debugger, and `pytest` on the student's own functions.

The dataset is STATS19 for one area and a few years. The work is to read it, clean it, and distrust it — missing values, implausible coordinates, a severity field whose coding changed.

*Tutorial 1 (2h):* live debugging of errors the cohort actually hit, harvested from their notebooks. Plus the two ideas that do not survive silent reading — most likely mutation/aliasing and what a function's scope actually is.

#### Stage 2 — AI-accelerated and agentic workflows → **Tutorial 2**

Autocomplete first, then agentic coding. Framed throughout as **generate, then interrogate**: predict what the code will do before running it, read the diff rather than the summary, and write the test that would catch it being wrong.

The vehicle is the linking task: join STATS19 to traffic counts to compute collision *rates* rather than counts. The joining logic is genuinely fiddly, agents are genuinely good at it, and the result is genuinely easy to get silently wrong — a mismatched key that drops half the rows and still returns a plausible number.

*Tutorial 2 (2h):* students complete a real task with an agent, then swap notebooks and break each other's analysis. The competence being built is finding the planted fault, not producing the code. This is formative only — the project is the sole assessed artefact (see §9, item 2).

#### Stage 3 — Direct machine learning → **Tutorial 3**

Tensors, shapes and broadcasting; autograd; a training loop written by hand in PyTorch; then the same model in Keras for contrast. Train/validation/test, overfitting, and metrics that survive class imbalance — which matters, because serious-injury collisions are rare and accuracy is a liar.

Two tasks on the spine: predict collision severity from conditions (classification), and forecast flow from a sensor series (regression).

*Tutorial 3 (2h):* a tensor-shape and leakage clinic. Every student brings a model that trains; the session is about finding out which ones learned nothing.

#### Stage 4 — Project → **Studios 1 and 2**

Open projects on student-chosen questions. Deliverable: a working notebook demonstrated live, plus a short presentation.

*Studio 1 (3h):* scoping. Narrowing an ambition to something achievable, a data reality check, and a skeleton notebook that runs end to end with placeholder results before any real work begins.

*Studio 2 (3h):* progress and rehearsal. Debugging clinic, then presentation practice with the specific question every student must be able to answer: *how do you know this is right?*

Scaffolding provided: a project template repository, a scoping worksheet, and a bank of starting points at three difficulty levels — not worked examples, which would collapse the cohort onto one project.

#### Stretch — where this goes next

Three short optional notebooks, each with one runnable taster, clearly marked as beyond the module: reinforcement learning (signal control on a toy network), computer vision (a small classifier on street imagery), and vision-based safety models (what a detection model outputs and why that is not yet a safety claim). These exist so the vocabulary is familiar when students meet it in a dissertation.

### 7.4 Widgets

Eight to ten, each justified by a specific bottleneck. Candidates, in rough teaching order:

1. **Traceback explorer** — click each part of a real Python error to see what it tells you.
2. **DataFrame playground** — filter and group without writing code, to build the mental model before the syntax.
3. **Join visualiser** — two tables, draggable keys, rows visibly lost to an inner join.
4. **Leakage demo** — split a dataset, watch a contaminated split produce a beautiful, meaningless score.
5. **Gradient descent** — a loss surface with a learning-rate slider. Divergence should be one drag away.
6. **Shape and broadcasting calculator** — type two shapes, see whether they broadcast and what comes out.
7. **Threshold and confusion matrix** — on imbalanced collision data, so accuracy can be seen lying.
8. **Capacity slider** — train and validation error diverging as model capacity grows.
9. **Convolution kernel** — a kernel dragged over a street scene.
10. **Spot the planted bug** — agent-produced code with a real fault; find it before revealing.

Each has a stated learning objective in its source file. A widget that cannot state one does not ship.

### 7.5 Site support layer

Beyond rendered notebooks and widgets, the site carries what notebooks do badly:

- **Progressive hints** — nudge, then method, then solution, each behind a click. Students report that *hints* are what let them work alone at night.
- **Self-check** — expected output and normalised answer comparison, client-side, no server.
- **Bilingual glossary** — technical terms paired with Chinese equivalents. Delivery is in English, and vocabulary is the real barrier rather than grammar.
- **Degraded-mode reading path** — every notebook readable in full on the site, so a student with a dead Codespace connection loses minutes rather than a morning.

### 7.6 Repository structure

```
.devcontainer/          devcontainer.json, postCreate
notebooks/
  00-warmup/            optional, no dependency
  01-foundations/
  02-ai-accelerated/
  03-machine-learning/
  04-project/
  90-stretch/
data/
  README.md             provenance, licence, attribution per source
  stats19/
  dft-counts/
  osm/
  synthetic/
  LICENSES/
scripts/                seeded generators, subsetting, data refresh
src/cwai/               teaching package: data, plotting, checks
tests/                  tests of the teaching package
site/                   Quarto project
  widgets/              one directory per widget
docs/superpowers/specs/
```


### 7.7 Solutions, hints and self-checking

**Module lead's decision:** solutions are open. The repository is public, and students are expected to check their work against known truths whenever they want.

- Each notebook has cells tagged `solution`. The student notebook ships with these stripped to a stub so an exercise is still an exercise on first contact; the full version is one click away on the site and plainly present in the repository.
- The site's hint layer escalates in three tiers — **nudge** (what to look at), **method** (the approach in prose, no code), **worked code** — all available on demand. The tiers exist so the smallest useful intervention is easy to find, not to withhold anything.
- **This changes how anti-goal 1 is defended, and the change is load-bearing.** Once answers are open, "write code that outputs X" stops being a meaningful exercise, because copying is always available and often the rational move. The defence cannot be scarcity, so it has to be exercise design. The weight moves onto tasks where having the answer does not short-circuit the learning:
  - **Predict before you run.** The cell asks what the output will be, then reveals it. The answer being available is the entire point.
  - **Find the fault.** Working-looking code with a planted error. Knowing where it was is only useful after you have looked.
  - **Explain why.** A short written answer the student compares against a model answer themselves.
  - **Verify someone else's.** Given an analysis and the claim drawn from it, decide whether the claim actually holds.
- The real check on understanding is the studio demonstration and the one question every student must be able to answer: *how do you know this is right?* That cannot be copied, which is what makes open solutions safe.
- Consequence: no two-repository split is needed (§9). One public tree, which is substantially simpler to build and maintain.
- CI must verify that the student render contains no solution cells, and that every exercise carries at least a nudge and a method hint.

### 7.8 Version control and material distribution

**Author's call:** minimal git, taught as a tool rather than as a topic.

- Each student gets their own Codespace from a template repository. Project work lives in their own repository from day one, which is also how it is submitted and demonstrated.
- Stage 1 includes one short notebook on `clone`, `pull`, `add`, `commit`, `push` and reading a diff — roughly 20 minutes. Justified because stage 2 depends on reading diffs, and because a fix must be able to reach students mid-block.
- **Fixes ship as new files, never as edits to a file a student may have modified.** A corrected notebook arrives as `03b-...` with a note, so `git pull` cannot conflict with their work. This constrains authoring: notebooks must be independently runnable.
- Branching, merging, rebasing and pull requests are out of scope.

### 7.9 Accessibility

**Author's assumption, to be corrected if wrong:** the site falls under the Public Sector Bodies Accessibility Regulations and must meet **WCAG 2.2 AA**, with a published accessibility statement.

Consequences, which bind before the first widget is written:

- Widgets are **DOM and SVG based, not Canvas**, so their content sits in the accessibility tree.
- Every widget has a keyboard path — arrow keys for any slider or drag — and a text-equivalent view presenting the same information as a table or as prose.
- This costs roughly 1.5 to 2 times as much per widget. The widget count is therefore a ceiling to cut from rather than a target to hit: six excellent accessible widgets beat ten inaccessible ones.

### 7.10 Compute ceilings

Design to the floor rather than the hope: **2-core, 8 GB Codespace, no GPU, no guarantee of prebuilds.**

- Every training example in stage 3 must complete in **under two minutes** on that machine. This caps dataset size, model size and epoch count, and those caps are inputs to writing the notebooks rather than discoveries to be made during a dry run.
- PyTorch and TensorFlow are multi-gigabyte and cannot be vendored. The offline guarantee therefore covers **data and material, not the environment.** The material states this plainly rather than implying the container is bulletproof: if a rebuild is needed, it is a long download.
- Keras and TensorFlow appear for **contrast only** — one model, read and run, not a parallel track. This keeps the image smaller and the cognitive load lower. If image size becomes a problem, TensorFlow is the first thing cut.

### 7.11 Imagery and personal data

The vision taster must not create a data-protection problem. CC BY-SA licensing resolves copyright, not privacy, and identifiable faces and vehicle registrations redistributed in a university repository are a separate issue.

**Author's call:** the vendored vision set contains **no identifiable people or vehicle registrations** — selected for that property, blurred where necessary, with the blurring script kept in `scripts/`. If a clean set of sufficient quality cannot be assembled, the taster falls back to synthetically rendered street scenes, which serves the teaching purpose at some cost in realism.

---

## 8. What is left to the builder

Deliberately open:

- Exact notebook count and the split of material between them, within the four stages. The stage boundaries and their learning objectives are fixed; the pagination is not.
- Which area STATS19 and DfT counts are subset to, and across which years. West Yorkshire is the obvious default for an ITS-authored module, but the builder should pick what produces the cleanest teaching examples.
- Precise widget list from the candidates above, and their visual design.
- Exact synthetic data generators and the faults planted in each.
- Tutorial-by-tutorial facilitation notes, including how the cohort's real errors get harvested before each session.
- Project starting-point bank contents.
- Total vendored data size budget.

---

## 9. Answers from the teaching team

Resolved in the design conversation of 2026-11-25.

| Question | Answer | Effect on the design |
|---|---|---|
| Agentic tool access | **Assume GitHub Copilot.** Claude is not available in mainland China. | Stage 2 is built on Copilot agent mode inside the Codespace. Seat provisioning via GitHub Education remains an action for the teaching team. |
| Module descriptor | **None known to exist.** The module will be adapted over time rather than built once. | No external wording to match. Outcomes are stated in the material so a descriptor can be derived from it later. Maintainability is a first-class requirement, not a nicety. |
| Release model | **Release everything at once.** Students progress at their own pace and revisit later. Colleagues in mainland China will test before release. | No phasing, so the full scope is the first deliverable. Notebooks must not depend on session attendance or on each other's completion. A China reachability check becomes a release gate (§10). |
| Delivery mode | **Everyone in one room.** | The tutorial designs stand as written: error harvesting, notebook swapping and the live clinic all assume co-presence. |
| Repository | **Public, with solutions deliberately exposed** so students can check against known truths. | One public tree, no two-repository split. Shifts the defence of anti-goal 1 onto exercise design (§7.7). |

### Still outstanding, for the teaching team rather than the builder

1. **Delivery date.** No longer blocks sequencing, since nothing is phased, but it sets the build budget.
2. **Copilot seat provisioning** for both cohorts, including whether SWJTU students can be enrolled in GitHub Education.
3. **Codespaces quota** sufficient for perpetual access, and whether prebuilds are available (§7.10).
4. Whether SWJTU-supplied Chinese data will arrive, and in what form.
5. Cohort size and the number of demonstrators available in sessions.

---

## 10. Release gate: verification before the block

Because everything ships at once and there is no recovery slack during the block, the following must pass before release. Colleagues in mainland China are the only people who can confirm the first three.

1. **Reachability from Chengdu.** The Pages site loads at acceptable speed; a Codespace opens and stays connected; Copilot responds inside it.
2. **Cold-start path.** A student with a fresh GitHub account reaches a running notebook without help, and without a local install.
3. **Degraded mode.** With the Codespace unreachable, the site alone still supports reading every notebook and every hint tier.
4. **Full clean run.** Every notebook executes top to bottom on a 2-core container inside the stated time ceilings, from a fresh clone, with no network access beyond what is documented.
5. **Self-paced integrity.** Each notebook runs independently of whether earlier ones were completed, so a student who skips ahead or returns months later is not blocked.
6. **Accessibility.** Every shipped widget has a keyboard path and a text-equivalent view (§7.9).
7. **Licence hygiene.** `data/README.md` accounts for every vendored file with provenance, licence and attribution; ODbL notice present; no identifiable people or vehicle registrations in imagery (§7.11).
