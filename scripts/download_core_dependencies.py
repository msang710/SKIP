#!/usr/bin/env python3
"""Fetch only the exact locked Windows wheels; never install into this machine."""
import argparse
import hashlib
import json
from pathlib import Path
import urllib.request


def download(source, target):
    lock=json.loads((source/'plugins/codex/dependency-lock.json').read_text())
    target.mkdir(parents=True,exist_ok=True)
    for wheel in lock['wheels']:
        path=target/wheel['filename']
        if path.exists():
            if hashlib.sha256(path.read_bytes()).hexdigest()!=wheel['sha256']:raise ValueError('Existing wheel differs: '+path.name)
            continue
        url='https://pypi.org/pypi/'+wheel['name']+'/'+wheel['version']+'/json'
        with urllib.request.urlopen(url,timeout=30) as response:metadata=json.load(response)
        match=[v for v in metadata['urls'] if v['filename']==wheel['filename'] and v['digests']['sha256']==wheel['sha256']]
        if len(match)!=1 or not match[0]['url'].startswith('https://files.pythonhosted.org/'):raise ValueError('Locked wheel unavailable')
        with urllib.request.urlopen(match[0]['url'],timeout=60) as response:data=response.read(100*1024*1024)
        if hashlib.sha256(data).hexdigest()!=wheel['sha256']:raise ValueError('Wheel digest mismatch')
        with path.open('xb') as out:out.write(data)
    print(json.dumps({'verified_wheels':len(lock['wheels'])}))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--target',type=Path,default=Path('.build/core-wheels-windows'))
    download(Path(__file__).resolve().parent.parent,p.parse_args().target)
