"""Compare the registered routes with independent local repository roots."""
from dataclasses import dataclass
from pathlib import Path

from .manifest import FAMILIES, Repository, WorkspaceError, validate_manifest
from .repositories import Result, checkout, local_path, repository_name


@dataclass(frozen=True)
class Entry:
    repo: Repository
    state: str
    result: Result
    registered: bool


def missing_path(root: Path, repo: Repository) -> bool:
    directory = local_path(root, repo.path)
    return not directory.exists() or (directory.is_dir() and not any(directory.iterdir()))


def inspect(root: Path, repositories: list[Repository]) -> list[Entry]:
    entries = []
    registered = {repo.path.casefold(): repo for repo in repositories}
    for repo in repositories:
        try:
            if missing_path(root, repo):
                entries.append(Entry(repo, "missing", Result("❌", "missing checkout", True), True))
            else:
                checkout(root, repo)
                entries.append(Entry(repo, "match", Result("✅", "matches index"), True))
        except (OSError, WorkspaceError) as error:
            entries.append(Entry(repo, "blocked", Result("⚠️", str(error), True), True))

    def visit(directory: Path) -> None:
        relative = directory.relative_to(root).as_posix()
        if directory.is_symlink():
            return
        try:
            marker = directory / ".git"
            if marker.exists() or marker.is_symlink():
                # Stop at every Git boundary, including invalid or unregistered ones.
                if relative.casefold() not in registered:
                    repo = Repository(relative, "unknown origin")
                    try:
                        repo = Repository(relative, repository_name(directory))
                        validate_manifest({"version": 1, "repositories": [{"path": repo.path, "github": repo.github}]})
                        entries.append(Entry(repo, "new", Result("⚠️", "new local repository; not indexed", True), False))
                    except (OSError, WorkspaceError) as error:
                        entries.append(Entry(repo, "blocked", Result("⚠️", f"unregistered repository: {error}", True), False))
                return
            for child in sorted(directory.iterdir(), key=lambda p: p.name.casefold()):
                if child.name.startswith(".") or child.name in {"node_modules", "__pycache__"}:
                    continue
                if child.is_dir() and not child.is_symlink():
                    visit(child)
        except OSError as error:
            if relative.casefold() not in registered:
                entries.append(Entry(Repository(relative, "unknown origin"), "blocked", Result("⚠️", f"cannot inspect: {error}", True), False))

    for family in FAMILIES:
        directory = root / family
        if directory.is_dir() and not directory.is_symlink():
            visit(directory)
    return sorted(entries, key=lambda entry: entry.repo.path.casefold())
