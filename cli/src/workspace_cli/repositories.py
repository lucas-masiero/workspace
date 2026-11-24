"""Inspect main without checking it out; fetch never merges working files."""
from dataclasses import dataclass
import os
from pathlib import Path
import re
import subprocess
from urllib.parse import urlsplit

from .manifest import Repository, WorkspaceError


@dataclass(frozen=True)
class Result:
    symbol: str
    detail: str
    failed: bool = False


def git(directory: Path, *args: str, timeout: int = 15) -> str:
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GCM_INTERACTIVE": "Never", "GIT_OPTIONAL_LOCKS": "0"}
    try:
        result = subprocess.run(["git", "-C", str(directory), *args], capture_output=True,
                                text=True, errors="replace", env=env, timeout=timeout)
    except FileNotFoundError as error:
        raise WorkspaceError("Git is missing; run the setup script for this device") from error
    except subprocess.TimeoutExpired as error:
        raise WorkspaceError(f"Git timed out after {timeout}s") from error
    if result.returncode:
        # Report useful failures without echoing possible URL credentials.
        message = re.sub(r"https?://[^\s/@]+:[^\s/@]+@", "https://[redacted]@", result.stderr.strip())
        message = " ".join(message.split())[:300] or "Git command failed"
        raise WorkspaceError(message)
    return result.stdout.strip() if "-z" not in args else result.stdout


def github_name(url: str) -> str | None:
    if url.startswith("git@github.com:"):
        name = url[len("git@github.com:"):]
    else:
        try:
            parsed = urlsplit(url)
            if parsed.hostname != "github.com" or parsed.scheme not in {"ssh", "https"} or parsed.query or parsed.fragment:
                return None
            name = parsed.path.lstrip("/")
        except ValueError:
            return None
    name = name.removesuffix(".git")
    return name.casefold() if re.fullmatch(r"[\w.-]+/[\w.-]+", name) else None


def checkout(root: Path, repo: Repository) -> Path | None:
    directory = local_path(root, repo.path)
    if not directory.exists():
        return None
    if repository_name(directory) != repo.github.casefold():
        raise WorkspaceError("origin does not match the registered GitHub repository")
    return directory


def local_path(root: Path, relative: str) -> Path:
    directory = root
    for part in relative.split("/"):
        directory /= part
        if directory.is_symlink():
            raise WorkspaceError("Checkout path contains a symlink; skipped")
    return directory


def repository_name(directory: Path) -> str:
    if not directory.is_dir():
        raise WorkspaceError("Checkout path is not a directory")
    if Path(git(directory, "rev-parse", "--show-toplevel")).resolve() != directory.resolve():
        raise WorkspaceError("Path is not a standalone repository")
    urls = git(directory, "config", "--get-all", "remote.origin.url").splitlines()
    name = github_name(urls[0]) if len(urls) == 1 else None
    if name is None:
        raise WorkspaceError("Expected one GitHub repository as origin")
    return name


def classify(ahead: int, behind: int, dirty: bool) -> str:
    local_changes = ahead > 0 or dirty
    if behind and local_changes:
        return "⚠️"
    if behind:
        return "🔽"
    return "🔼" if local_changes else "✅"


def status(root: Path, repo: Repository) -> Result:
    try:
        directory = checkout(root, repo)
        if directory is None:
            return Result("⚪", "not cloned")
        for ref in ("refs/heads/main", "refs/remotes/origin/main"):
            try:
                git(directory, "rev-parse", "--verify", ref)
            except WorkspaceError as error:
                raise WorkspaceError(f"Missing {ref}; cannot compare main") from error
        counts = git(directory, "rev-list", "--left-right", "--count", "refs/heads/main...refs/remotes/origin/main")
        ahead, behind = map(int, counts.split())
        dirty = bool(git(directory, "status", "--porcelain=v1", "-z", "--untracked-files=normal"))
        branch = git(directory, "rev-parse", "--abbrev-ref", "HEAD")
        detail = f"main +{ahead} −{behind}"
        if dirty:
            detail += "; uncommitted changes"
        if branch != "main":
            detail += f"; on {branch if branch != 'HEAD' else 'detached HEAD'}"
        return Result(classify(ahead, behind, dirty), detail)
    except (OSError, WorkspaceError) as error:
        return Result("⚠️", str(error), failed=True)


def fetch(root: Path, repo: Repository) -> Result:
    try:
        directory = checkout(root, repo)
        if directory is None:
            return Result("⚪", "not cloned; skipped")
        git(directory, "fetch", "origin", timeout=60)
        return Result("✅", "fetched origin")
    except (OSError, WorkspaceError) as error:
        return Result("⚠️", str(error), failed=True)
