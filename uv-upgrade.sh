uv lock --upgrade
uv sync --upgrade
# to pick up a new 3.14.x patch: uv python upgrade 3.14
# to move to a new Python version: uv python install 3.15, then rm -rf .venv && uv sync -p 3.15

