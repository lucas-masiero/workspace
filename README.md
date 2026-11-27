# Workspace

An index of independent Git repositories. Workspace owns the catalog and device
setup notes; [Workit](https://github.com/cohesian-tools/workit) is the separate
Go CLI that operates on it. There is no CLI implementation in this repository.

## Install Workit

With Go 1.25+ and Git available:

```sh
go install github.com/cohesian-tools/workit@v0.1.0
export PATH="$(go env GOPATH)/bin:$PATH"
workit --version
```

Go builds the binary for your device. Its default installation directory is
`$(go env GOPATH)/bin`; if you set GOBIN, put that directory on PATH instead.
Workit is public; access to the private repositories listed here is separate.

## A new Termux phone

Run inside Termux's home directory, rather than Android shared storage:

```sh
pkg update
pkg install git gh golang openssh

go install github.com/cohesian-tools/workit@v0.1.0
export PATH="$(go env GOPATH)/bin:$PATH"

gh auth login --git-protocol https
gh auth setup-git
gh repo clone lucas-masiero/workspace "$HOME/Workspace"
cd "$HOME/Workspace"

workit sync workdir add --dry-run
workit sync workdir add
workit repo status
```

Add the PATH line to your shell startup file to keep it in future sessions.
The TOML index is already included: do not run `workit init` in this checkout.
`sync workdir add` creates missing namespaces/checkouts from that index. It
preserves existing repositories and never pulls, resets or deletes them.
HTTPS is the default for future clones; existing SSH origins remain unchanged.

## macOS

With Homebrew configured, `brew install git gh go` supplies the prerequisites.
Then use the same go install, GitHub authentication, clone and sync sequence.
Individual projects may need additional runtimes such as Node.js or Python;
those are not requirements of Workit or this index.

## Optional Bash helpers

The manual flow above is enough. Existing script entry points stay small:

- `bash scripts/termux/setup.sh` installs prerequisites with pkg and prints next steps.
- `bash scripts/macos/setup.sh` installs prerequisites with Homebrew.
- `bash scripts/install-cli.sh` delegates to the pinned go install command.
- `bash scripts/bootstrap.sh --dry-run` delegates to `workit -C <root> sync workdir add --dry-run`.
- `bash scripts/bootstrap.sh` applies that Workit clone plan.

Seeds do not install a Python CLI, authenticate or clone automatically. There is
no independent Bash manifest parser or repository-management implementation.

## Catalog and layout

[.workit.toml](.workit.toml) is the only active machine-readable inventory:

```text
organization/
  cohesian/{arch,core,site}
  cohesian-tools/{front,site,tools/<repository>}
  cohesian-essays/{front,site,essays/<repository>}
personal/
  resume
  portfolio
  repositories/{leetcode,pj-homesolution}
projects/
  bookly-up/{auth,booking,payment}
```

The 29 workstation (`w`) nodes are independent Git checkouts. Namespace (`n`)
parents are explicit; the root (`r`) is this index, even though it is itself
versioned with Git. Source families are ignored here, not nested repositories
in this history. `scripts/` and `tests/` are excluded management directories.
[ARCHITECTURE.md](ARCHITECTURE.md) provides the human routing table and ownership.

## Daily use

Scope follows your current directory, or the explicit `-C` path:

```sh
workit repo status
workit -C organization/cohesian-tools repo fetch
workit -C organization/cohesian/site repo status
workit sync index add --dry-run
workit sync workdir add --dry-run
```

Status reads each current branch's cached upstream; it does not always compare
main or contact GitHub. Run fetch explicitly to refresh tracking references.
`sync index add/prune` changes registration. `sync workdir add/remove` changes
physical content. Review plans before applying them. Workdir remove moves extras
to `.void/`; only `void clean` permanently deletes managed quarantine entries.
Workit never automatically commits/pushes an index edit. Update the human routing
table in ARCHITECTURE.md when registration changes.

Each source has its own Git boundary. Root `git status` examines only this index;
use `git -C <repository path>` for a particular source checkout.

## Migration from the Python CLI

Workit replaces `workspace`. The old source is retained in Git history, and
[.migration/repositories.v1.json](.migration/repositories.v1.json) preserves the
original 27 mappings and their role descriptions exactly. It is a historical
snapshot, not a second inventory. Workit adds its own source as the 28th entry.

Existing checkouts, working edits, `.trash/` and `.venv-cli/` are preserved.
Ignored Python cache/build metadata left by the old editable installation is
kept locally under `.migration/python-local/`, outside Workit discovery. The
old `workspace` executable/virtual environment is retired and not maintained.
Use `workit`; you can remove the old installation separately when convenient.
Old `.trash/` data is not automatically converted into the new `.void` format.

Old owner/name query flags and fixed-main status semantics do not carry over;
select directories with cd/-C and use Workit's current-branch/upstream status.

## Cohesian publishing

The gateway consumes Core. Tools and Essays have independent Front catalogs and
Sites. Each domain Site uses `npm run fetch` then `npm run build` from committed
`fetched/` snapshots. Individual tools and essays remain presentation-agnostic.
The detailed contracts belong to organization/cohesian/arch; Workit changes
workspace operations, not these publishing relationships.

## Checks

Developer checks for this repository (Python 3.11+ for TOML parsing in tests):

```sh
python3 -m unittest discover -s tests
```

Tests use fake package tools and temporary roots. They never install packages,
clone private repositories or modify shell profiles. Workit's own Go tests and
release checks belong to its source repository.
