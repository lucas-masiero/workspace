#!/usr/bin/env bash
# Seed macOS prerequisites; Workit installation and repository cloning are explicit.
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
WORKSPACE_DIR="$(cd -- "$SCRIPT_DIR/../.." && pwd -P)"

if [[ "$(uname -s)" != Darwin ]]; then
  printf 'This setup requires macOS.\n' >&2
  exit 1
fi

BREW="$(command -v brew || true)"
if [[ -z "$BREW" ]]; then
  for candidate in /opt/homebrew/bin/brew /usr/local/bin/brew; do
    if [[ -x "$candidate" ]]; then
      BREW="$candidate"
      break
    fi
  done
fi
if [[ -z "$BREW" ]]; then
  printf 'Installing Homebrew using its official interactive installer...\n'
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  for candidate in /opt/homebrew/bin/brew /usr/local/bin/brew; do
    if [[ -x "$candidate" ]]; then BREW="$candidate"; break; fi
  done
fi
if [[ -z "$BREW" ]]; then
  printf 'Homebrew is unavailable. See https://docs.brew.sh/Installation\n' >&2
  exit 1
fi
eval "$("$BREW" shellenv)"
"$BREW" install git gh go

# Persist Homebrew for the next shell on a freshly seeded Mac.
brew_line="eval \"\$($BREW shellenv)\" # Cohesian Workspace Homebrew"
case "${SHELL:-/bin/zsh}" in
  */bash) brew_profile="$HOME/.bash_profile" ;;
  *) brew_profile="$HOME/.zprofile" ;;
esac
if [[ ! -f "$brew_profile" ]] || ! grep -Fqx -- "$brew_line" "$brew_profile"; then
  printf '\n%s\n' "$brew_line" >> "$brew_profile"
fi

printf '\nPrerequisites ready. Next:\n'
printf '%s\n' \
  'go install github.com/cohesian-tools/workit@v0.1.0' \
  'export PATH="$(go env GOPATH)/bin:$PATH"' \
  'gh auth login --git-protocol https' \
  'gh auth setup-git' \
  'workit sync workdir add --dry-run' \
  'workit sync workdir add'
