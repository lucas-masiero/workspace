#!/usr/bin/env bash
# Seed a new Termux installation; cloning repositories remains a separate step.
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
WORKSPACE_DIR="$(cd -- "$SCRIPT_DIR/../.." && pwd -P)"

if ! command -v pkg >/dev/null 2>&1; then
  printf 'This setup requires Termux (pkg is missing).\n' >&2
  exit 1
fi
pkg update -y
pkg install -y openssh git gh python python-pip python-ensurepip-wheels nodejs

bash "$WORKSPACE_DIR/scripts/install-cli.sh"
"$WORKSPACE_DIR/.venv-cli/bin/workspace" repo login
printf '\nTermux is ready. To clone missing registered repos:\n'
printf 'bash "%s/scripts/bootstrap.sh"\n' "$WORKSPACE_DIR"
