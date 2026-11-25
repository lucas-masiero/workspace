# Workspace Index

This repository is the **index and root of a local tree of independent Git repositories**. It contains the map and documentation of the workspace, **not the source code** of the projects it indexes.

The three top-level project families are:

- **`organization/`** — `cohesian/{arch,core,site}`, `cohesian-tools/{front,site,tools}` and `cohesian-essays/{front,site,essays}`.
- **`personal/`** — Resume, Portfolio and personal repositories (`repositories/`).
- **`projects/`** — independent project namespaces such as Bookly Up.

These directories are ignored by the root Git repository. Their leaves are
independent checkouts, not submodules. Namespace/container directories are not
repositories themselves.

## Where to look

- **[`AGENTS.md`](AGENTS.md)** — instructions for AI agents working anywhere in this workspace.
- **[`ARCHITECTURE.md`](ARCHITECTURE.md)** — the complete repository tree, GitHub mappings, responsibilities, and information flows.
- **[`repositories.json`](repositories.json)** — machine-readable, canonical map from local paths to GitHub repositories.
- **[`cli/README.md`](cli/README.md)** — installable Python CLI: repository trees, main status, fetch, index/workdir reconciliation, trash and GitHub login.
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
workspace repo check
workspace repo login
workspace sync index --add
workspace sync index --remove
workspace sync workdir --clone
workspace sync workdir --purge owner/repo
workspace trash init
workspace trash empty
```

Queries default to all, or select an exact GitHub owner or owner/name.
Inspection/fetch/sync commands render the local repository tree. -l N
limits its displayed depth; collapsed groups summarize their hidden leaves.
The query, not depth, selects which repositories are fetched.

Status compares local main with cached origin/main: ✅ synced, 🔽 behind,
🔼 ahead/local edits, ⚠️ mixed or error. ⚪ means not cloned. Run fetch before
status to refresh remote information. fetch updates references without pulling
or changing branches/files. Missing checkouts are skipped. See cli/README.md
for exact status rules, root discovery and installation options.

check compares the index to checkouts: ✅ matching, ❌ missing, ⚠️ new or
blocked. It discovers independent Git roots within the three project families.
sync changes only the explicitly selected side: index --add/--remove registers
new local repos or drops missing entries; workdir --clone/--purge fills missing
checkouts or moves unregistered ones into recoverable .trash/. -p aliases
--purge. With no mode, sync does nothing; there is no combined all mode.
Index changes also update ARCHITECTURE.md's managed routing table.

trash init is idempotent and runs automatically on purge. trash empty
permanently clears saved trash contents. These operations never commit or push.

## Git boundaries

Running `git status` from `~/Workspace` inspects **only the index**. To inspect a project, enter that project or use `git -C`, for example:

```bash
git -C ~/Workspace/organization/cohesian-tools/tools/resumy status
```

Do not confuse the index's Git repository with any repository under `organization/`, `personal/` or `projects/`.

## Cohesian content publishing

[organization/cohesian/arch](organization/cohesian/arch/README.md) documents
ownership and publication formats. The main Site consumes only Core and links
to `tools.cohesian.org` and `essays.cohesian.org`.

Each domain has its own Front catalog and Astro Site. Author an entry in
`organization/cohesian-tools/front` or `organization/cohesian-essays/front`,
validate and push it, then run `npm run fetch` and `npm run build` inside that
domain's Site. `fetch -- --local` previews sibling edits. Builds use committed
`fetched/` snapshots and need no source credentials.

Individual tools and essays have no presentation packages. Core stays agnostic;
its visual adaptation belongs to the gateway. Portfolio consumes native Resume
and gateway settings/assets/Core data, keeping its own presentation adapters.
The former combined `cohesian/front` is an archived compatibility source, not
part of the active local index. Workspace-level add-tool/add-essay functions
remain a future step.
