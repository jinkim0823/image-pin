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
            ldconfig = tools / 'ldconfig'
            ldconfig.write_text('#!/bin/bash\necho "libxcb-cursor.so.0 (libc6,x86-64) => /stub"\n')
            ldconfig.chmod(0o755)
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
            ldconfig.write_text('#!/bin/bash\nexit 0\n')
            result = subprocess.run(['bash', str(source / 'install.sh')], env=env, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('libxcb-cursor0', result.stderr)
            self.assertFalse(installed.is_symlink())
            ldconfig.write_text('#!/bin/bash\necho "libxcb-cursor.so.0 (libc6,x86-64) => /stub"\n')
            installed.write_text('unrelated tool')
            result = subprocess.run(['bash', str(source / 'install.sh')], env=env, capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(installed.read_text(), 'unrelated tool')

    def test_helper_only_skips_extension_build_and_keeps_extensions(self):
        with tempfile.TemporaryDirectory(prefix='image-pin-helper-') as tmp:
            root = Path(tmp)
            source = root / 'source'
            source.mkdir()
            for name in ('install.sh', 'uninstall.sh', 'bin'):
                shutil.copytree(PROJECT / name, source / name) if (PROJECT / name).is_dir() \
                    else shutil.copy(PROJECT / name, source / name)
            tools = root / 'tools'
            tools.mkdir()
            called = root / 'node-tool-called'
            stubs = {'uv': 'exit 0', 'gnome-screenshot': 'exit 0',
                     'ldconfig': 'echo "libxcb-cursor.so.0 (libc6,x86-64) => /stub"'}
            # Node tools must be neither required nor run for a helper-only install.
            for name in ('npm', 'node', 'vicinae'):
                stubs[name] = f'touch "{called}"; exit 1'
            for name, body in stubs.items():
                (tools / name).write_text(f'#!/bin/bash\n{body}\n')
                (tools / name).chmod(0o755)
            bin_dir = root / 'bin'
            extension = root / 'data/vicinae/extensions/image-pin'
            extension.mkdir(parents=True)
            (extension / 'package.json').write_text('{"name": "image-pin", "author": "jinkim0823"}')
            env = {**os.environ, 'PATH': str(tools) + os.pathsep + os.environ['PATH'],
                   'IMAGE_PIN_BIN_DIR': str(bin_dir), 'XDG_DATA_HOME': str(root / 'data')}
            result = subprocess.run(['bash', str(source / 'install.sh'), '--helper-only'],
                                    env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((bin_dir / 'image-pin').is_symlink())
            self.assertFalse(called.exists())
            subprocess.run(['bash', str(source / 'uninstall.sh'), '--helper-only'],
                           env=env, check=True, capture_output=True)
            self.assertFalse((bin_dir / 'image-pin').is_symlink())
            self.assertTrue((extension / 'package.json').exists())
            result = subprocess.run(['bash', str(source / 'install.sh'), '--bogus'],
                                    env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)


    def test_missing_prerequisites_print_one_ready_command(self):
        with tempfile.TemporaryDirectory(prefix='image-pin-missing-') as tmp:
            root = Path(tmp)
            shutil.copy(PROJECT / 'install.sh', root / 'install.sh')
            # Only the shell utilities the installer itself uses; no uv,
            # gnome-screenshot or libxcb-cursor are visible.
            tools = root / 'tools'
            tools.mkdir()
            for name in ('dirname', 'grep'):
                (tools / name).symlink_to(shutil.which(name))
            (tools / 'ldconfig').write_text('#!/bin/bash\nexit 0\n')
            (tools / 'ldconfig').chmod(0o755)
            env = {**os.environ, 'PATH': str(tools)}
            result = subprocess.run([shutil.which('bash'), str(root / 'install.sh'), '--helper-only'],
                                    env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertIn('sudo apt install gnome-screenshot libxcb-cursor0', result.stderr)
            self.assertIn('uv: https://docs.astral.sh/uv/', result.stderr)
            self.assertNotIn('node', result.stderr)


if __name__ == '__main__':
    unittest.main()
