import subprocess
import os
import json
import re
import shutil
from pathlib import Path
import unittest

class Test7DaysIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Run setup_7days.py once for all tests in this class
        subprocess.run(["python3", "setup_7days.py"], check=True)

    def test_npm_config(self):
        npmrc = Path.home() / ".npmrc"
        if shutil.which("npm"):
            self.assertTrue(npmrc.exists(), ".npmrc should exist")
            self.assertIn("min-release-age=7", npmrc.read_text())

    def test_pnpm_config(self):
        if shutil.which("pnpm"):
            pnpmrc = Path.home() / ".config" / "pnpm" / "rc"
            self.assertTrue(pnpmrc.exists(), "pnpmrc should exist")
            self.assertIn("minimum-release-age=10080", pnpmrc.read_text())

    def test_bun_config(self):
        if shutil.which("bun"):
            bunfig = Path.home() / ".bunfig.toml"
            self.assertTrue(bunfig.exists(), ".bunfig.toml should exist")
            self.assertIn("minimumReleaseAge = 604800", bunfig.read_text())

    def test_deno_config(self):
        if shutil.which("deno"):
            deno_json = Path.home() / ".deno.json"
            self.assertTrue(deno_json.exists(), ".deno.json should exist")
            self.assertIn("minimumDependencyAge", deno_json.read_text())

    def test_pip_config(self):
        if shutil.which("pip") or shutil.which("pip3"):
            pip_conf = Path.home() / ".config" / "pip" / "pip.conf"
            self.assertTrue(pip_conf.exists(), "pip.conf should exist")
            self.assertIn("uploaded-prior-to", pip_conf.read_text())
            self.assertIn("[global]", pip_conf.read_text())

    def test_pipx_config(self):
        if shutil.which("pipx"):
            # setup_7days.py should have verified pipx
            res = subprocess.run(["python3", "setup_7days.py"], capture_output=True, text=True)
            self.assertIn("Verified pipx", res.stdout)

    def test_uv_env(self):
        if shutil.which("uv"):
            found = False
            for prof in [".bashrc", ".zshrc", ".bash_profile"]:
                p = Path.home() / prof
                if p.exists() and "UV_EXCLUDE_NEWER" in p.read_text():
                    found = True
                    break
            self.assertTrue(found, "UV_EXCLUDE_NEWER not found in shell profiles")

    def test_composer_config(self):
        if shutil.which("composer"):
            # Check version first
            v_out = subprocess.check_output(["composer", "--version"], stderr=subprocess.STDOUT).decode()
            v_match = re.search(r'Composer version (\d+\.\d+\.\d+)', v_out)
            if v_match:
                v = tuple(map(int, v_match.group(1).split('.')))
                if v >= (2, 10, 0):
                    res = subprocess.run(["composer", "config", "--global", "minimum-release-age"], capture_output=True, text=True)
                    self.assertIn("7 days", res.stdout)
                else:
                    self.skipTest(f"Composer version {v_match.group(1)} too old for release-age gate")

    def test_npm_blockade(self):
        if shutil.which("npm"):
            res = subprocess.run(["npm", "install", "is-sorted", "--min-release-age", "36500", "--dry-run"], capture_output=True, text=True)
            output = (res.stdout + res.stderr).lower()
            self.assertTrue(res.returncode != 0 or "release-age" in output or "not found" in output)

    def test_audit_npm(self):
        lockfile = {
            "name": "test",
            "version": "1.0.0",
            "lockfileVersion": 3,
            "requires": True,
            "packages": {
                "": { "name": "test", "version": "1.0.0" },
                "node_modules/is-sorted": { "version": "1.0.0" }
            }
        }
        Path("package-lock.json").write_text(json.dumps(lockfile))
        res = subprocess.run(["python3", "audit_7days.py", "--npm"], capture_output=True, text=True)
        self.assertIn("Auditing package-lock.json", res.stdout)
        self.assertIn("No 'young' JS packages found", res.stdout)
        os.remove("package-lock.json")

    def test_audit_cargo(self):
        lockfile = """
[[package]]
name = "serde"
version = "1.0.0"
"""
        Path("Cargo.lock").write_text(lockfile)
        res = subprocess.run(["python3", "audit_7days.py", "--cargo"], capture_output=True, text=True)
        self.assertIn("Auditing Cargo.lock", res.stdout)
        # serde 1.0.0 is old
        self.assertIn("No 'young' Cargo packages found", res.stdout)
        os.remove("Cargo.lock")

    def test_audit_pipx(self):
        if shutil.which("pipx"):
            res = subprocess.run(["python3", "audit_7days.py", "--pipx"], capture_output=True, text=True)
            self.assertIn("Auditing pipx installed packages", res.stdout)
            # Should be empty or no danger if nothing installed
            self.assertIn("No 'young' pipx packages found", res.stdout)

if __name__ == "__main__":
    unittest.main()
