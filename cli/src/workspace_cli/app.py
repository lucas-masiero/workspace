"""Tree-based repository inspection and explicit index/checkout reconciliation."""
import argparse
import sys

from . import __version__
from .auth import login
from .inventory import inspect
from .manifest import WorkspaceError, discover_root, load_repositories, select
from .repositories import status, fetch
from .sync import synchronize
from .trash import initialize as initialize_trash, empty as empty_trash
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
        "check": "compare indexed routes with local checkouts and discover unregistered repositories",
    }.items():
        command = commands.add_parser(name, help=description, description=description)
        tree_arguments(command)
    commands.add_parser("login", help="authenticate GitHub CLI and SSH for this device")
    sync = groups.add_parser("sync", help="explicitly reconcile the index or workdir; no default action")
    targets = sync.add_subparsers(dest="sync_target")
    for target, descriptions in {
        "index": {"add": "add unregistered local repositories to the index", "remove": "remove index entries whose local checkouts are missing"},
        "workdir": {"purge": "move local repositories absent from the index to recoverable trash", "clone": "clone indexed repositories whose local checkouts are missing"},
    }.items():
        scoped = targets.add_parser(target, help=f"reconcile the {target}")
        modes = scoped.add_mutually_exclusive_group()
        for mode, description in descriptions.items():
            flags = ("-p", "--purge") if mode == "purge" else ("--" + mode,)
            modes.add_argument(*flags, dest="sync_mode", action="store_const", const=mode, help=description)
        tree_arguments(scoped)
    trash = groups.add_parser("trash", help="initialize or permanently empty Workspace's .trash directory")
    trash_commands = trash.add_subparsers(dest="trash_action", required=True)
    trash_commands.add_parser("init", help="initialize .trash; existing managed contents are preserved")
    trash_commands.add_parser("empty", help="permanently delete all saved trash entries; retain .trash itself")
    return app


def tree_arguments(command: argparse.ArgumentParser) -> None:
    command.add_argument("query", nargs="?", default="all", metavar="QUERY", help="all (default), owner, or owner/name")
    command.add_argument("-l", "--level", dest="depth", type=positive, metavar="N", help="tree display depth; does not limit the selected repositories")


def main(argv: list[str] | None = None) -> int:
    arguments = parser().parse_args(argv)
    try:
        if arguments.group == "repo" and arguments.command == "login":
            return login()
        if arguments.group == "sync" and not getattr(arguments, "sync_mode", None):
            print("No sync mode selected; no changes made. Use sync index --add/--remove or sync workdir --clone/--purge.")
            return 0
        root = discover_root(arguments.root)
        if arguments.group == "trash":
            if arguments.trash_action == "init":
                print(f"Workspace trash ready: {initialize_trash(root)}")
            else:
                count = empty_trash(root)
                print(f"Trash emptied: {count} saved entries permanently removed.")
            return 0
        if arguments.group == "sync":
            repositories, results = synchronize(root, arguments.sync_target, arguments.sync_mode, arguments.query)
            print(render_tree(root.name, repositories, results, arguments.depth))
            if not repositories:
                print(f"\nNothing to {arguments.sync_mode} in {arguments.sync_target} for {arguments.query}.")
            return int(any(result.failed for result in results.values()))
        if arguments.command == "check":
            inventory = inspect(root, load_repositories(root))
            repositories = select([entry.repo for entry in inventory], arguments.query)
            results = {entry.repo.path: entry.result for entry in inventory}
            print(render_tree(root.name, repositories, results, arguments.depth))
            print("\n✅ matches index  ❌ missing checkout  ⚠️ new local repository or path/origin conflict")
            print("Check is local and read-only; discovery stops at repository boundaries.")
            return int(any(results[repo.path].failed for repo in repositories))
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
