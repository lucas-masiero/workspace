#!/usr/bin/env bash
# Optional convenience wrapper. Workit is distributed as a separate Go module.
set -euo pipefail
if ! command -v go >/dev/null 2>&1; then
  printf 'Install Go 1.25+ first (Termux: pkg install golang).\n' >&2
  exit 1
fi
WORKIT_VERSION="${WORKIT_VERSION:-v0.1.0}"
go install "github.com/cohesian-tools/workit@$WORKIT_VERSION"
workit_bin="$(go env GOBIN)"
if [[ -z "$workit_bin" ]]; then
  workit_path="$(go env GOPATH)"
  workit_bin="${workit_path%%:*}/bin"
fi
"$workit_bin/workit" --version
printf 'Installed in %s. Add this directory to PATH if needed.\n' "$workit_bin"
