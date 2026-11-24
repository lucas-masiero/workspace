"""Serialize mutations of an index, its checkouts and its trash."""
from contextlib import contextmanager
from pathlib import Path

from .manifest import WorkspaceError


@contextmanager
def workspace_lock(root: Path):
    directory = root / ".workspace-sync.lock"
    try:
        directory.mkdir()
    except FileExistsError as error:
        raise WorkspaceError("Another sync/trash operation is running, or .workspace-sync.lock remains from an interrupted run") from error
    try:
        yield
    finally:
        directory.rmdir()
