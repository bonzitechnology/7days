import os
import shutil
from pathlib import Path
import unittest
import sys

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))
import setup_7days

class TestHomebrewLogic(unittest.TestCase):
    def setUp(self):
        self.mock_root = Path("/tmp/mock_brew_logic")
        if self.mock_root.exists():
            shutil.rmtree(self.mock_root)
        self.mock_root.mkdir(parents=True)
        
        # Mock Cellar
        self.cellar = self.mock_root / "Cellar"
        self.cellar.mkdir()
        
        # Mock binaries
        self.bin_dir = self.mock_root / "bin"
        self.bin_dir.mkdir()

    def create_mock_binary(self, name, cellar_name):
        real_path = self.cellar / cellar_name / "1.0.0" / "bin" / name
        real_path.parent.mkdir(parents=True, exist_ok=True)
        real_path.write_text("#!/bin/sh\necho 1.0.0")
        real_path.chmod(0o755)
        
        link_path = self.bin_dir / name
        if link_path.exists():
            link_path.unlink()
        os.symlink(real_path, link_path)
        return link_path

    def test_brew_detection_npm(self):
        path = self.create_mock_binary("npm", "node")
        self.assertTrue(setup_7days.is_homebrew_managed(path))
        
        import io
        from contextlib import redirect_stdout
        f = io.StringIO()
        with redirect_stdout(f):
            setup_7days.version_too_low("npm", "11.9.0", (11, 10, 0), str(path))
        
        output = f.getvalue()
        self.assertIn("managed by Homebrew", output)
        self.assertIn("brew upgrade node", output)

    def test_brew_detection_composer(self):
        path = self.create_mock_binary("composer", "composer")
        self.assertTrue(setup_7days.is_homebrew_managed(path))
        
        import io
        from contextlib import redirect_stdout
        f = io.StringIO()
        with redirect_stdout(f):
            setup_7days.version_too_low("composer", "2.9.5", (2, 10, 0), str(path))
        
        output = f.getvalue()
        self.assertIn("managed by Homebrew", output)
        self.assertIn("brew upgrade composer", output)

    def test_non_brew_pip(self):
        # Create a non-brew pip
        other_dir = self.mock_root / "other" / "bin"
        other_dir.mkdir(parents=True)
        pip_path = other_dir / "pip"
        pip_path.write_text("#!/usr/bin/python3\n")
        pip_path.chmod(0o755)
        
        self.assertFalse(setup_7days.is_homebrew_managed(pip_path))
        
        import io
        from contextlib import redirect_stdout
        f = io.StringIO()
        with redirect_stdout(f):
            setup_7days.version_too_low("pip", "20.0.0", (26, 0, 0), str(pip_path))
        
        output = f.getvalue()
        self.assertNotIn("Homebrew", output)
        # Should suggest the python -m pip format
        self.assertIn("-m pip install --upgrade pip", output)

if __name__ == "__main__":
    unittest.main()
