# Workspace CLI

A Python 3.10+ CLI for the repository leaves registered in Workspace's
repositories.json. There are no Python runtime dependencies. Git is required
for status/fetch; GitHub CLI and OpenSSH are required for login.

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
workspace repo login
```

list, status and fetch accept one optional query: all (the default), an exact
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
Depth never changes the query's scope: fetch still processes all selected
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
repositories. check, pull, push, content publishing and add-tool/add-essay are
outside this first CLI version.
