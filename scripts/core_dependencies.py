"""Build-time wheel verification. No pip execution or downloads at runtime."""
import hashlib
import json
from pathlib import Path,PurePosixPath
import stat
import zipfile


def collect_dependencies(source, wheelhouse):
    lock=json.loads((source/'plugins/codex/dependency-lock.json').read_text())
    result={}
    for wheel in lock['wheels']:
        p=wheelhouse/wheel['filename']
        if p.is_symlink() or hashlib.sha256(p.read_bytes()).hexdigest()!=wheel['sha256']:
            raise ValueError('dependency wheel SHA-256 mismatch: '+wheel['filename'])
        with zipfile.ZipFile(p) as archive:
            if sum(i.file_size for i in archive.infolist())>200*1024*1024:
                raise ValueError('dependency wheel exceeds bound')
            for item in archive.infolist():
                path=PurePosixPath(item.filename)
                if path.is_absolute() or '..' in path.parts or '\\' in item.filename or ':' in item.filename or stat.S_ISLNK(item.external_attr>>16):
                    raise ValueError('unsafe dependency archive member')
                if item.is_dir():continue
                parts=path.parts
                if parts[0].endswith('.data'):
                    if len(parts)<3 or parts[1] not in ('purelib','platlib'):
                        # Console scripts/data are not needed; entrypoints call Python modules.
                        continue
                    path=PurePosixPath(*parts[2:])
                name=path.as_posix()
                if name in result:raise ValueError('duplicate dependency member: '+name)
                result[name]=archive.read(item)
    if 'mcp/__init__.py' not in result:raise ValueError('MCP SDK missing from dependency bundle')
    return result
