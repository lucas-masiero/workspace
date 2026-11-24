"""Explicit index add/remove and workdir clone/purge. Never commit or push."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import tempfile
from uuid import uuid4

from .inventory import inspect, missing_path
from .locking import workspace_lock
from .manifest import Repository, WorkspaceError, load_repositories, select, validate_manifest
from .repositories import Result, git, local_path, repository_name
from .trash import ensure_trash

TABLE_START = "<!-- workspace-repositories:start -->"
TABLE_END = "<!-- workspace-repositories:end -->"


def replace_index(root: Path, original: bytes, data: dict) -> None:
    """Replace the manifest and its managed documentation together, with rollback."""
    validate_manifest(data)
    replacements = {root / "repositories.json": (original, (json.dumps(data, indent=2, ensure_ascii=False) + "\n").encode())}
    architecture = root / "ARCHITECTURE.md"
    if architecture.exists():
        before = architecture.read_bytes()
        text = before.decode("utf-8")
        if text.count(TABLE_START) != 1 or text.count(TABLE_END) != 1 or text.index(TABLE_START) > text.index(TABLE_END):
            raise WorkspaceError("ARCHITECTURE.md needs one managed repository table; index unchanged")
        rows = ["| Local path | GitHub repository |", "|---|---|"]
        rows += [f"| `{item['path']}` | `{item['github']}` |" for item in data["repositories"]]
        start = text.index(TABLE_START) + len(TABLE_START)
        end = text.index(TABLE_END)
        after = text[:start] + "\n" + "\n".join(rows) + "\n" + text[end:]
        replacements[architecture] = (before, after.encode())
    if all(before == after for before, after in replacements.values()):
        return
    stage = Path(tempfile.mkdtemp(prefix=".workspace-sync-", dir=root))
    replaced, backups = [], {}
    retain = False
    try:
        for index, (target, (before, after)) in enumerate(replacements.items()):
            if target.is_symlink() or not target.is_file():
                raise WorkspaceError(f"Refusing to replace a non-regular index file: {target.name}")
            backup, ready = stage / f"backup-{index}", stage / f"ready-{index}"
            backup.write_bytes(before)
            backup.chmod(target.stat().st_mode & 0o777)
            ready.write_bytes(after)
            ready.chmod(target.stat().st_mode & 0o777)
            backups[target] = backup
            if target.read_bytes() != before:
                raise WorkspaceError(f"{target.name} changed during sync; rerun the command")
            os.replace(ready, target)
            replaced.append(target)
    except BaseException:
        for target in reversed(replaced):
            try:
                if target.read_bytes() != replacements[target][1]:
                    retain = True
                    continue
                os.replace(backups[target], target)
            except OSError:
                retain = True
        if retain:
            raise WorkspaceError(f"Index recovery files retained in {stage}; concurrent changes were preserved")
        raise
    finally:
        if not retain:
            shutil.rmtree(stage)


def read_index(root: Path) -> tuple[bytes, dict]:
    file = root / "repositories.json"
    if file.is_symlink():
        raise WorkspaceError("Refusing to edit a symlinked repositories.json")
    original = file.read_bytes()
    try:
        data = json.loads(original)
    except ValueError as error:
        raise WorkspaceError(f"Invalid repositories.json: {error}") from error
    validate_manifest(data)
    return original, data


def clone_repository(repo: Repository, target: Path) -> None:
    git(target.parent, "clone", "--", f"git@github.com:{repo.github}.git", str(target), timeout=60)


def materialize(root: Path, repo: Repository, clone=clone_repository) -> None:
    if not missing_path(root, repo):
        raise WorkspaceError("Checkout path is occupied; existing files were preserved")
    target = local_path(root, repo.path)
    target.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".workspace-clone-", dir=target.parent))
    try:
        prepared = stage / "checkout"
        clone(repo, prepared)
        if repository_name(prepared) != repo.github.casefold():
            raise WorkspaceError("Cloned origin does not match the index")
        if not missing_path(root, repo):
            raise WorkspaceError("Checkout path changed during clone; existing files were preserved")
        # POSIX rename also safely replaces an existing empty directory.
        os.rename(prepared, target)
    finally:
        shutil.rmtree(stage)


def quarantine(root: Path, repo: Repository, repositories: list[Repository]) -> Path:
    directory = local_path(root, repo.path)
    # Recheck the inventory immediately before removing a checkout from the tree.
    if any(item.path.casefold() == repo.path.casefold() or item.path.casefold().startswith(repo.path.casefold() + "/") for item in repositories):
        raise WorkspaceError("Path is indexed or contains indexed descendants; preserved")
    if repository_name(directory) != repo.github.casefold():
        raise WorkspaceError("Local origin changed during sync; checkout preserved")
    if not (directory / ".git").is_dir() or (directory / ".git").is_symlink():
        raise WorkspaceError("Linked worktree or external Git metadata; use Git worktree management explicitly")
    if sum(line.startswith("worktree ") for line in git(directory, "worktree", "list", "--porcelain").splitlines()) > 1:
        raise WorkspaceError("Repository has linked worktrees; preserved")
    trash = ensure_trash(root)
    destination = trash / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-") + uuid4().hex) / repo.path
    destination.parent.mkdir(parents=True)
    os.rename(directory, destination)
    return destination


def synchronize(root: Path, target: str, mode: str, query: str = "all", clone=clone_repository) -> tuple[list[Repository], dict[str, Result]]:
    if (target, mode) not in {("index", "add"), ("index", "remove"), ("workdir", "clone"), ("workdir", "purge")}:
        raise WorkspaceError("Use sync index --add/--remove or sync workdir --clone/--purge")
    with workspace_lock(root):
        original, data = read_index(root)
        registered = validate_manifest(data)
        inventory = inspect(root, registered)
        chosen = {repo.path for repo in select([entry.repo for entry in inventory], query)}
        missing = mode in {"remove", "clone"}
        targets = [entry for entry in inventory if entry.repo.path in chosen and (
            entry.registered and entry.state != "match" if missing else not entry.registered)]
        results = {entry.repo.path: entry.result for entry in targets}
        actionable = [entry for entry in targets if entry.state == ("missing" if missing else "new")]
        if target == "index" and mode == "remove":
            removed = {entry.repo.path for entry in actionable}
            # Match against the live filesystem again before changing the index.
            for entry in actionable:
                if not missing_path(root, entry.repo):
                    raise WorkspaceError("A missing checkout appeared during sync; index unchanged")
            data["repositories"] = [item for item in data["repositories"] if item["path"] not in removed]
            if removed:
                replace_index(root, original, data)
            for entry in actionable:
                results[entry.repo.path] = Result("✅", "removed missing entry from index")
        elif target == "index" and mode == "add":
            for entry in actionable:
                if repository_name(local_path(root, entry.repo.path)) != entry.repo.github.casefold():
                    raise WorkspaceError("A local origin changed during sync; index unchanged")
            data["repositories"] += [{"path": entry.repo.path, "github": entry.repo.github} for entry in actionable]
            if actionable:
                replace_index(root, original, data)
            for entry in actionable:
                results[entry.repo.path] = Result("✅", "added local repository to index")
        else:
            for entry in actionable:
                try:
                    if mode == "clone":
                        materialize(root, entry.repo, clone)
                        result = Result("✅", "cloned to indexed path")
                    else:
                        if (root / "repositories.json").read_bytes() != original:
                            raise WorkspaceError("Index changed during sync; checkout preserved")
                        destination = quarantine(root, entry.repo, load_repositories(root))
                        result = Result("✅", f"moved to {destination.relative_to(root)}")
                    results[entry.repo.path] = result
                except (OSError, WorkspaceError) as error:
                    results[entry.repo.path] = Result("⚠️", str(error), True)
        return [entry.repo for entry in targets], results
