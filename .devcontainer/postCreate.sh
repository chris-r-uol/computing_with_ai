#!/usr/bin/env bash
set -euo pipefail

# uv is not in the base image. `pip install --user` puts it in ~/.local/bin,
# which is not on PATH, and the export below dies with this script — so
# devcontainer.json also adds that directory to remoteEnv.PATH. Without it the
# shell a student gets has no uv, and every instruction in the repository
# begins `uv run`.
pip install --user uv
export PATH="$HOME/.local/bin:$PATH"

uv sync --all-groups

# Smoke check: Quarto is installed from PyPI (quarto-cli) in the dev group
uv run quarto --version
