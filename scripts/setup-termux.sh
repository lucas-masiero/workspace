#!/usr/bin/env bash
# Keep the original entry point working; the seed now lives under termux/.
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
exec bash "$SCRIPT_DIR/termux/setup.sh" "$@"
