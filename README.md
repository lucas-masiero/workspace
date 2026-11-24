# Workspace Index

This repository is the **index and root of a local tree of independent Git repositories**. It contains the map and documentation of the workspace, **not the source code** of the projects it indexes.

The three top-level project families are:

- **`Cohesian/`** — the Cohesian organization: its architecture (`arch`), principles (`core`), central presentation catalog (`front`), public site (`site`), books/research (`essays`), and software (`tools`).
- **`Profile/`** — personal resume data and portfolio
- **`Projects/`** — personal projects

The `Cohesian/`, `Profile/`, and `Projects/` directories are deliberately ignored by this repository's `.gitignore`. They are populated locally by cloning independent repositories. They are **not** Git submodules, and the index does not track their content.

## Where to look

- **[`AGENTS.md`](AGENTS.md)** — instructions for AI agents working anywhere in this workspace.
- **[`ARCHITECTURE.md`](ARCHITECTURE.md)** — the complete repository tree, GitHub mappings, responsibilities, and information flows.
- **[`repositories.json`](repositories.json)** — machine-readable, canonical map from local paths to GitHub repositories.
- **[`cli/README.md`](cli/README.md)** — installable Python CLI: repository trees, main status, fetch and GitHub login.
- **[`scripts/termux/setup.sh`](scripts/termux/setup.sh)** — seed Termux with pkg, install the CLI and authenticate GitHub.
- **[`scripts/macos/setup.sh`](scripts/macos/setup.sh)** — seed macOS with Homebrew, install the CLI and authenticate GitHub.
- **[`scripts/install-cli.sh`](scripts/install-cli.sh)** — install just the CLI on an already configured computer/phone.
- **[`scripts/bootstrap.sh`](scripts/bootstrap.sh)** — create missing directories and clone missing project repositories; does not install packages.

## Getting started

The index itself is cloned or unpacked into a directory such as `~/Workspace`. The local project trees may initially be absent; that's expected.

On a new **Termux** installation:

```bash
cd ~/Workspace
bash scripts/termux/setup.sh
bash scripts/bootstrap.sh
```

On **macOS**:

```bash
cd ~/Workspace
bash scripts/macos/setup.sh
bash scripts/bootstrap.sh
```

Both seed scripts install Git, GitHub CLI, Python and Node.js, install the
workspace command in an isolated local environment, then run workspace repo
login. Termux also installs OpenSSH, python-pip and python-ensurepip-wheels through pkg; macOS uses
Homebrew and the system SSH client. If Homebrew is missing, its official
interactive installer runs first. Seeds do not clone project repos. The
original scripts/setup-termux.sh entry point also remains usable.

The bootstrap is idempotent: existing valid repositories are left alone, even if behind their remotes. It neither fetches nor pulls, and never deletes unexpected directories. Re-running it fills in missing repositories.

**Initial clone:** This repository must already exist locally before either script can run. Clone lucas-masiero/workspace into `~/Workspace` first. A private index requires GitHub access before the clone (or a downloaded archive); the seed then prepares the remaining tooling and verifies authentication.

On Termux, keep the clone in its home directory, such as ~/Workspace. For an
already prepared environment, run only bash scripts/install-cli.sh.

## Daily repository commands

```sh
workspace repo list
workspace repo list cohesian-tools -l 3
workspace repo status
workspace repo status cohesian/site
workspace repo fetch
workspace repo fetch lucas-masiero
workspace repo login
```

Queries default to all, or select an exact GitHub owner or owner/name.
All three inspection/fetch commands render the registered local tree. -l N
limits its displayed depth; collapsed groups summarize their hidden leaves.
The query, not depth, selects which repositories are fetched.

Status compares local main with cached origin/main: ✅ synced, 🔽 behind,
🔼 ahead/local edits, ⚠️ mixed or error. ⚪ means not cloned. Run fetch before
status to refresh remote information. fetch updates references without pulling
or changing branches/files. Missing checkouts are skipped. See cli/README.md
for exact status rules, root discovery and installation options.

## Git boundaries

Running `git status` from `~/Workspace` inspects **only the index**. To inspect a project, enter that project or use `git -C`, for example:

```bash
git -C ~/Workspace/Cohesian/tools/resumy status
```

Do not confuse the index's Git repository with any repository under `Cohesian/` or `Profile/`.

## Cohesian content publishing

[Cohesian/arch](Cohesian/arch/README.md) documents the architecture.
[Cohesian/front](Cohesian/front/README.md) owns shared tool/essay schemas and
instance.json + assets entries. After validating and pushing Front, run
`npm run fetch` and `npm run build` inside Cohesian/site. Its build uses a
committed snapshot, so source credentials are needed only for fetch.
Workspace-level add-tool/add-essay functions are a future step.

Presentation belongs to consumers: Site owns the Core view; Portfolio owns
Resume and Cohesian views. Both consumers use fetched/ and the same fetch/build
commands. Source tools, essays, Resume and Site expose no front packages.
See Cohesian/arch/README.md for the updated data boundaries.
