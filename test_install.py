"""Installer regression with isolated paths and stub build tools."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

PROJECT = Path(__file__).resolve().parent


class InstallerTests(unittest.TestCase):
    def test_install_and_uninstall_from_path_with_spaces(self):
        with tempfile.TemporaryDirectory(prefix='image-pin-install-') as tmp:
            root = Path(tmp)
            source = root / 'source with spaces'
            source.mkdir()
            for name in ('install.sh', 'uninstall.sh', 'bin', 'extension', 'pyproject.toml'):
                item = PROJECT / name
                if item.is_dir():
                    shutil.copytree(item, source / name, ignore=shutil.ignore_patterns('node_modules'))
                else:
                    shutil.copy(item, source / name)
            tools = root / 'tools'
            tools.mkdir()
            for name in ('uv', 'npm', 'vicinae', 'gnome-screenshot'):
                script = tools / name
                script.write_text('#!/bin/bash\nexit 0\n')
                script.chmod(0o755)
            bin_dir = root / 'bin with spaces'
            env = {**os.environ, 'PATH': str(tools) + os.pathsep + os.environ['PATH'],
                   'IMAGE_PIN_BIN_DIR': str(bin_dir), 'XDG_DATA_HOME': str(root / 'data')}
            subprocess.run(['bash', str(source / 'install.sh')], env=env, check=True, capture_output=True)
            installed = bin_dir / 'image-pin'
            self.assertTrue(installed.is_symlink())
            self.assertEqual(installed.resolve(), source / 'bin/image-pin')
            subprocess.run(['bash', str(source / 'uninstall.sh')], env=env, check=True, capture_output=True)
            self.assertFalse(installed.is_symlink())
            self.assertTrue(source.exists())
            bin_dir.mkdir(exist_ok=True)
            installed.write_text('unrelated tool')
            result = subprocess.run(['bash', str(source / 'install.sh')], env=env, capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(installed.read_text(), 'unrelated tool')


if __name__ == '__main__':
    unittest.main()
