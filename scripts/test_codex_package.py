import io
import json
from pathlib import Path
import unittest
import zipfile
from scripts.build_codex_package import collect, sha


class CodexPackageContract(unittest.TestCase):
    def archive(self, extra=None):
        output = io.BytesIO()
        with zipfile.ZipFile(output, 'w') as archive:
            for name in ('python.exe', 'python314.dll', 'python314.zip', 'LICENSE.txt', 'python314._pth'):
                archive.writestr(name, 'test fixture')
            if extra:
                archive.writestr(extra, 'unsafe')
        data = output.getvalue()
        return data, {'sha256': sha(data), 'platform': 'windows-x64', 'version': '3.14.7'}

    def test_bundle_contains_one_core_isolated_paths_and_no_runtime_records(self):
        data, lock = self.archive()
        source = Path(__file__).resolve().parent.parent
        files = collect(source, data, lock, with_tests=True, dependencies={"mcp/__init__.py": b""})
        manifest = json.loads(files['package-manifest.json'])
        self.assertEqual(files['skills/skip/SKILL.md'], (source / 'SKILL.md').read_bytes())
        self.assertIn('skills/skip/adapters/codex/entry.py', files)
        self.assertIn('import site', files['runtime/windows-x64/python314._pth'].decode())
        self.assertFalse(any('/records/' in key or '/NOW/' in key or '/.git/' in key for key in files))
        self.assertFalse(any('/scripts/' in key for key in files))
        self.assertIn('skills/skip/skip_core/migrations/0001_initial.sql', files)
        for path, digest in manifest['files'].items():
            self.assertEqual(sha(files[path]), digest)

    def test_tampered_runtime_and_archive_escape_are_rejected(self):
        data, lock = self.archive()
        with self.assertRaisesRegex(ValueError, 'SHA-256'):
            collect(Path.cwd(), data + b'tampered', lock)
        data, lock = self.archive('../escape')
        with self.assertRaisesRegex(ValueError, 'unsafe'):
            collect(Path.cwd(), data, lock)
