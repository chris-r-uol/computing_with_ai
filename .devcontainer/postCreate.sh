#!/usr/bin/env bash
set -euo pipefail

# uv is not in the base image
pip install --user uv
export PATH="$HOME/.local/bin:$PATH"

uv sync --all-groups

# Smoke check: Quarto is installed from PyPI (quarto-cli) in the dev group
uv run quarto --version
