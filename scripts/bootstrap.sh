#!/usr/bin/env bash
# Compatibility entry point; all discovery/planning/cloning belongs to Workit.
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
WORKSPACE_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd -P)"
if ! command -v workit >/dev/null 2>&1; then
  printf 'Install Workit first: go install github.com/cohesian-tools/workit@v0.1.0\n' >&2
  exit 1
fi
exec workit -C "$WORKSPACE_DIR" sync workdir add "$@"
