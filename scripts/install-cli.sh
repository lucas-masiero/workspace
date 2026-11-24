#!/usr/bin/env bash
# Install only this index's CLI, in a local virtual environment.
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
WORKSPACE_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd -P)"
WORKSPACE_PYTHON="${WORKSPACE_PYTHON:-python3}"
WORKSPACE_BIN_DIR="${WORKSPACE_BIN_DIR:-$HOME/.local/bin}"
CLI_ENV="$WORKSPACE_DIR/.venv-cli"
CLI_LINK="$WORKSPACE_BIN_DIR/workspace"

if ! command -v "$WORKSPACE_PYTHON" >/dev/null 2>&1; then
  printf 'Python 3.10+ is required. Run the setup script for this device.\n' >&2
  exit 1
fi
"$WORKSPACE_PYTHON" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else "Python 3.10+ is required")'

if [[ -e "$CLI_LINK" || -L "$CLI_LINK" ]]; then
  if [[ ! -L "$CLI_LINK" || "$(readlink "$CLI_LINK")" != "$CLI_ENV/bin/workspace" ]]; then
    printf 'Refusing to replace %s. Choose another WORKSPACE_BIN_DIR.\n' "$CLI_LINK" >&2
    exit 1
  fi
fi

if [[ ! -d "$CLI_ENV" ]]; then
  "$WORKSPACE_PYTHON" -m venv "$CLI_ENV"
fi
"$CLI_ENV/bin/python" -m pip install --disable-pip-version-check --editable "$WORKSPACE_DIR/cli"
mkdir -p -- "$WORKSPACE_BIN_DIR"
ln -sfn -- "$CLI_ENV/bin/workspace" "$CLI_LINK"

# Make the command available in future default Bash/Zsh sessions, once.
case ":$PATH:" in
  *":$WORKSPACE_BIN_DIR:"*) ;;
  *)
    case "${SHELL:-}" in
      */zsh) shell_rc="$HOME/.zshrc" ;;
      */bash)
        if [[ "$(uname -s)" == Darwin ]]; then
          shell_rc="$HOME/.bash_profile"
        else
          shell_rc="$HOME/.bashrc"
        fi
        ;;
      *) shell_rc="" ;;
    esac
    if [[ -n "$shell_rc" ]]; then
      "$CLI_ENV/bin/python" - "$shell_rc" "$WORKSPACE_BIN_DIR" <<'PY'
from pathlib import Path
import shlex
import sys
rc, directory = Path(sys.argv[1]), sys.argv[2]
line = f'export PATH={shlex.quote(directory)}:"$PATH" # Cohesian Workspace CLI'
content = rc.read_text() if rc.exists() else ''
if line not in content.splitlines():
    with rc.open('a') as stream:
        stream.write('\n' + line + '\n')
PY
    fi
    printf '\nOpen a new shell to use workspace, or run: %s\n' "$CLI_LINK"
    ;;
esac
"$CLI_LINK" --version
printf 'CLI installed. Try: workspace repo list\n'
