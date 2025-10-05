#!/usr/bin/env bash
set -Eeuo pipefail

# One-click launcher for the Arena Rules Overlay
# - Creates a venv if missing
# - Installs/updates dependencies
# - Starts the overlay

# Resolve repository directory (where this script lives)
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd -P)"
VENV_DIR="$SCRIPT_DIR/.venv"
REQUIREMENTS_FILE="$SCRIPT_DIR/requirements.txt"
APP_FILE="$SCRIPT_DIR/overlay_rules.py"

have() { command -v "$1" >/dev/null 2>&1; }

# Choose Python interpreter
if have python3; then
  PY=python3
elif have python; then
  PY=python
else
  echo "Error: Python is not installed. Please install Python 3." >&2
  exit 1
fi

# Create venv if missing
if [[ ! -d "$VENV_DIR" ]]; then
  echo "[overlay] Creating virtual environment..."
  "$PY" -m venv "$VENV_DIR"
fi

# Activate venv
# shellcheck source=/dev/null
source "$VENV_DIR/bin/activate"

# Ensure pip is up to date and install deps
if [[ -f "$REQUIREMENTS_FILE" ]]; then
  echo "[overlay] Installing dependencies (this may take a moment)..."
  python -m pip install --upgrade pip wheel setuptools >/dev/null
  pip install -r "$REQUIREMENTS_FILE"
else
  echo "Warning: requirements.txt not found; attempting to run anyway." >&2
fi

# Launch the overlay
echo "[overlay] Starting overlay... (press 1 to toggle, Ctrl+C to quit)"
exec python "$APP_FILE"
