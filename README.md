# Computing with AI

Teaching material for a university Python and AI module: students work through
notebooks that build from Python foundations, through AI-accelerated coding,
to machine learning and a final project.

## Environment

The GitHub Codespace defined in `.devcontainer/` is the only supported
environment. It provides Python 3.12, all dependencies and Quarto, and needs
at least 2 cores and 8 GB of memory.

**Local installation is unsupported.** Please open the repository in a
Codespace rather than setting up Python on your own machine.

## Which folder is mine?

Work in **`student/`**. Its notebooks have the exercises with the answers
removed, so you write the code yourself. `notebooks/` holds the full authoring
copies with every solution in place: opening those instead quietly removes the
exercise. Answers are open on purpose, so when you are stuck work up through
the hint tiers (nudge, then method, then code) before opening `notebooks/`.

The hints themselves are in `hints/`, one file per stage. The site interface
that will serve them one tier at a time is still to be built, so for now read
them from those files.

## Maintenance

CI has three workflows, plus `checks`, which holds the one list of checks the
other two call rather than restating.

- `tests` runs that list — lint, `actionlint`, unit tests, the
  student-notebook check and the licence audit — on every pull request and on
  a push to `main`.
- `notebooks` executes every notebook in a fresh kernel, on the same triggers
  and **weekly on Mondays**. A second job in the weekly run re-resolves the
  dependencies from `pyproject.toml` instead of installing `uv.lock`, which is
  what catches a dependency drifting under material nobody has touched; it
  reports separately and does not fail the workflow.
- `site` builds the Quarto site and publishes it to GitHub Pages on a push to
  `main`. It runs the same check list first with `CWAI_PUBLISH_GATE=1`, which
  turns on the checks that only a publication has to pass — today, that the
  accessibility statement has no unfinished TODO left in it. Nothing is
  deployed unless they pass.

Pushing to a branch other than `main` runs nothing: open a pull request.

**GitHub automatically disables scheduled workflows in a public repository after
about 60 days without repository activity.** That is exactly the situation the
weekly run exists for, so check the Actions tab now and then. If the schedule has
been disabled, re-enable it there (Actions, `notebooks`, Enable workflow), or run
it by hand with "Run workflow" (all three workflows support
`workflow_dispatch`). Any commit to the repository also resets the clock.
