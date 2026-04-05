import os
import shutil
import subprocess
import sys
from pathlib import Path
import unittest

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))
import setup_7days

class TestBrewDetection(unittest.TestCase):
    def setUp(self):
        # Create a mock Homebrew Cellar structure
        self.test_root = Path("tests/mock_brew")
        if self.test_root.exists():
            shutil.rmtree(self.test_root)
        
        self.cellar = self.test_root / "Cellar"
        self.bin_dir = self.test_root / "bin"
        
        self.cellar.mkdir(parents=True)
        self.bin_dir.mkdir(parents=True)
        
        # Create a mock npm binary in Cellar
        self.npm_real_path = self.cellar / "node" / "25.6.1_1" / "bin" / "npm"
        self.npm_real_path.parent.mkdir(parents=True)
        self.npm_real_path.write_text("#!/bin/sh\necho 11.9.0")
        self.npm_real_path.chmod(0o755)
        
        # Symlink it to mock bin dir
        self.npm_link_path = self.bin_dir / "npm"
        os.symlink(self.npm_real_path, self.npm_link_path)

    def test_is_homebrew_managed(self):
        self.assertTrue(setup_7days.is_homebrew_managed(self.npm_link_path))
        self.assertTrue(setup_7days.is_homebrew_managed(self.npm_real_path))
        
        # Test non-brew path
        dummy = self.test_root / "some-other-tool"
        dummy.write_text("test")
        self.assertFalse(setup_7days.is_homebrew_managed(dummy))

    def test_suggestion_logic(self):
        # We'll capture stdout to verify the suggestion
        import io
        from contextlib import redirect_stdout
        
        f = io.StringIO()
        with redirect_stdout(f):
            setup_7days.version_too_low("npm", "11.9.0", (11, 10, 0), str(self.npm_link_path))
        
        output = f.getvalue()
        self.assertIn("appears to be managed by Homebrew", output)
        self.assertIn("brew upgrade node", output)

if __name__ == "__main__":
    unittest.main()
