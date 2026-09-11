#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UV_INSTALL_URL="https://docs.astral.sh/uv/getting-started/installation/"

if ! command -v uv >/dev/null 2>&1; then
    echo "Error: uv is not installed or not on PATH." >&2
    echo "Install uv from: ${UV_INSTALL_URL}" >&2
    exit 1
fi

cd "${ROOT_DIR}"
uv sync
uv run python setup.py "$@"
