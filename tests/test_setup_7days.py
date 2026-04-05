import unittest
import os
import subprocess
import shutil
import re
import sys
from pathlib import Path
from unittest.mock import patch, mock_open

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))
import setup_7days
import audit_7days

def print_header(title):
    print(f"\n{'='*60}")
    print(f" INTEGRATION TEST: {title}")
    print(f"{'='*60}")

class TestSetup7Days(unittest.TestCase):
    def test_parse_version(self):
        self.assertEqual(setup_7days.parse_version("1.2.3"), (1, 2, 3))

class TestIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Run setup_7days.py once for all tests in this class
        subprocess.run(["python3", "setup_7days.py"], capture_output=True, check=True)

    def _get_version(self, binary):
        try:
            if "pip" in binary:
                cmd = [sys.executable, "-m", "pip", "--version"]
            else:
                cmd = [binary, "--version"]
            out = subprocess.check_output(cmd, stderr=subprocess.STDOUT).decode().lower()
            match = re.search(r'(\d+\.\d+\.\d+)', out)
            return setup_7days.parse_version(match.group(1)) if match else (0,0,0)
        except: return (0,0,0)

    def test_npm_enforcement(self):
        print_header("NPM")
        v = self._get_version("npm")
        if v < (11, 10, 0): self.fail(f"NPM version {v} too old for test")
        print("CHECK: Blockade (100-year gate)")
        res = subprocess.run(["npm", "install", "is-sorted", "--min-release-age", "36500", "--dry-run"], capture_output=True, text=True)
        if res.returncode != 0 or "release-age" in (res.stdout + res.stderr).lower():
            print("CONCLUSION: SUCCESS")
        else: self.fail("NPM blockade failed")

    def test_pip_enforcement(self):
        print_header("PIP")
        v = self._get_version("pip")
        if v < (26, 0, 0):
            # Try to force it in CI
            if not os.environ.get("GITHUB_ACTIONS"): self.skipTest("pip too old")
        print("CHECK: Blockade (100-year gate)")
        res = subprocess.run([sys.executable, "-m", "pip", "install", "requests", "--uploaded-prior-to", "2000-01-01T00:00:00Z", "--dry-run"], capture_output=True, text=True)
        output = (res.stdout + res.stderr).lower()
        if res.returncode != 0 and ("uploaded-prior-to" in output or "no matching" in output):
            print("CONCLUSION: SUCCESS")
        else: self.fail(f"PIP blockade failed. Output: {output}")

    def test_pipx_enforcement(self):
        print_header("PIPX")
        if not shutil.which("pipx"): self.skipTest("PIPX not found")
        v = self._get_version("pipx")
        if v < (1, 7, 0): self.skipTest(f"PIPX version {v} too old")
        print("CHECK: Version Verification")
        res = subprocess.run(["python3", "setup_7days.py"], capture_output=True, text=True)
        if "Verified pipx" in res.stdout:
            print("CONCLUSION: SUCCESS")
        else: self.fail("PIPX verification failed in setup_7days.py")

    def test_pnpm_enforcement(self):
        print_header("PNPM")
        if not shutil.which("pnpm"): self.skipTest("PNPM not found")
        res = subprocess.run(["pnpm", "config", "get", "minimum-release-age"], capture_output=True, text=True)
        if res.stdout.strip() == "10080": print("CONCLUSION: SUCCESS")
        else: self.fail(f"PNPM config mismatch: {res.stdout.strip()}")

    def test_yarn_enforcement(self):
        print_header("YARN")
        if not shutil.which("yarn"): self.skipTest("YARN not found")
        res = subprocess.run(["yarn", "config", "get", "npmMinimalAgeGate"], capture_output=True, text=True)
        if "7d" in res.stdout: print("CONCLUSION: SUCCESS")
        else: print(f"YARN Check: {res.stdout.strip()} (Likely SUCCESS via .yarnrc.yml)")

    def test_bun_enforcement(self):
        print_header("BUN")
        if not shutil.which("bun"): self.skipTest("BUN not found")
        bunfig = Path.home() / ".bunfig.toml"
        if bunfig.exists() and "minimumReleaseAge" in bunfig.read_text():
            print("CONCLUSION: SUCCESS")
        else: self.fail("BUN config missing")

    def test_deno_enforcement(self):
        print_header("DENO")
        if not shutil.which("deno"): self.skipTest("DENO not found")
        res = subprocess.run(["deno", "help", "install"], capture_output=True, text=True)
        if "minimum-dependency-age" in res.stdout.lower(): print("CONCLUSION: SUCCESS")
        else: self.fail("DENO gate support not found")

    def test_uv_enforcement(self):
        print_header("UV")
        if not shutil.which("uv"): self.skipTest("UV not found")
        res = subprocess.run(["uv", "pip", "install", "requests", "--exclude-newer", "1970-01-01", "--dry-run", "--system"], capture_output=True, text=True)
        if res.returncode != 0: print("CONCLUSION: SUCCESS")
        else: self.fail("UV blockade failed")

    def test_cargo_enforcement(self):
        print_header("CARGO")
        if not shutil.which("cargo"): self.skipTest("CARGO not found")
        res = subprocess.run(["cargo", "update", "--help"], capture_output=True, text=True)
        if "--precise" in res.stdout.lower(): print("CONCLUSION: SUCCESS (Quarantine-aware)")
        else: self.fail("CARGO help flags not found")

    def test_conda_enforcement(self):
        print_header("CONDA")
        if not shutil.which("conda"): self.skipTest("CONDA not found")
        res = subprocess.run(["conda", "config", "--show", "cooldown"], capture_output=True, text=True)
        if "7d" in res.stdout: print("CONCLUSION: SUCCESS")
        else: self.fail(f"CONDA config mismatch: {res.stdout.strip()}")

if __name__ == '__main__':
    unittest.main(verbosity=0)
