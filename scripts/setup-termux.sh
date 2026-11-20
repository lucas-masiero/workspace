#!/usr/bin/env bash
# Configure Termux tooling and GitHub authentication.
# Does not clone the workspace project repositories.
set -euo pipefail

if ! command -v pkg >/dev/null 2>&1; then
  printf 'ERROR: This setup script is intended for Termux (pkg is missing).\n' >&2
  exit 1
fi

printf 'Updating Termux package metadata...\n'
pkg update -y
printf '\nInstalling/verifying packages (safe to repeat)...\n'
pkg install -y openssh git gh python nodejs

mkdir -p -- "$HOME/.ssh"
chmod 700 "$HOME/.ssh"

KEY=""
for candidate in "$HOME/.ssh/id_ed25519" "$HOME/.ssh/id_rsa"; do
  if [[ -f "$candidate" ]]; then
    KEY="$candidate"
    break
  fi
done

if [[ -z "$KEY" ]]; then
  KEY="$HOME/.ssh/id_ed25519"
  printf '\nNo SSH key found. Creating an Ed25519 key...\n'
  printf 'Choose a passphrase when prompted (recommended).\n'
  ssh-keygen -t ed25519 -f "$KEY" -C "termux@$(hostname)"
fi

if [[ ! -f "$KEY.pub" ]]; then
  printf '\nPublic key missing; attempting to derive it from the private key...\n'
  ssh-keygen -y -f "$KEY" > "$KEY.pub"
fi
chmod 600 "$KEY"
chmod 644 "$KEY.pub"

# GitHub's SSH success message is returned with exit status 1; use the message.
ssh_check() {
  local output
  output="$(ssh -o ConnectTimeout=10 -o BatchMode=yes -o StrictHostKeyChecking=yes -T git@github.com 2>&1)" || true
  [[ "$output" == *"successfully authenticated"* ]]
}

if ssh_check; then
  printf '\n[OK] GitHub SSH authentication already works.\n'
else
  printf '\nAdd this PUBLIC key to GitHub -> https://github.com/settings/keys\n\n'
  cat -- "$KEY.pub"
  printf '\nNever upload/share your private key (%s).\n' "$KEY"
  read -r -p 'Have you added this public key to GitHub? [y/N] ' answer
  case "$answer" in
    y|Y|yes|YES) ;;
    *) printf 'Key registration not confirmed. Rerun this script after adding it.\n'; exit 0 ;;
  esac

  printf '\nTesting SSH. If asked about the GitHub host key, verify its fingerprint first:\n'
  printf 'https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/githubs-ssh-key-fingerprints\n'
  output="$(ssh -o ConnectTimeout=10 -T git@github.com 2>&1)" || true
  printf '%s\n' "$output"
  if [[ "$output" != *"successfully authenticated"* ]]; then
    printf 'ERROR: GitHub SSH verification failed. Correct the key setup and rerun.\n' >&2
    exit 1
  fi
fi

if gh auth status --hostname github.com >/dev/null 2>&1; then
  printf '[OK] GitHub CLI already authenticated.\n'
else
  printf '\nSigning into GitHub CLI (web/device flow)...\n'
  gh auth login --hostname github.com --git-protocol ssh --web --skip-ssh-key
  gh auth status --hostname github.com
fi

printf '\nTermux setup complete. No repositories were cloned.\n'
printf 'To populate the workspace, run: bash scripts/bootstrap.sh\n'
