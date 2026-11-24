# Agent Instructions — Workspace Index

This directory is a **routing index for multiple independent Git repositories**, not a monorepo or a shared application. The root Git repository owns this index's documentation, manifest, setup scripts and Python workspace CLI. `Cohesian/`, `Profile/`, and `Projects/` are separate local project trees and are ignored by the root `.gitignore`.

## Read first

1. Read [`README.md`](README.md) for the purpose and boundaries of this index.
2. Read [`ARCHITECTURE.md`](ARCHITECTURE.md) to understand the repository tree, ownership, and cross-project data flow.
3. Consult [`repositories.json`](repositories.json) to resolve a local path to its exact GitHub repository. Treat this file as the source of truth **for path-to-repository mappings**.
4. When working on a particular project, read that project's own documentation and instructions before changing its files.

## Routing and scope

- Determine **which project owns the requested change** before editing anything.
- Work inside the owning repository. Do not treat a root-level `git status`, commit, or push as applying to nested repositories.
- Do not add nested repositories to the index's Git history or convert them into submodules.
- Do not create, replace, reset, pull, or push repositories unless the user explicitly asks.
- Do not assume a missing repository is an error in the index; a checkout can contain only some projects. `scripts/bootstrap.sh` fills in missing clones when requested.
- Preserve existing project work, including uncommitted changes. Do not rewrite files merely to make their contents conform to this index.
- If a task spans repositories, explain the affected owners and contracts and make only the changes necessary to satisfy the task.
- If the manifest and the human-oriented documentation disagree about a repository path, use the manifest for routing and flag the inconsistency rather than silently guessing.

## Architectural rules

- **Cohesian `core`** owns the organization's foundational principles.
- **Cohesian `arch`** owns the organization architecture and workflows.
- **Cohesian `front`** owns the central tool/essay presentation catalog and schemas. Site consumes this registry and Core; it no longer imports individual works’ front folders. Read Front’s own AGENTS.md before adding instances or assets.
- **Cohesian `essays` and `tools`** are namespace containers of independent implementation/authoring repositories. They remain factual sources for the presentations; preserve their histories and local work.
- **Cohesian `site`** consumes Core reference data and Central Front through its own fetched/ snapshot. It owns Core’s visual adaptation and its native app settings, and does not export a self-presentation package.
- **Profile `resume`** owns native CV JSON, photo/theme and its matching PDF/JSON artifacts, generated with Resumy. It has no frontend export or dependency on Site catalogs.
- **Profile `portfolio`** consumes native Resume and Site data into its own fetched/ snapshot and owns their presentation adapters, schemas, cover/card assets and styles. Keep producer nodes agnostic; never require their own front folders.
- **Projects** is an independant node from the rest, containing personal projects from different scopes and owners.

Do **not** infer technical specifics—API routes, file paths, schema names, export formats, build tools, or deploy targets—from these conceptual relationships. Inspect the actual projects before implementing integration changes.

## Editing the index itself

Keep `ARCHITECTURE.md` readable for humans and `repositories.json` precise for machines. When adding, removing, or relocating repositories, update both together, and update the root `.gitignore` if a new top-level project family is introduced. Seeds configure Termux/macOS and install the CLI; bootstrap materializes the repository map. Keep those responsibilities separate.

Read cli/README.md before changing the CLI. list/status/fetch use only
repositories.json for inventory, with all, owner, or owner/name selection.
All share the local tree and -l display depth.
Status compares local main with cached origin/main and notes current worktree
edits without switching branches. Fetch refreshes origin; never automatically
pull/reset/merge/commit/push. Missing checkouts are normal. login delegates
interactive authentication to gh/SSH. Keep runtime dependencies in Python's standard library.
Test CLI changes with PYTHONPATH=cli/src python3 -m unittest discover -s cli/tests.
Seed scripts target Bash 3.2+ as well as Termux Bash; never upgrade system pip.

repo check is a read-only comparison/discovery under Cohesian/Profile/Projects;
stop scanning at Git boundaries and never follow symlinks. workspace sync is
a separate group: index --add/--remove and workdir --clone/--purge (-p).
Require one explicit mode per call; no mode is a no-op and there is no all mode.
Queries remain all, owner, or owner/name, with display-only depth.
Index mutations update the marked table in ARCHITECTURE.md as well as the JSON.
Preserve existing fields, files and checkouts; reject conflicting routes/origins.
Purge moves only unregistered repos to ignored .trash/, preserving their tree,
Git history and local edits. trash init is idempotent; trash empty explicitly
permanently clears only initialized Workspace trash. Never empty it incidentally
while implementing features. Tests use temporary roots and local Git remotes.

Both frontend consumers use fetched/ and npm run fetch / npm run build.
Use --local for unpublished sibling inputs. Keep Core unchanged as a reference
unless an explicit principle change is requested. Catalog schemas stay only
in Central Front and trusted consumer validators, never individual nodes.
