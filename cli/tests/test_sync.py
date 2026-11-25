import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from workspace_cli.app import main
from workspace_cli.inventory import inspect
from workspace_cli.manifest import WorkspaceError, load_repositories
from workspace_cli.repositories import repository_name
from workspace_cli.sync import TABLE_START, TABLE_END, synchronize
from test_workspace import run_git, identity, commit


class ReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="workspace-sync-test-")
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name).resolve()
        self.root = self.base / "Workspace"
        self.root.mkdir()
        self.manifest = self.root / "repositories.json"
        self.architecture = self.root / "ARCHITECTURE.md"
        self.initial = {
            "version": 1, "note": "preserve custom fields",
            "repositories": [
                {"path": "organization/cohesian/core", "github": "cohesian/core", "role": "Reference"},
                {"path": "organization/cohesian-tools/tools/absent", "github": "cohesian-tools/absent"},
            ],
        }
        self.manifest.write_text(json.dumps(self.initial, indent=2) + "\n")
        self.architecture.write_text(f"# Architecture\n\n{TABLE_START}\nold table\n{TABLE_END}\n\nKeep this prose.\n")
        self.core = self.make_repo("organization/cohesian/core", "cohesian/core")
        self.new = self.make_repo("personal/new-tool", "person/new-tool")

    def make_repo(self, relative, github):
        directory = self.root / relative
        directory.mkdir(parents=True)
        run_git(directory, "init", "-qb", "main")
        identity(directory)
        commit(directory, "source.txt")
        run_git(directory, "remote", "add", "origin", f"git@github.com:{github}.git")
        return directory

    def invoke(self, *args):
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = main(["--root", str(self.root), *args] if args[0] == "sync" else ["--root", str(self.root), "repo", *args])
        return code, stdout.getvalue(), stderr.getvalue()

    def local_clone(self, repo, target):
        subprocess.run(["git", "clone", "-q", "-b", "main", str(self.core), str(target)], check=True)
        run_git(target, "remote", "set-url", "origin", f"git@github.com:{repo.github}.git")

    def test_check_reports_matches_missing_and_new_without_changing_anything(self):
        before = self.manifest.read_bytes(), self.architecture.read_bytes()
        code, output, _ = self.invoke("check")
        self.assertEqual(code, 1)
        self.assertIn("✅ matches index", output)
        self.assertIn("absent [cohesian-tools/absent]  ❌ missing checkout", output)
        self.assertIn("new-tool [person/new-tool]  ⚠️ new local repository", output)
        self.assertEqual((self.manifest.read_bytes(), self.architecture.read_bytes()), before)
        self.assertFalse((self.root / ".workspace-sync.lock").exists())
        self.assertFalse((self.root / ".trash").exists())
        self.assertEqual(self.invoke("check", "cohesian/core")[0], 0)
        self.assertEqual(self.invoke("check", "person")[0], 1)

    def test_discovery_stops_at_git_boundaries_and_ignores_symlinks(self):
        self.make_repo("organization/cohesian/core/dependencies/nested", "person/nested")
        (self.root / "personal/alias").symlink_to(self.new, target_is_directory=True)
        inventory = inspect(self.root, load_repositories(self.root))
        self.assertEqual({e.repo.path for e in inventory}, {"organization/cohesian/core", "organization/cohesian-tools/tools/absent", "personal/new-tool"})
        code, output, _ = self.invoke("check", "person", "-l", "1")
        self.assertEqual(code, 1)
        self.assertIn("personal/ (1 repo)  ⚠️ 1", output)
        self.assertNotIn("[person/new-tool]", output)

    def test_index_remove_updates_index_and_routing_table_only(self):
        source = (self.core / "source.txt").read_bytes()
        head = run_git(self.core, "rev-parse", "HEAD")
        repos, results = synchronize(self.root, "index", "remove", "cohesian-tools")
        self.assertEqual(len(repos), 1)
        self.assertFalse(next(iter(results.values())).failed)
        data = json.loads(self.manifest.read_bytes())
        self.assertEqual(data["note"], self.initial["note"])
        self.assertEqual(data["repositories"], self.initial["repositories"][:1])
        self.assertIn("| `organization/cohesian/core` | `cohesian/core` |", self.architecture.read_text())
        self.assertIn("Keep this prose.", self.architecture.read_text())
        self.assertNotIn("absent", self.architecture.read_text())
        self.assertEqual(run_git(self.core, "rev-parse", "HEAD"), head)
        self.assertEqual((self.core / "source.txt").read_bytes(), source)
        self.assertTrue(self.new.is_dir())

    def test_workdir_clone_materializes_checkout_without_editing_index(self):
        before = self.manifest.read_bytes(), self.architecture.read_bytes()
        # Exercise the actual clone transport without contacting GitHub.
        with patch.dict(os.environ, {"GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": f"url.{self.core}.insteadOf", "GIT_CONFIG_VALUE_0": "git@github.com:cohesian-tools/absent.git"}):
            repos, results = synchronize(self.root, "workdir", "clone")
        target = self.root / "organization/cohesian-tools/tools/absent"
        self.assertEqual(repository_name(target), "cohesian-tools/absent")
        self.assertEqual((target / "source.txt").read_bytes(), (self.core / "source.txt").read_bytes())
        self.assertFalse(results[repos[0].path].failed)
        self.assertEqual((self.manifest.read_bytes(), self.architecture.read_bytes()), before)
        self.assertFalse(list(target.parent.glob(".workspace-clone-*")))

    def test_empty_directory_is_missing_and_can_be_cloned(self):
        target = self.root / "organization/cohesian-tools/tools/absent"
        target.mkdir(parents=True)
        _, results = synchronize(self.root, "workdir", "clone", clone=self.local_clone)
        self.assertFalse(results["organization/cohesian-tools/tools/absent"].failed)
        self.assertTrue((target / ".git").is_dir())

    def test_failed_clone_and_racing_working_files_are_preserved(self):
        target = self.root / "organization/cohesian-tools/tools/absent"
        target.mkdir(parents=True)
        def fail(repo, prepared):
            prepared.mkdir()
            (prepared / "partial.txt").write_text("partial clone")
            raise WorkspaceError("Network unavailable")
        _, results = synchronize(self.root, "workdir", "clone", clone=fail)
        self.assertTrue(results["organization/cohesian-tools/tools/absent"].failed)
        self.assertEqual(list(target.iterdir()), [])
        def change(repo, prepared):
            self.local_clone(repo, prepared)
            (target / "local.txt").write_text("concurrent work")
        _, results = synchronize(self.root, "workdir", "clone", clone=change)
        self.assertTrue(results["organization/cohesian-tools/tools/absent"].failed)
        self.assertEqual((target / "local.txt").read_text(), "concurrent work")
        self.assertFalse(list(target.parent.glob(".workspace-clone-*")))

    def test_occupied_or_wrong_origin_paths_are_never_purged_or_replaced(self):
        target = self.root / "organization/cohesian-tools/tools/absent"
        target.mkdir(parents=True)
        (target / "important.txt").write_text("preserve me")
        run_git(self.core, "remote", "set-url", "origin", "git@github.com:other/core.git")
        original = self.manifest.read_bytes()
        with patch("workspace_cli.sync.clone_repository") as clone:
            for action in ("remove", "clone"):
                _, results = synchronize(self.root, "index" if action == "remove" else "workdir", action, clone=clone)
                self.assertTrue(all(result.failed for result in results.values()))
            clone.assert_not_called()
        self.assertEqual(self.manifest.read_bytes(), original)
        self.assertEqual((target / "important.txt").read_text(), "preserve me")

    def test_index_add_registers_existing_repo_and_is_idempotent(self):
        (self.new / "uncommitted.txt").write_text("unfinished")
        before = run_git(self.new, "status", "--porcelain"), run_git(self.new, "rev-parse", "HEAD")
        repos, results = synchronize(self.root, "index", "add", "person")
        self.assertEqual(len(repos), 1)
        self.assertFalse(results[repos[0].path].failed)
        self.assertIn({"path": "personal/new-tool", "github": "person/new-tool"}, json.loads(self.manifest.read_bytes())["repositories"])
        self.assertIn("| `personal/new-tool` | `person/new-tool` |", self.architecture.read_text())
        self.assertEqual((run_git(self.new, "status", "--porcelain"), run_git(self.new, "rev-parse", "HEAD")), before)
        before = self.manifest.read_bytes(), self.architecture.read_bytes()
        self.assertEqual(synchronize(self.root, "index", "add", "person"), ([], {}))
        self.assertEqual((self.manifest.read_bytes(), self.architecture.read_bytes()), before)

    def test_workdir_purge_moves_complete_checkout_to_recoverable_trash(self):
        (self.new / "uncommitted.txt").write_text("unfinished")
        head = run_git(self.new, "rev-parse", "HEAD")
        before = self.manifest.read_bytes(), self.architecture.read_bytes()
        repos, results = synchronize(self.root, "workdir", "purge", "person")
        self.assertFalse(results[repos[0].path].failed)
        self.assertFalse(self.new.exists())
        saved = list((self.root / ".trash").glob("*/personal/new-tool"))
        self.assertEqual(len(saved), 1)
        self.assertEqual((saved[0] / "uncommitted.txt").read_text(), "unfinished")
        self.assertEqual(run_git(saved[0], "rev-parse", "HEAD"), head)
        self.assertIn(str(saved[0].relative_to(self.root)), results[repos[0].path].detail)
        self.assertEqual((self.manifest.read_bytes(), self.architecture.read_bytes()), before)
        self.assertFalse(any(not entry.registered for entry in inspect(self.root, load_repositories(self.root))))

    def test_duplicate_origins_and_nested_routes_cannot_be_registered(self):
        run_git(self.new, "remote", "set-url", "origin", "git@github.com:cohesian/core.git")
        before = self.manifest.read_bytes(), self.architecture.read_bytes()
        with self.assertRaisesRegex(WorkspaceError, "Duplicate"):
            synchronize(self.root, "index", "add")
        self.assertEqual((self.manifest.read_bytes(), self.architecture.read_bytes()), before)
        run_git(self.new, "remote", "set-url", "origin", "git@github.com:person/new-tool.git")
        self.make_repo("organization/cohesian-tools/tools", "person/container")
        with self.assertRaisesRegex(WorkspaceError, "Nested"):
            synchronize(self.root, "index", "add")
        self.assertEqual((self.manifest.read_bytes(), self.architecture.read_bytes()), before)
        _, results = synchronize(self.root, "workdir", "purge", "person/container")
        self.assertTrue(results["organization/cohesian-tools/tools"].failed)
        self.assertTrue((self.root / "organization/cohesian-tools/tools/.git").is_dir())

    def test_doc_write_failure_rolls_back_manifest_without_touching_sources(self):
        before = self.manifest.read_bytes(), self.architecture.read_bytes()
        from workspace_cli import sync
        replace = sync.os.replace
        def fail_architecture(source, target):
            if target == self.architecture:
                raise OSError("simulated documentation write failure")
            return replace(source, target)
        with patch("workspace_cli.sync.os.replace", side_effect=fail_architecture), self.assertRaisesRegex(OSError, "documentation"):
            synchronize(self.root, "index", "add")
        self.assertEqual((self.manifest.read_bytes(), self.architecture.read_bytes()), before)
        self.assertFalse(list(self.root.glob(".workspace-sync-*")))
        self.assertFalse((self.root / ".workspace-sync.lock").exists())
        self.assertTrue(self.new.is_dir())

    def test_concurrent_index_edits_are_preserved_with_recovery_files(self):
        from workspace_cli import sync
        replace = sync.os.replace
        concurrent = b'{"concurrent":"edit"}\n'
        def interrupt_docs(source, target):
            if target == self.architecture:
                self.manifest.write_bytes(concurrent)
                raise OSError("concurrent documentation edit")
            return replace(source, target)
        with patch("workspace_cli.sync.os.replace", side_effect=interrupt_docs), self.assertRaisesRegex(WorkspaceError, "recovery"):
            synchronize(self.root, "index", "add")
        self.assertEqual(self.manifest.read_bytes(), concurrent)
        self.assertTrue(list(self.root.glob(".workspace-sync-*/backup-0")))

    def test_linked_worktrees_and_symlinked_trash_are_preserved(self):
        worktree = self.root / "personal/linked"
        run_git(self.new, "worktree", "add", "-qb", "feature", str(worktree))
        _, results = synchronize(self.root, "workdir", "purge", "person")
        self.assertTrue(all(result.failed for result in results.values()))
        self.assertTrue(worktree.is_dir())
        self.assertTrue(self.new.is_dir())
        run_git(self.new, "worktree", "remove", str(worktree))
        external = self.base / "external-trash"
        external.mkdir()
        (self.root / ".trash").symlink_to(external, target_is_directory=True)
        _, results = synchronize(self.root, "workdir", "purge", "person")
        self.assertTrue(results["personal/new-tool"].failed)
        self.assertTrue(self.new.is_dir())
        self.assertEqual(list(external.iterdir()), [])

    def test_incomplete_sync_is_noop_and_all_mode_or_old_flags_are_rejected(self):
        with patch("workspace_cli.app.discover_root", side_effect=AssertionError("no-op must not inspect or mutate workspace")):
            for args in [("sync",), ("sync", "index"), ("sync", "workdir")]:
                self.assertEqual(self.invoke(*args)[0], 0)
        for args in [("sync", "all"), ("sync", "-a"), ("sync", "missing"), ("sync", "index", "--add", "--remove"), ("sync", "workdir", "--purge", "--clone")]:
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
                self.invoke(*args)
            self.assertEqual(error.exception.code, 2)

    def test_existing_lock_prevents_concurrent_changes(self):
        (self.root / ".workspace-sync.lock").mkdir()
        before = self.manifest.read_bytes()
        with self.assertRaisesRegex(WorkspaceError, "Another sync"):
            synchronize(self.root, "index", "remove")
        self.assertEqual(self.manifest.read_bytes(), before)

    def test_cli_flags_select_the_exact_side_and_operation(self):
        with patch("workspace_cli.app.synchronize", return_value=([], {})) as operation:
            for target, mode in [("index", "add"), ("index", "remove"), ("workdir", "clone"), ("workdir", "purge")]:
                code, _, _ = self.invoke("sync", target, "--" + mode, "person", "-l", "1")
                self.assertEqual(code, 0)
                operation.assert_called_with(self.root, target, mode, "person")
            self.assertEqual(self.invoke("sync", "workdir", "-p", "person")[0], 0)
            operation.assert_called_with(self.root, "workdir", "purge", "person")


if __name__ == "__main__":
    unittest.main()
