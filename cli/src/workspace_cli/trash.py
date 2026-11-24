"""Recoverable purge storage. Only trash empty permanently deletes its contents."""
import json
from pathlib import Path
import shutil

from .locking import workspace_lock
from .manifest import WorkspaceError

MARKER = ".workspace-trash.json"
IDENTITY = {"schemaVersion": 1, "kind": "cohesian-workspace-trash"}


def trash_directory(root: Path) -> Path:
    directory = root / ".trash"
    if directory.is_symlink() or (directory.exists() and not directory.is_dir()):
        raise WorkspaceError(".trash must be a real directory, never a symlink or file")
    return directory


def validate_trash(directory: Path) -> None:
    marker = directory / MARKER
    try:
        if marker.is_symlink() or not marker.is_file() or json.loads(marker.read_text()) != IDENTITY:
            raise WorkspaceError(".trash is not initialized by Workspace; contents preserved")
    except (ValueError, OSError) as error:
        raise WorkspaceError("Invalid Workspace trash marker; contents preserved") from error


def ensure_trash(root: Path) -> Path:
    """Caller holds workspace_lock; adopt only an absent or empty directory."""
    directory = trash_directory(root)
    if directory.exists() and any(directory.iterdir()):
        validate_trash(directory)
    else:
        directory.mkdir(exist_ok=True)
        (directory / MARKER).write_text(json.dumps(IDENTITY) + "\n")
    return directory


def initialize(root: Path) -> Path:
    with workspace_lock(root):
        return ensure_trash(root)


def empty(root: Path) -> int:
    with workspace_lock(root):
        directory = trash_directory(root)
        if not directory.exists():
            return 0
        validate_trash(directory)
        entries = [child for child in directory.iterdir() if child.name != MARKER]
        for child in entries:
            if child.is_symlink() or not child.is_dir():
                child.unlink()
            else:
                shutil.rmtree(child)
        return len(entries)
