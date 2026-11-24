# Agent Instructions — Workspace Index

This directory is a **routing index for multiple independent Git repositories**, not a monorepo or a shared application. The root Git repository is responsible only for this index's documentation, manifest, and scripts. `Cohesian/`, `Profile/`, and `Projects/` are separate local project trees and are ignored by the root `.gitignore`.

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
- **Cohesian `site`** publishes the organization catalog and exposes a smaller Cohesian presentation/card that **Profile `portfolio`** consumes.
- **Profile `resume`** owns structured personal and career data; its `resume.json` conforms to a schema used by **`resumy`** to generate a formatted `resume.pdf`.
- **Profile `portfolio`** presents personal data from `Profile/resume` and the Cohesian presentation from `Cohesian/site`; do not duplicate either source of truth without cause.
- **Projects** is an independant node from the rest, containing personal projects from different scopes and owners.

Do **not** infer technical specifics—API routes, file paths, schema names, export formats, build tools, or deploy targets—from these conceptual relationships. Inspect the actual projects before implementing integration changes.

## Editing the index itself

Keep `ARCHITECTURE.md` readable for humans and `repositories.json` precise for machines. When adding, removing, or relocating repositories, update both together, and update the root `.gitignore` if a new top-level project family is introduced. The setup script configures Termux; the bootstrap script materializes the repository map. Keep those responsibilities separate.
