"""The workspace index is the only repository inventory."""
from dataclasses import dataclass
import json
import os
from pathlib import Path, PurePosixPath
import re


class WorkspaceError(Exception):
    """A user-facing configuration or operation error."""


@dataclass(frozen=True)
class Repository:
    path: str
    github: str


def discover_root(explicit: str | None = None) -> Path:
    selected = explicit or os.environ.get("WORKSPACE_ROOT")
    if selected:
        root = Path(selected).expanduser().resolve()
        if not (root / "repositories.json").is_file():
            raise WorkspaceError(f"No repositories.json in {root}")
        return root
    # Editable installs can also locate their index when invoked from elsewhere.
    for start in (Path.cwd().resolve(), Path(__file__).resolve().parent):
        for directory in (start, *start.parents):
            if (directory / "repositories.json").is_file():
                return directory
    raise WorkspaceError("Workspace not found. Use --root PATH or set WORKSPACE_ROOT.")


def load_repositories(root: Path) -> list[Repository]:
    try:
        data = json.loads((root / "repositories.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise WorkspaceError(f"Cannot read repositories.json: {error}") from error
    if not isinstance(data, dict) or data.get("version") != 1 or not isinstance(data.get("repositories"), list):
        raise WorkspaceError("Expected repositories.json version 1 with a repositories list")
    repos, paths, names = [], set(), set()
    for item in data["repositories"]:
        if not isinstance(item, dict):
            raise WorkspaceError("Every repository must be an object")
        relative, github = item.get("path"), item.get("github")
        if not isinstance(relative, str) or not isinstance(github, str):
            raise WorkspaceError("Repository path and github must be strings")
        parts = relative.split("/")
        if (len(parts) < 2 or parts[0] not in {"Cohesian", "Profile", "Projects"}
                or any(not re.fullmatch(r"[A-Za-z0-9._-]+", p) or p in {".", ".."} for p in parts)
                or PurePosixPath(relative).as_posix() != relative):
            raise WorkspaceError(f"Unsafe repository path: {relative!r}")
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", github):
            raise WorkspaceError(f"Invalid GitHub owner/name: {github!r}")
        if relative.casefold() in paths or github.casefold() in names:
            raise WorkspaceError(f"Duplicate repository path or GitHub name: {relative}")
        paths.add(relative.casefold())
        names.add(github.casefold())
        repos.append(Repository(relative, github))
    if any(a.startswith(b + "/") for a in paths for b in paths if a != b):
        raise WorkspaceError("Nested repository targets are unsupported")
    return sorted(repos, key=lambda repo: repo.path.casefold())


def select(repositories: list[Repository], query: str) -> list[Repository]:
    query = query.casefold()
    if query == "all":
        return repositories
    if not re.fullmatch(r"[a-z0-9_.-]+(?:/[a-z0-9_.-]+)?", query):
        raise WorkspaceError("Query must be all, owner, or owner/name")
    matches = [repo for repo in repositories if (
        repo.github.casefold() == query if "/" in query
        else repo.github.split("/")[0].casefold() == query
    )]
    if not matches:
        raise WorkspaceError(f"No registered repositories match {query!r}")
    return matches
