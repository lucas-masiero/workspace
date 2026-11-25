import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from workspace_cli.app import main
from workspace_cli.manifest import WorkspaceError
from workspace_cli.trash import MARKER, initialize, empty


class TrashTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="workspace-trash-test-")
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name).resolve()
        self.root = self.base / "Workspace"
        self.root.mkdir()
        (self.root / "repositories.json").write_text(json.dumps({"version": 1, "repositories": []}))

    def test_init_is_idempotent_and_preserves_saved_files(self):
        trash = initialize(self.root)
        self.assertEqual(trash, self.root / ".trash")
        self.assertTrue((trash / MARKER).is_file())
        saved = trash / "saved/organization/cohesian/tool/uncommitted.txt"
        saved.parent.mkdir(parents=True)
        saved.write_text("unfinished work")
        initialize(self.root)
        self.assertEqual(saved.read_text(), "unfinished work")

    def test_empty_deletes_saved_tree_and_retains_initialized_trash(self):
        trash = initialize(self.root)
        saved = trash / "batch/personal/project/file.txt"
        saved.parent.mkdir(parents=True)
        saved.write_text("explicitly discarded")
        outside = self.base / "outside"
        outside.mkdir()
        (outside / "preserve.txt").write_text("keep")
        (trash / "external-link").symlink_to(outside, target_is_directory=True)
        self.assertEqual(empty(self.root), 2)
        self.assertEqual([p.name for p in trash.iterdir()], [MARKER])
        self.assertEqual((outside / "preserve.txt").read_text(), "keep")
        self.assertEqual(empty(self.root), 0)

    def test_empty_before_initialization_is_a_noop(self):
        self.assertEqual(empty(self.root), 0)
        self.assertFalse((self.root / ".trash").exists())
        self.assertFalse((self.root / ".workspace-sync.lock").exists())

    def test_unmanaged_populated_directory_is_never_adopted_or_emptied(self):
        trash = self.root / ".trash"
        trash.mkdir()
        (trash / "important.txt").write_text("not managed by Workspace")
        for operation in (initialize, empty):
            with self.assertRaisesRegex(WorkspaceError, "not initialized"):
                operation(self.root)
            self.assertEqual((trash / "important.txt").read_text(), "not managed by Workspace")

    def test_symlinked_trash_or_marker_is_refused(self):
        outside = self.base / "outside"
        outside.mkdir()
        trash = self.root / ".trash"
        trash.symlink_to(outside, target_is_directory=True)
        for operation in (initialize, empty):
            with self.assertRaisesRegex(WorkspaceError, "real directory"):
                operation(self.root)
        trash.unlink()
        trash.mkdir()
        marker = outside / "marker.json"
        marker.write_text('{"schemaVersion":1,"kind":"cohesian-workspace-trash"}')
        (trash / MARKER).symlink_to(marker)
        with self.assertRaisesRegex(WorkspaceError, "not initialized"):
            empty(self.root)
        self.assertTrue(marker.exists())

    def test_trash_commands_share_the_sync_lock(self):
        (self.root / ".workspace-sync.lock").mkdir()
        for operation in (initialize, empty):
            with self.assertRaisesRegex(WorkspaceError, "Another sync/trash"):
                operation(self.root)

    def test_cli_initializes_and_empties_the_selected_workspace(self):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            self.assertEqual(main(["--root", str(self.root), "trash", "init"]), 0)
            (self.root / ".trash/discard.txt").write_text("discard")
            self.assertEqual(main(["--root", str(self.root), "trash", "empty"]), 0)
        self.assertIn("1 saved entries permanently removed", stdout.getvalue())
        self.assertFalse((self.root / ".trash/discard.txt").exists())


if __name__ == "__main__":
    unittest.main()
