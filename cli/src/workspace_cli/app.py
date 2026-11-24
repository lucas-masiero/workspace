"""Command grammar: workspace repo {list,status,fetch} [all|owner|owner/name]."""
import argparse
import sys

from . import __version__
from .auth import login
from .manifest import WorkspaceError, discover_root, load_repositories, select
from .repositories import status, fetch
from .tree import render_tree


def positive(value: str) -> int:
    try:
        number = int(value)
        if number >= 1:
            return number
    except ValueError:
        pass
    raise argparse.ArgumentTypeError("depth must be a positive integer (root is level 0)")


def parser() -> argparse.ArgumentParser:
    app = argparse.ArgumentParser(prog="workspace", description="Manage the repository leaves registered in repositories.json.")
    app.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    app.add_argument("--root", metavar="PATH", help="workspace directory; otherwise use WORKSPACE_ROOT or auto-discovery")
    groups = app.add_subparsers(dest="group", required=True)
    repo = groups.add_parser("repo", help="list, inspect, fetch or authenticate repositories")
    commands = repo.add_subparsers(dest="command", required=True)
    for name, description in {
        "list": "show the registered repository tree (no Git/network access)",
        "status": "compare local main with the last fetched origin/main, including local edits",
        "fetch": "git fetch origin in selected existing checkouts; never merge or switch branches",
    }.items():
        command = commands.add_parser(name, help=description, description=description)
        command.add_argument("query", nargs="?", default="all", metavar="QUERY", help="all (default), owner, or owner/name")
        command.add_argument("-l", "--level", dest="depth", type=positive, metavar="N", help="tree display depth; does not limit the selected repositories")
    commands.add_parser("login", help="authenticate GitHub CLI and SSH for this device")
    return app


def main(argv: list[str] | None = None) -> int:
    arguments = parser().parse_args(argv)
    try:
        if arguments.command == "login":
            return login()
        root = discover_root(arguments.root)
        repositories = select(load_repositories(root), arguments.query)
        results = None
        if arguments.command != "list":
            operation = {"status": status, "fetch": fetch}[arguments.command]
            results = {}
            for repo in repositories:
                if arguments.command == "fetch" and sys.stderr.isatty():
                    print(f"Fetching {repo.github}…", file=sys.stderr, flush=True)
                results[repo.path] = operation(root, repo)
        print(render_tree(root.name, repositories, results, arguments.depth))
        if arguments.command == "status":
            print("\n✅ synced  🔽 behind  🔼 local changes/ahead  ⚠️ mixed/error  ⚪ not cloned")
            print("main compared with cached origin/main; run workspace repo fetch to refresh.")
        if arguments.command == "fetch":
            print("\nFetch updates remote references only. Run workspace repo status to compare main.")
        return 1 if results and any(result.failed for result in results.values()) else 0
    except (OSError, WorkspaceError) as error:
        print(f"workspace: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nworkspace: interrupted", file=sys.stderr)
        return 130
