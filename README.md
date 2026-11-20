# Workspace Index

This repository is the **index and root of a local tree of independent Git repositories**. It contains the map and documentation of the workspace, **not the source code** of the projects it indexes.

The two top-level project families are:

- **`Cohesian/`** — the Cohesian organization: its principles (`core`), public site (`site`), books/research (`essays`), and software (`tools`).
- **`Profile/`** — personal resume data, portfolio, and projects.

The `Cohesian/` and `Profile/` directories are deliberately ignored by this repository's `.gitignore`. They are populated locally by cloning independent repositories. They are **not** Git submodules, and the index does not track their content.

## Where to look

- **[`AGENTS.md`](AGENTS.md)** — instructions for AI agents working anywhere in this workspace.
- **[`ARCHITECTURE.md`](ARCHITECTURE.md)** — the complete repository tree, GitHub mappings, responsibilities, and information flows.
- **[`repositories.json`](repositories.json)** — machine-readable, canonical map from local paths to GitHub repositories.
- **[`scripts/setup-termux.sh`](scripts/setup-termux.sh)** — install and configure the Termux environment; does not clone projects.
- **[`scripts/bootstrap.sh`](scripts/bootstrap.sh)** — create missing directories and clone missing project repositories; does not install packages.

## Getting started

The index itself is cloned or unpacked into a directory such as `~/Workspace`. The local project trees may initially be absent; that's expected.

On a new **Termux** installation:

```bash
cd ~/Workspace
bash scripts/setup-termux.sh
bash scripts/bootstrap.sh
```

On **macOS** (with Git, SSH authentication, and Python 3 already configured):

```bash
cd ~/Workspace
bash scripts/bootstrap.sh
```

The bootstrap is idempotent: existing valid repositories are left alone, even if behind their remotes. It neither fetches nor pulls, and never deletes unexpected directories. Re-running it fills in missing repositories.

**Initial clone:** This repository must already exist locally before either script can run. Once you publish the index to GitHub, clone it into `~/Workspace` first. A public index can be cloned over HTTPS before SSH is configured; a private index requires access first (or a downloaded archive).

## Git boundaries

Running `git status` from `~/Workspace` inspects **only the index**. To inspect a project, enter that project or use `git -C`, for example:

```bash
git -C ~/Workspace/Cohesian/tools/resumy status
```

Do not confuse the index's Git repository with any repository under `Cohesian/` or `Profile/`.
