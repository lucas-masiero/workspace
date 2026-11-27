#!/usr/bin/env bash
# Optional prerequisites only; Go installation, login and cloning stay explicit.
set -euo pipefail
if ! command -v pkg >/dev/null 2>&1; then
  printf 'This setup requires Termux (pkg is missing).\n' >&2
  exit 1
fi
pkg update -y
pkg install -y openssh git gh golang
printf '\nPrerequisites ready. Next:\n'
printf '%s\n' \
  'go install github.com/cohesian-tools/workit@v0.1.0' \
  'export PATH="$(go env GOPATH)/bin:$PATH"' \
  'gh auth login --git-protocol https' \
  'gh auth setup-git' \
  'workit sync workdir add --dry-run' \
  'workit sync workdir add'
