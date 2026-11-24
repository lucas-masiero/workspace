"""Interactive GitHub device/browser login, shared by both setup scripts."""
import shutil
import subprocess

from .manifest import WorkspaceError


def ssh_ready() -> bool:
    try:
        result = subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes",
                                 "-o", "ConnectTimeout=10", "-T", "git@github.com"],
                                capture_output=True, text=True, timeout=15)
        # GitHub deliberately returns 1 for a successful SSH authentication test.
        return result.returncode == 1 and "successfully authenticated" in result.stdout + result.stderr
    except (OSError, subprocess.TimeoutExpired):
        return False


def login() -> int:
    for command in ("gh", "git", "ssh"):
        if not shutil.which(command):
            raise WorkspaceError(f"{command} is missing; run this device's setup script first")
    try:
        ready = subprocess.run(["gh", "auth", "status", "--hostname", "github.com"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30).returncode == 0
        if ready and ssh_ready():
            print("GitHub CLI and SSH authentication are ready.")
            return 0
        print("Signing into GitHub. Follow the browser/device prompts; SSH key setup is handled by gh.", flush=True)
        code = subprocess.call(["gh", "auth", "login", "--hostname", "github.com", "--git-protocol", "ssh", "--web"])
        if code:
            return code
        print("Testing GitHub SSH. Verify a new host fingerprint against:", flush=True)
        print("https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/githubs-ssh-key-fingerprints", flush=True)
        result = subprocess.run(["ssh", "-o", "ConnectTimeout=10", "-T", "git@github.com"],
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=60)
        print(result.stdout.strip())
        if result.returncode != 1 or "successfully authenticated" not in result.stdout:
            raise WorkspaceError("GitHub SSH is not ready. Check your registered SSH key/agent, then rerun workspace repo login.")
        return 0
    except subprocess.TimeoutExpired as error:
        raise WorkspaceError("Authentication timed out; rerun workspace repo login") from error
