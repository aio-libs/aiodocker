#! /bin/bash
# Runs the test suite via uv's managed environment.
# If you bootstrapped the project with pip instead, activate the venv and run
# `python3 -m pytest "$@"` directly.
uv run --no-sync python3 -m pytest "$@"
