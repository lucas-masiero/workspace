import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from workspace_cli.app import main
from workspace_cli.auth import login
from workspace_cli.manifest import Repository, WorkspaceError, discover_root, load_repositories, select
from workspace_cli.repositories import Result, fetch, github_name, status
from workspace_cli.tree import render_tree


def run_git(directory, *args):
    return subprocess.check_output(["git", "-C", str(directory), *args], text=True, stderr=subprocess.PIPE).strip()


def identity(directory):
    for name, value in [("user.name", "Workspace Test"), ("user.email", "test@example.org"),
                        ("commit.gpgsign", "false"), ("core.hooksPath", "/dev/null")]:
        run_git(directory, "config", name, value)


def commit(directory, name):
    (directory / name).write_text(name)
    run_git(directory, "add", name)
    run_git(directory, "commit", "-qm", name)


class GitTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="workspace-git-test-")
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name).resolve()
        self.root = self.base / "Workspace"
        self.root.mkdir()
        self.repo = Repository("Cohesian/site", "example/site")
        self.local = self.root / self.repo.path
        self.local.mkdir(parents=True)
        self.remote = self.base / "remote.git"
        subprocess.run(["git", "init", "--bare", "-q", str(self.remote)], check=True)
        run_git(self.local, "init", "-qb", "main")
        identity(self.local)
        commit(self.local, "initial.txt")
        run_git(self.local, "remote", "add", "origin", str(self.remote))
        run_git(self.local, "push", "-qu", "origin", "main")
        # Exercise normal Git transport using a local bare repo, with no network.
        url = "https://github.com/example/site.git"
        run_git(self.local, "remote", "set-url", "origin", url)
        run_git(self.local, "config", f"url.{self.remote}.insteadOf", url)
        self.actor = self.base / "actor"
        subprocess.run(["git", "clone", "-q", "-b", "main", str(self.remote), str(self.actor)], check=True)
        identity(self.actor)

    def advance_remote(self):
        commit(self.actor, "remote.txt")
        run_git(self.actor, "push", "-q", "origin", "main")

    def test_synced_and_uncommitted_states(self):
        self.assertEqual(status(self.root, self.repo).symbol, "✅")
        (self.local / "untracked.txt").write_text("work")
        self.assertEqual(status(self.root, self.repo).symbol, "🔼")
        run_git(self.local, "add", "untracked.txt")
        self.assertIn("uncommitted", status(self.root, self.repo).detail)
        commit(self.local, "ahead.txt")
        result = status(self.root, self.repo)
        self.assertEqual(result.symbol, "🔼")
        self.assertIn("+1", result.detail)

    def test_behind_is_cached_until_fetch_and_fetch_does_not_edit_work(self):
        self.advance_remote()
        self.assertEqual(status(self.root, self.repo).symbol, "✅")
        before = run_git(self.local, "rev-parse", "HEAD")
        (self.local / "initial.txt").write_text("local unfinished work")
        self.assertFalse(fetch(self.root, self.repo).failed)
        self.assertEqual(run_git(self.local, "rev-parse", "HEAD"), before)
        self.assertEqual((self.local / "initial.txt").read_text(), "local unfinished work")
        self.assertEqual(status(self.root, self.repo).symbol, "⚠️")
        (self.local / "initial.txt").write_text("initial.txt")
        result = status(self.root, self.repo)
        self.assertEqual(result.symbol, "🔽")
        self.assertIn("−1", result.detail)

    def test_diverged_main_is_mixed(self):
        self.advance_remote()
        commit(self.local, "local.txt")
        fetch(self.root, self.repo)
        result = status(self.root, self.repo)
        self.assertEqual(result.symbol, "⚠️")
        self.assertIn("+1 −1", result.detail)
        self.assertFalse(result.failed)

    def test_status_and_fetch_compare_main_without_switching_feature_branch(self):
        run_git(self.local, "checkout", "-qb", "feature")
        commit(self.local, "feature.txt")
        self.advance_remote()
        self.assertEqual(status(self.root, self.repo).symbol, "✅")
        fetch(self.root, self.repo)
        result = status(self.root, self.repo)
        self.assertEqual(result.symbol, "🔽")
        self.assertIn("on feature", result.detail)
        self.assertEqual(run_git(self.local, "branch", "--show-current"), "feature")

    def test_missing_main_or_remote_main_never_reports_synced(self):
        run_git(self.local, "branch", "-m", "different")
        self.assertTrue(status(self.root, self.repo).failed)
        run_git(self.local, "branch", "-m", "main")
        run_git(self.local, "update-ref", "-d", "refs/remotes/origin/main")
        self.assertIn("Missing refs/remotes/origin/main", status(self.root, self.repo).detail)

    def test_missing_checkout_is_skipped_without_creating_it(self):
        absent = Repository("Cohesian/tools/missing", "example/missing")
        self.assertEqual(status(self.root, absent).symbol, "⚪")
        self.assertEqual(fetch(self.root, absent).symbol, "⚪")
        self.assertFalse((self.root / absent.path).exists())

    def test_wrong_origin_symlinks_and_parent_index_are_not_operated_on(self):
        run_git(self.local, "remote", "set-url", "origin", "git@github.com:other/repo.git")
        self.assertTrue(fetch(self.root, self.repo).failed)
        self.assertIn("origin does not match", status(self.root, self.repo).detail)
        linked = self.root / "Profile/linked"
        linked.parent.mkdir()
        linked.symlink_to(self.local, target_is_directory=True)
        self.assertIn("symlink", fetch(self.root, Repository("Profile/linked", "example/site")).detail)
        run_git(self.root, "init", "-q")
        empty = self.root / "Projects/plain"
        empty.mkdir(parents=True)
        self.assertIn("standalone", status(self.root, Repository("Projects/plain", "example/plain")).detail)

    def test_fetch_failure_is_visible_without_modifying_main(self):
        shutil.rmtree(self.remote)
        before = run_git(self.local, "rev-parse", "HEAD")
        result = fetch(self.root, self.repo)
        self.assertTrue(result.failed)
        self.assertEqual(run_git(self.local, "rev-parse", "HEAD"), before)


class IndexTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="workspace-index-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.entries = [
            {"path": "Cohesian/site", "github": "cohesian/site"},
            {"path": "Cohesian/tools/tool", "github": "cohesian-tools/tool"},
            {"path": "Profile/resume", "github": "person/resume"},
        ]
        self.write(self.entries)

    def write(self, entries):
        (self.root / "repositories.json").write_text(json.dumps({"version": 1, "repositories": entries}))

    def invoke(self, *args):
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = main(["--root", str(self.root), "repo", *args])
        return code, stdout.getvalue(), stderr.getvalue()

    def test_filters_use_github_namespace_and_default_selects_all(self):
        repositories = load_repositories(self.root)
        self.assertEqual(len(select(repositories, "all")), 3)
        self.assertEqual([r.github for r in select(repositories, "COHESIAN")], ["cohesian/site"])
        self.assertEqual(select(repositories, "cohesian-tools/tool")[0].path, "Cohesian/tools/tool")
        with self.assertRaises(WorkspaceError):
            select(repositories, "../unknown")
        with self.assertRaises(WorkspaceError):
            select(repositories, "missing")

    def test_tree_levels_preserve_summaries_for_hidden_repositories(self):
        repos = load_repositories(self.root)
        results = {r.path: Result("✅", "synced") for r in repos}
        results[repos[1].path] = Result("🔼", "local work")
        full = render_tree("Workspace", repos, results)
        self.assertIn("└── tool [cohesian-tools/tool]", full)
        collapsed = render_tree("Workspace", repos, results, depth=1)
        self.assertIn("Cohesian/ (2 repos)  ✅ 1  🔼 1", collapsed)
        self.assertNotIn("[cohesian/site]", collapsed)
        self.assertEqual(self.invoke("list", "person")[0], 0)

    def test_list_needs_no_git_and_status_missing_is_explicit(self):
        with patch("workspace_cli.repositories.git", side_effect=AssertionError("list must not invoke Git")):
            code, output, _ = self.invoke("list")
        self.assertEqual(code, 0)
        self.assertIn("[cohesian/site]", output)
        code, output, _ = self.invoke("status", "cohesian")
        self.assertEqual(code, 0)
        self.assertIn("⚪ not cloned", output)

    def test_fetch_handles_every_selected_repo_even_when_collapsed_or_one_fails(self):
        with patch("workspace_cli.app.fetch", side_effect=[Result("⚠️", "failed", True), Result("✅", "fetched"), Result("⚪", "not cloned")]) as operation:
            code, output, _ = self.invoke("fetch", "all", "-l", "1")
        self.assertEqual(code, 1)
        self.assertEqual(operation.call_count, 3)
        self.assertIn("⚠️ 1", output)
        self.assertNotIn("[cohesian/site]", output)

    def test_invalid_inventory_rejects_all_before_any_operation(self):
        cases = [
            [*self.entries, self.entries[0]],
            [{"path": "Cohesian/../outside", "github": "cohesian/site"}],
            [*self.entries, {"path": "Cohesian/site/child", "github": "person/child"}],
            [{"path": "Cohesian/site", "github": "https://github.com/cohesian/site"}],
        ]
        with patch("workspace_cli.app.fetch") as operation:
            for entries in cases:
                with self.subTest(entries=entries):
                    self.write(entries)
                    self.assertEqual(self.invoke("fetch")[0], 1)
            operation.assert_not_called()

    def test_root_resolution_and_unknown_query_errors(self):
        self.assertEqual(discover_root(str(self.root)), self.root)
        with patch.dict(os.environ, {"WORKSPACE_ROOT": str(self.root)}):
            self.assertEqual(discover_root(), self.root)
        code, _, error = self.invoke("list", "absent/repo")
        self.assertEqual(code, 1)
        self.assertIn("No registered", error)

    def test_invalid_depth_and_unknown_commands_are_helpful_errors(self):
        for args in [("list", "-l", "0"), ("status", "-l", "bad"), ("unknown",)]:
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
                self.invoke(*args)
            self.assertEqual(error.exception.code, 2)

    def test_remote_names_accept_standard_ssh_and_https_forms(self):
        for value in ["git@github.com:cohesian/site.git", "https://github.com/cohesian/site", "ssh://git@github.com/cohesian/site.git"]:
            self.assertEqual(github_name(value), "cohesian/site")
        self.assertIsNone(github_name("https://github.com.evil.test/cohesian/site"))
        self.assertIsNone(github_name("/some/local/path"))


class LoginTests(unittest.TestCase):
    def test_existing_authentication_is_reused(self):
        with patch("workspace_cli.auth.shutil.which", return_value="/bin/tool"), patch("workspace_cli.auth.subprocess.run", return_value=subprocess.CompletedProcess([], 0)), patch("workspace_cli.auth.ssh_ready", return_value=True), patch("workspace_cli.auth.subprocess.call") as interactive:
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(login(), 0)
            interactive.assert_not_called()

    def test_device_login_and_ssh_test_handle_github_exit_one(self):
        responses = [subprocess.CompletedProcess([], 1), subprocess.CompletedProcess([], 1, stdout="Hi! You've successfully authenticated, but GitHub does not provide shell access.")]
        with patch("workspace_cli.auth.shutil.which", return_value="/bin/tool"), patch("workspace_cli.auth.subprocess.run", side_effect=responses), patch("workspace_cli.auth.subprocess.call", return_value=0) as interactive:
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(login(), 0)
            self.assertIn("--web", interactive.call_args.args[0])
            self.assertIn("ssh", interactive.call_args.args[0])

    def test_failed_login_does_not_proceed_to_ssh_or_mask_exit_status(self):
        with patch("workspace_cli.auth.shutil.which", return_value="/bin/tool"), patch("workspace_cli.auth.subprocess.run", return_value=subprocess.CompletedProcess([], 1)) as run, patch("workspace_cli.auth.subprocess.call", return_value=4):
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(login(), 4)
            self.assertEqual(run.call_count, 1)


if __name__ == "__main__":
    unittest.main()
