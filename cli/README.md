# Workspace CLI

A Python 3.10+ CLI for the repository leaves registered in Workspace's
repositories.json. There are no Python runtime dependencies. Git is required
for repository inspection and sync; GitHub CLI and OpenSSH are required for login.

## Install

After cloning the Workspace index, run `bash scripts/install-cli.sh` from its
root. This creates an isolated .venv-cli/, installs this package in editable
mode and links workspace into ~/.local/bin/. The installer adds that directory
to Bash/Zsh startup configuration only when it is missing from PATH. Open a
new shell if needed. Re-running the installer refreshes the installation.
It does not change system Python, log in, or clone any project repositories.

Alternatively, install this directory in your own Python virtual environment:

```sh
python3 -m pip install --editable ./cli
```

The normal macOS/Termux seed scripts include CLI installation and login; see
the root README. WORKSPACE_PYTHON and WORKSPACE_BIN_DIR can select a different
interpreter or command directory for install-cli.sh. An existing unrelated
workspace command in that directory is preserved and reported as a conflict.

## Commands and queries

```sh
workspace repo list
workspace repo list all -l 2
workspace repo list cohesian-tools
workspace repo status
workspace repo status cohesian/site
workspace repo status lucas-masiero -l 2
workspace repo fetch
workspace repo fetch cohesian-tools
workspace repo fetch cohesian/site
workspace repo check
workspace repo check cohesian-tools -l 3
workspace repo login
workspace sync index --add
workspace sync index --remove
workspace sync workdir --clone
workspace sync workdir --purge person/example
workspace trash init
workspace trash empty
```

list, status, fetch, check and the sync targets accept one optional query: all (the default), an exact
GitHub owner, or owner/name. Matching ignores case. The resulting tree retains
the local paths from the index; an owner filter uses the GitHub namespace,
not a local directory name. For example, cohesian matches cohesian/site and
cohesian/research, while cohesian-tools selects the tools namespace.

All registered leaves appear even when a repo has not been cloned. The index
repository itself is the tree root and is not a registered leaf. list reads
only the index; it works without Git or any local project checkouts.

`-l N` / `--level N` controls display depth, like tree. Root is level 0;
`-l 1` shows the project families. The default displays the complete tree.
Hidden descendants are summarized with repository counts and status symbols.
Depth never changes the query's scope: fetch and sync still process all selected
leaves, including those below the displayed level.

## Status always compares main

| Symbol | Meaning |
|---|---|
| ✅ | Local main equals origin/main, and the working tree is clean |
| 🔽 | Main is behind origin/main, with no ahead commits or local edits |
| 🔼 | Main is ahead and/or there are staged, unstaged or untracked edits; not behind |
| ⚠️ | Behind plus ahead/local edits, or a repository inspection/fetch error |
| ⚪ | Registered checkout has not been cloned; fetch skips it |

`main +N −M` reports committed differences; uncommitted work is indicated
separately. Work on another checked-out branch is labeled, but committed
comparisons remain main versus origin/main. Neither status nor fetch switches
branches. A missing main or origin/main is reported explicitly, with no fallback
to another branch. A checkout on a feature branch can have synced main while
that feature branch has its own unpublished commits.

Status does **not** contact GitHub. origin/main is the last fetched remote
reference; use fetch before status when you need current remote information.
fetch runs `git fetch origin` in existing matching standalone checkouts. It
does not clone, pull, merge, commit, push or reset working files. It verifies
each origin against the index and refuses symlinked/mismatched checkout paths.
Errors do not stop other selected repositories from being processed.

Commands exit 0 on success (including skipped absent checkouts), 1 on an
operation/configuration failure, 2 on usage errors, and 130 on interruption.
Ahead/behind/mixed states are information, not execution failures. login may
also return GitHub CLI's authentication exit code.

## Check the index against the workdir

`workspace repo check` is local and read-only. It compares registered paths
and GitHub origins, then discovers unregistered repositories under organization/,
personal/ and projects/. It does not inspect Git commit synchronization; use
status for that.

- ✅ The registered path contains a standalone checkout with the expected origin.
- ❌ Its checkout is absent or its target directory is empty.
- ⚠️ A new local repository is not indexed, or a path/origin cannot be matched.

Discovery stops at each .git boundary, avoiding dependencies, nested Git
objects and source internals. It skips symlinks, hidden directories,
node_modules and __pycache__. The index repo itself is excluded. Invalid or
non-GitHub origins are reported but cannot be registered automatically.
Check exits 1 when there are missing/new/blocked entries in the query, 0 when
all selected entries match. list/status/fetch continue to use only the index.

## Sync one side explicitly

| Command | Change |
|---|---|
| `workspace sync index --add` | Add discovered local repositories to repositories.json |
| `workspace sync index --remove` | Remove index entries whose checkouts are missing locally |
| `workspace sync workdir --clone` | Clone indexed repos that are absent locally |
| `workspace sync workdir --purge` | Move local repos absent from the index into .trash/ |

Each target accepts exactly one mode per call. With no mode, sync does nothing.
There is no combined all mode. The query still defaults to all and can select
an owner or owner/name; -l limits only the displayed result tree.

```sh
workspace sync index --add cohesian-tools
workspace sync index --remove person/old-project
workspace sync workdir --clone cohesian/site
workspace sync workdir -p person/unused-project
```

-p is the short alias for --purge. The result tree reports the actions taken.
Sync never commits/pushes, pulls, resets or switches an existing checkout.
Index add/remove preserve existing metadata and update the managed repository
table in ARCHITECTURE.md alongside repositories.json. Duplicate GitHub names,
nested routes and concurrent index edits are rejected; failed writes roll back.
Review and commit index changes yourself after running these commands.

Clone uses SSH authentication (repo login) and stages the checkout before
installing it at its indexed path. Existing nonempty directories and mismatched
origins are reported and preserved. An empty target directory can be filled.
Missing entries are removed only by explicit sync index --remove.

Purge preserves the complete checkout, Git history and uncommitted files at:

```text
.trash/
├── .workspace-trash.json
└── <timestamp-and-id>/
    └── personal/unused-project/
        ├── .git/
        └── ...
```

The original project path is preserved inside each uniquely named batch, and
the command reports its recovery path. To recover it, move that directory back
to its original vacant path. Purge refuses indexed paths/ancestors and linked
worktrees rather than breaking their external Git metadata.

## Trash

`workspace trash init` creates the ignored .trash directory idempotently.
Purge calls the same initializer automatically. `workspace trash empty`
**permanently deletes its saved contents**, retaining .trash and its ownership
marker. It does not touch active checkouts or the index. Emptying absent trash
does nothing. Populated unmanaged directories and symlinked trash/markers are
refused. Sync and trash operations share a lock to prevent overlapping edits.
If a process is killed, inspect any .workspace-sync.lock and recovery directory
before manually clearing a stale lock.

## Finding the workspace

The command looks for repositories.json in the current directory or its
parents, then beside its editable installation. It therefore works from
inside a project checkout or elsewhere after the standard local install.
To select another index explicitly:

```sh
workspace --root /path/to/Workspace repo status
```

WORKSPACE_ROOT is an alternative. An explicit --root takes precedence.

## GitHub login

login is device-wide; it has no repository query or tree depth. It reuses
working GitHub CLI + SSH authentication. Otherwise it runs GitHub CLI's
browser/device flow with SSH key setup, then tests SSH access. Confirm a new
host fingerprint using GitHub's official fingerprints. Credentials stay in
the GitHub CLI/SSH configuration, never in this repository or its index.

See [GitHub CLI login](https://cli.github.com/manual/gh_auth_login).
The bootstrap currently clones over SSH; existing HTTPS checkouts also work
with repository status/fetch when Git credentials are already configured.

## Development

From the Workspace root:

```sh
PYTHONPATH=cli/src python3 -m unittest discover -s cli/tests -v
bash -n scripts/install-cli.sh scripts/termux/setup.sh scripts/macos/setup.sh scripts/setup-termux.sh scripts/bootstrap.sh
```

Git tests use local bare remotes and temporary checkouts, never live GitHub
repositories. pull, push, content publishing and add-tool/add-essay remain
outside this CLI.
