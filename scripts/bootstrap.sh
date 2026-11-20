#!/usr/bin/env bash
# Materialize the repository tree described in ../repositories.json.
# Idempotent: never pull, reset, overwrite, or delete existing repositories.
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd -P)"
MANIFEST="$ROOT/repositories.json"

if [[ ! -f "$MANIFEST" ]]; then
  printf 'ERROR: Missing %s\n' "$MANIFEST" >&2
  exit 1
fi
if ! command -v git >/dev/null 2>&1; then
  printf 'ERROR: Git not found. Install Git first.\n' >&2
  exit 1
fi
if command -v python3 >/dev/null 2>&1; then
  PYTHON=python3
elif command -v python >/dev/null 2>&1; then
  PYTHON=python
else
  printf 'ERROR: Python 3 not found. Install Python first.\n' >&2
  exit 1
fi

ROUTES="$(mktemp)"
trap 'rm -f -- "$ROUTES"' EXIT

# Validate the *entire* manifest before creating any files or folders.
"$PYTHON" - "$MANIFEST" > "$ROUTES" <<'PY'
import json
import re
import sys
from pathlib import PurePosixPath

manifest_path = sys.argv[1]
with open(manifest_path, encoding="utf-8") as stream:
    manifest = json.load(stream)

if not isinstance(manifest, dict) or manifest.get("version") != 1:
    raise SystemExit("ERROR: Unsupported repositories.json version (expected 1)")
repos = manifest.get("repositories")
if not isinstance(repos, list):
    raise SystemExit("ERROR: repositories must be a list")

seen_paths = set()
for entry in repos:
    if not isinstance(entry, dict):
        raise SystemExit("ERROR: Every repository must be an object")
    path, github = entry.get("path"), entry.get("github")
    if not isinstance(path, str) or not isinstance(github, str):
        raise SystemExit("ERROR: path and github must be strings")
    parts = path.split("/")
    if (len(parts) < 2 or parts[0] not in {"Cohesian", "Profile"}
            or any(not re.fullmatch(r"[A-Za-z0-9._-]+", p) or p in {".", ".."} for p in parts)
            or PurePosixPath(path).as_posix() != path):
        raise SystemExit(f"ERROR: Unsafe or invalid project path: {path!r}")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", github):
        raise SystemExit(f"ERROR: Invalid GitHub owner/repo: {github!r}")
    if path in seen_paths:
        raise SystemExit(f"ERROR: Duplicate project path: {path}")
    seen_paths.add(path)

for path in seen_paths:
    if any(path.startswith(other + "/") for other in seen_paths if other != path):
        raise SystemExit(f"ERROR: Nested repository targets are not supported: {path}")

for entry in repos:
    print(f"{entry['path']}\t{entry['github']}")
PY

printf 'Workspace: %s\nManifest:  %s\n\n' "$ROOT" "$MANIFEST"
created=0
kept=0
blocked=0
failed=0

while IFS=$'\t' read -r relpath github; do
  [[ -n "$relpath" ]] || continue
  target="$ROOT/$relpath"
  url="git@github.com:$github.git"

  # Existing repositories (even outdated ones) are deliberately not touched.
  if [[ -d "$target" ]] && git -C "$target" rev-parse --show-toplevel >/dev/null 2>&1; then
    project_root="$(git -C "$target" rev-parse --show-toplevel)"
    if [[ "$project_root" == "$target" ]]; then
      printf '[KEEP]    %s\n' "$relpath"
      kept=$((kept + 1))
      continue
    fi
  fi

  if [[ -e "$target" || -L "$target" ]]; then
    printf '[BLOCKED] %s exists but is not a standalone Git repository; leaving it untouched\n' "$relpath" >&2
    blocked=$((blocked + 1))
    continue
  fi

  # Do not follow a symlink in any parent directory of a target.
  parent="$ROOT"
  safe_parent=1
  IFS='/' read -r -a parts <<< "$relpath"
  for ((i=0; i<${#parts[@]}-1; i++)); do
    parent="$parent/${parts[i]}"
    if [[ -L "$parent" ]]; then
      printf '[BLOCKED] %s: symlink parent %s\n' "$relpath" "$parent" >&2
      blocked=$((blocked + 1))
      safe_parent=0
      break
    fi
  done
  [[ "$safe_parent" -eq 1 ]] || continue

  mkdir -p -- "$(dirname -- "$target")"
  printf '[CLONE]   %-36s %s\n' "$relpath" "$url"
  if git clone -- "$url" "$target"; then
    created=$((created + 1))
  else
    printf '[FAILED]  Could not clone %s (check SSH and GitHub access)\n' "$github" >&2
    failed=$((failed + 1))
  fi
done < "$ROUTES"

printf '\nResult: %d cloned, %d kept, %d blocked, %d failed\n' "$created" "$kept" "$blocked" "$failed"
if ((blocked > 0 || failed > 0)); then
  exit 1
fi
