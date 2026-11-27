"""Validate the migrated catalog and small Bash wrappers without real mutations."""
import json
import hashlib
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import tempfile
import tomllib
import unittest

ROOT = Path(__file__).resolve().parents[1]


class CatalogTests(unittest.TestCase):
    def test_frozen_migration_snapshot_and_current_routing_contract(self):
        old = json.loads((ROOT / '.migration/repositories.v1.json').read_text())
        new = tomllib.loads((ROOT / '.workit.toml').read_text())
        self.assertEqual(new['version'], 1)
        self.assertIn(new['protocol'], ['https', 'ssh'])
        self.assertEqual(hashlib.sha256((ROOT / '.migration/repositories.v1.json').read_bytes()).hexdigest(), '83b0864508e80b99bcbd374905a9a49a399edc5a20173608ff6cce0f8a6a8090')
        self.assertEqual(len(old['repositories']), 27)
        nodes = {n['path']: n for n in new['nodes']}
        self.assertEqual(len(nodes), len(new['nodes']))
        self.assertEqual(nodes['.']['kind'], 'r')
        new_repos = {n['path']: n['repository'] for n in new['nodes'] if n['kind'] == 'w'}
        for p, node in nodes.items():
            if p != '.':
                self.assertIn(nodes[str(PurePosixPath(p).parent)]['kind'], ['r', 'n'])
            for excluded in new['exclude']:
                self.assertFalse(p == excluded or p.startswith(excluded + '/'))
        self.assertIn('scripts', new['exclude'])
        self.assertIn('tests', new['exclude'])
        architecture = (ROOT / 'ARCHITECTURE.md').read_text().split('<!-- workspace-repositories:start -->')[1].split('<!-- workspace-repositories:end -->')[0]
        routes = dict(re.findall(r'\| `([^`]+)` \| `([^`]+)` \|', architecture))
        self.assertEqual(routes, new_repos)
        self.assertFalse((ROOT / 'repositories.json').exists())
        self.assertFalse((ROOT / 'cli').exists())


class ScriptTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='workspace-workit-test-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'Workspace with spaces'
        self.bin = self.root / 'fake-bin'
        self.bin.mkdir(parents=True)
        self.log = self.root / 'calls.log'
        shutil.copytree(ROOT / 'scripts', self.root / 'scripts')
        self.env = {**os.environ, 'PATH': str(self.bin) + os.pathsep + os.environ['PATH'], 'WORKSPACE_TEST_LOG': str(self.log), 'WORKSPACE_TEST_BIN': str(self.bin)}

    def executable(self, name, body):
        p = self.bin / name
        p.write_text('#!' + shutil.which('bash') + '\nset -eu\n' + body + '\n')
        p.chmod(0o755)

    def run_script(self, path, *args):
        return subprocess.run(['bash', str(self.root / path), *args], env=self.env, capture_output=True, text=True)

    def test_termux_only_installs_prerequisites(self):
        self.executable('pkg', 'printf "pkg %s\\n" "$*" >> "$WORKSPACE_TEST_LOG"')
        self.executable('go', 'exit 95')
        self.executable('gh', 'exit 96')
        result = self.run_script('scripts/termux/setup.sh')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.log.read_text().splitlines(), ['pkg update -y', 'pkg install -y openssh git gh golang'])
        self.assertIn('go install github.com/cohesian-tools/workit@v0.1.0', result.stdout)
        self.assertFalse((self.root / 'organization').exists())

    def test_termux_failure_does_not_continue(self):
        self.executable('pkg', 'exit 7')
        result = self.run_script('scripts/termux/setup.sh')
        self.assertEqual(result.returncode, 7)
        self.assertNotIn('Prerequisites ready', result.stdout)

    def test_installer_delegates_to_go_and_respects_binary_directory(self):
        self.executable('go', '''
case "$1" in
 install) printf '%s\\n' "$*" >> "$WORKSPACE_TEST_LOG" ;;
 env) if [[ "$2" == GOBIN ]]; then printf '%s\\n' "$WORKSPACE_TEST_BIN"; else exit 94; fi ;;
 *) exit 93 ;;
esac''')
        self.executable('workit', 'printf "version %s\\n" "$*" >> "$WORKSPACE_TEST_LOG"')
        result = self.run_script('scripts/install-cli.sh')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.log.read_text().splitlines(), ['install github.com/cohesian-tools/workit@v0.1.0', 'version --version'])
        self.assertFalse((self.root / '.venv-cli').exists())

    def test_installer_failure_is_not_reported_as_success(self):
        self.executable('go', 'exit 9')
        result = self.run_script('scripts/install-cli.sh')
        self.assertEqual(result.returncode, 9)
        self.assertNotIn('Installed in', result.stdout)

    def test_bootstrap_only_forwards_workit_with_root_and_arguments(self):
        self.executable('workit', 'printf "<%s>\\n" "$@" >> "$WORKSPACE_TEST_LOG"')
        result = self.run_script('scripts/bootstrap.sh', '--dry-run')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.log.read_text().splitlines(), ['<-C>', f'<{self.root.resolve()}>', '<sync>', '<workdir>', '<add>', '<--dry-run>'])

    def test_macos_guard_and_package_failure_never_touch_profiles(self):
        self.executable('uname', 'printf "Linux\\n"')
        result = self.run_script('scripts/macos/setup.sh')
        self.assertEqual(result.returncode, 1)
        self.executable('uname', 'printf "Darwin\\n"')
        self.executable('brew', '''
case "$1" in
 shellenv) exit 0 ;;
 install) printf '%s\\n' "$*" >> "$WORKSPACE_TEST_LOG"; exit 8 ;;
 *) exit 91 ;;
esac''')
        result = self.run_script('scripts/macos/setup.sh')
        self.assertEqual(result.returncode, 8)
        self.assertEqual(self.log.read_text().strip(), 'install git gh go')


if __name__ == '__main__':
    unittest.main()
