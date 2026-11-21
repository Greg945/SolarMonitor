#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
VENV_PYTHON="$PROJECT_DIR/.venv/bin/python"
REQUIREMENTS_HASH_FILE="$PROJECT_DIR/.requirements.sha256"

cd "$PROJECT_DIR"

if ! timeout 30s git -c credential.interactive=never pull --ff-only; then
    echo "SolarMonitor: Git-Update nicht möglich; starte mit dem vorhandenen Stand weiter." >&2
fi

CURRENT_REQUIREMENTS_HASH="$(sha256sum requirements.txt | awk '{print $1}')"
INSTALLED_REQUIREMENTS_HASH=""
if [[ -f "$REQUIREMENTS_HASH_FILE" ]]; then
    INSTALLED_REQUIREMENTS_HASH="$(cat "$REQUIREMENTS_HASH_FILE")"
fi

if [[ ! -x "$VENV_PYTHON" || "$CURRENT_REQUIREMENTS_HASH" != "$INSTALLED_REQUIREMENTS_HASH" ]]; then
    if [[ ! -x "$VENV_PYTHON" ]]; then
        python3 -m venv "$PROJECT_DIR/.venv"
    fi
    "$VENV_PYTHON" -m pip install --upgrade pip
    "$VENV_PYTHON" -m pip install -r requirements.txt
    printf '%s\n' "$CURRENT_REQUIREMENTS_HASH" > "$REQUIREMENTS_HASH_FILE"
fi
