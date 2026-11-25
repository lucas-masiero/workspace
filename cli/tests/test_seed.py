"""Exercise seed orchestration with fake package tools, without installing any."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]


class SeedTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="workspace-seed-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "Workspace with spaces"
        self.bin = self.root / "fake-bin"
        self.bin.mkdir(parents=True)
        self.log = self.root / "calls.log"
        for platform in ("termux", "macos"):
            directory = self.root / "scripts" / platform
            directory.mkdir(parents=True)
            shutil.copyfile(ROOT / "scripts" / platform / "setup.sh", directory / "setup.sh")
        self.env = {**os.environ, "PATH": str(self.bin) + os.pathsep + os.environ["PATH"], "WORKSPACE_TEST_LOG": str(self.log)}

    def executable(self, file, script):
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(f"#!{shutil.which('bash')}\nset -eu\n" + script + "\n")
        file.chmod(0o755)

    def test_termux_installs_tools_then_cli_then_login_without_cloning(self):
        self.executable(self.bin / "pkg", 'printf "pkg %s\\n" "$*" >> "$WORKSPACE_TEST_LOG"')
        self.executable(self.root / "scripts/install-cli.sh", 'printf "install cli\\n" >> "$WORKSPACE_TEST_LOG"')
        self.executable(self.root / ".venv-cli/bin/workspace", 'printf "workspace %s\\n" "$*" >> "$WORKSPACE_TEST_LOG"')
        result = subprocess.run(["bash", str(self.root / "scripts/termux/setup.sh")], env=self.env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        lines = self.log.read_text().splitlines()
        self.assertEqual(lines[0], "pkg update -y")
        self.assertIn("python-ensurepip-wheels", lines[1])
        self.assertEqual(lines[2:], ["install cli", "workspace repo login"])
        self.assertFalse((self.root / "organization").exists())
        self.assertIn("bootstrap.sh", result.stdout)

    def test_termux_package_failure_stops_before_cli_or_login(self):
        self.executable(self.bin / "pkg", 'exit 7')
        self.executable(self.root / "scripts/install-cli.sh", 'touch "$WORKSPACE_TEST_LOG"')
        result = subprocess.run(["bash", str(self.root / "scripts/termux/setup.sh")], env=self.env, capture_output=True)
        self.assertEqual(result.returncode, 7)
        self.assertFalse(self.log.exists())

    def test_macos_guard_rejects_other_platforms_before_installing(self):
        self.executable(self.bin / "uname", 'printf "Linux\\n"')
        self.executable(self.bin / "brew", 'touch "$WORKSPACE_TEST_LOG"')
        result = subprocess.run(["bash", str(self.root / "scripts/macos/setup.sh")], env=self.env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn("requires macOS", result.stderr)
        self.assertFalse(self.log.exists())

    def test_macos_package_failure_stops_before_profile_cli_or_login(self):
        self.executable(self.bin / "uname", 'printf "Darwin\\n"')
        self.executable(self.bin / "brew", '''
case "$1" in
  shellenv) exit 0 ;;
  install) printf "brew %s\\n" "$*" >> "$WORKSPACE_TEST_LOG"; exit 9 ;;
  *) exit 99 ;;
esac''')
        result = subprocess.run(["bash", str(self.root / "scripts/macos/setup.sh")], env=self.env, capture_output=True)
        self.assertEqual(result.returncode, 9)
        self.assertEqual(self.log.read_text().strip(), "brew install git gh python node")


if __name__ == "__main__":
    unittest.main()
