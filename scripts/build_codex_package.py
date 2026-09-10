#!/usr/bin/env python3
"""Build (never install/publish) an isolated Codex plugin with pinned Windows Python."""
from __future__ import annotations
import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import stat
import urllib.request
import zipfile



def sha(data):
    return hashlib.sha256(data).hexdigest()


def collect(source, runtime_zip, lock, *, with_tests=False, dependencies=None):
    if sha(runtime_zip) != lock['sha256']:
        raise ValueError('embedded runtime SHA-256 mismatch')
    files = {}
    runtime_prefix = 'runtime/' + lock['platform'] + '/'
    with zipfile.ZipFile(io.BytesIO(runtime_zip)) as archive:
        if sum(item.file_size for item in archive.infolist()) > 100 * 1024 * 1024:
            raise ValueError('runtime archive exceeds size limit')
        for item in archive.infolist():
            path = PurePosixPath(item.filename)
            if path.is_absolute() or '..' in path.parts or '\\' in item.filename or ':' in item.filename or stat.S_ISLNK(item.external_attr >> 16):
                raise ValueError('unsafe runtime archive member')
            if not item.is_dir():
                key = runtime_prefix + item.filename
                if key in files:
                    raise ValueError('duplicate runtime archive member')
                files[key] = archive.read(item)
    for name in ('python.exe', 'python314.dll', 'python314.zip', 'LICENSE.txt', 'python314._pth'):
        if runtime_prefix + name not in files:
            raise ValueError('embedded runtime missing ' + name)
    # Isolated embedded interpreter. site processes pywin32's bundled DLL bootstrap;
    # isolated mode disables user-site and environment Python path injection.
    files[runtime_prefix + 'python314._pth'] = b'python314.zip\n.\n../../skills/skip\nLib/site-packages\nimport site\n'
    if dependencies is None:
        raise ValueError('validated dependency bundle is required')
    for name, data in dependencies.items():
        files[runtime_prefix + 'Lib/site-packages/' + name] = data
    for directory in ('skip_core', 'skip_mcp', 'adapters', 'schemas'):
        for path in sorted((source / directory).rglob('*')):
            if '__pycache__' in path.parts or not path.is_file():
                continue
            if path.is_symlink():
                raise ValueError('source symlink is not distributable')
            if path.suffix not in ('.py', '.sql', '.json'):
                continue
            files['skills/skip/' + path.relative_to(source).as_posix()] = path.read_bytes()
    ui = source / 'ui/mcp-app/dist/index.html'
    if not ui.is_file():
        raise ValueError('build MCP App assets first')
    files['skills/skip/ui/mcp-app/dist/index.html'] = ui.read_bytes()
    for name in ('db-core-contract.md',):
        files['skills/skip/references/' + name] = (source / 'references' / name).read_bytes()
    if with_tests:
        for path in sorted((source / 'tests').rglob('*.py')):
            if '__pycache__' not in path.parts and path.name != 'test_migration.py':
                files['skills/skip/' + path.relative_to(source).as_posix()] = path.read_bytes()
    for origin, target in [('SKILL.md', 'skills/skip/SKILL.md'), ('agents/openai.yaml', 'skills/skip/agents/openai.yaml'),
                           ('LICENSE', 'LICENSE'), ('plugins/codex/skip/.codex-plugin/plugin.json', '.codex-plugin/plugin.json')]:
        files[target] = (source / origin).read_bytes()
    files['skip.cmd'] = b'@echo off\r\n"%~dp0runtime\\windows-x64\\python.exe" -X utf8 -B -m adapters.codex.entry %*\r\n'
    files['skip-core.cmd'] = b'@echo off\r\n"%~dp0runtime\\windows-x64\\python.exe" -X utf8 -B -m skip_core.cli %*\r\n'
    files['skip-mcp.cmd'] = b'@echo off\r\n"%~dp0runtime\\windows-x64\\python.exe" -X utf8 -B -m skip_mcp.server %*\r\n'
    manifest = {'schema': 'skip-package/v1', 'platform': lock['platform'], 'python': lock,
                'entrypoint': {'executable': runtime_prefix + 'python.exe',
                               'arguments': ['-X', 'utf8', '-B', '-m', 'adapters.codex.entry']},
                'host_enforcement': 'advisory', 'files': {name: sha(data) for name, data in sorted(files.items())}}
    files['package-manifest.json'] = (json.dumps(manifest, ensure_ascii=False, indent=2) + '\n').encode()
    return files


def build(source, output, runtime_path=None, with_tests=False, wheelhouse=None):
    lock = json.loads((source / 'plugins/codex/runtime-lock.json').read_text())
    if runtime_path:
        runtime = runtime_path.read_bytes()
    else:
        with urllib.request.urlopen(lock['url'], timeout=60) as response:
            runtime = response.read(32 * 1024 * 1024)
    if not __package__:
        from core_dependencies import collect_dependencies
    else:
        from scripts.core_dependencies import collect_dependencies
    dependencies = collect_dependencies(source, wheelhouse or source / '.build/core-wheels-windows')
    files = collect(source, runtime, lock, with_tests=with_tests, dependencies=dependencies)
    if output.exists():
        raise ValueError('output exists; choose a new artifact path')
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'x', compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo('skip/' + name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data)
    return {'status': 'built', 'path': str(output), 'sha256': sha(output.read_bytes()),
            'files': len(files), 'windows_execution': 'NOT_RUN', 'app_installation': 'NOT_RUN'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--runtime-zip', type=Path)
    parser.add_argument('--with-tests', action='store_true')
    parser.add_argument('--wheelhouse', type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(build(args.source, args.output, args.runtime_zip, args.with_tests, args.wheelhouse)))
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        parser.exit(2, str(exc) + '\n')


if __name__ == '__main__':
    main()
