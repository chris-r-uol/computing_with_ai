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
exercise. Answers are open on purpose, so when you are stuck use the hint tiers
on the site (nudge, then method, then code) before opening `notebooks/`.

## Maintenance

CI has two workflows. `tests` runs lint, unit tests and the licence audit.
`notebooks` executes every notebook in a fresh kernel, on every push and pull
request and **weekly on Mondays**; the weekly run is what catches a dependency
drifting under material nobody has touched.

**GitHub automatically disables scheduled workflows in a public repository after
about 60 days without repository activity.** That is exactly the situation the
weekly run exists for, so check the Actions tab now and then. If the schedule has
been disabled, re-enable it there (Actions, `notebooks`, Enable workflow), or run
it by hand with "Run workflow" (both workflows support `workflow_dispatch`). Any
commit to the repository also resets the clock.
