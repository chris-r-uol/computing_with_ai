#!/usr/bin/env bash
set -euo pipefail

# uv is not in the base image. `pip install --user` puts it in ~/.local/bin,
# which is not on PATH, and the export below dies with this script — so
# devcontainer.json also adds that directory to remoteEnv.PATH. Without it the
# shell a student gets has no uv, and every instruction in the repository
# begins `uv run`.
pip install --user uv
export PATH="$HOME/.local/bin:$PATH"

# --frozen: install exactly what uv.lock records, the versions CI tested.
# Not --locked, which CI uses: a stale lock must fail a CI run, but it must not
# fail a student's first Codespace at step one, with nothing they can do.
uv sync --frozen --all-groups

# Smoke check: Quarto is installed from PyPI (quarto-cli) in the dev group
uv run quarto --version
