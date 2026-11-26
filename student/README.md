# Your notebooks

Work in this folder. These notebooks have the exercises with the answers
removed. `notebooks/` holds the full copies with solutions, so opening those
instead removes the exercise. When stuck, work up through the hints (nudge,
then method, then code): they are in `hints/`, one file per stage, until the
site serves them a tier at a time.

These files are generated, so changes here are overwritten when they are built
again. Keep anything you want to hang on to in a copy of the notebook under
another name.

## Writing a cell that fails on purpose

A lesson may need a cell that raises an error, so students can read the
traceback. Give that cell both of these. First, add the `raises-exception` tag
to the cell. This keeps the notebook runner (`scripts/run_notebooks.py`) from
failing. Second, make `#| error: true` the first line of the cell. This keeps
the Quarto site render from failing. One alone is not enough: with only the
tag, the website does not build, and with only the option, the notebook runner
fails in CI. A test checks that the two always appear together.
