#!/usr/bin/env python3
"""Claim a new Kuma instance on loopback; never emit credentials or session tokens."""
import argparse
import json
import os
from pathlib import Path
import pwd
import secrets
import subprocess
import time
import urllib.request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', default='/opt/uptime-kuma')
    parser.add_argument('--address', required=True)
    parser.add_argument('--port', type=int, default=3001)
    args = parser.parse_args()
    root = Path(args.root)
    owner = pwd.getpwnam('argus')
    credential_file = root / 'admin-credentials.json'
    if not credential_file.exists():
        fd = os.open(credential_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w') as f:
            json.dump({'username': 'admin', 'password': secrets.token_urlsafe(36)}, f)
            f.write('\n')
        os.chown(credential_file, owner.pw_uid, owner.pw_gid)
    credentials = json.loads(credential_file.read_text())
    for attempt in range(90):
        try:
            with urllib.request.urlopen(f'http://127.0.0.1:{args.port}/', timeout=3):
                break
        except OSError:
            if attempt == 89:
                raise RuntimeError('Uptime Kuma did not become ready on loopback')
            time.sleep(2)
    payload = dict(credentials, address=args.address)
    result = subprocess.run(
        ['docker', 'compose', '--project-directory', str(root), 'exec', '-T',
         'uptime-kuma', 'node', '-e', (root / 'bootstrap.js').read_text()],
        input=json.dumps(payload), text=True, capture_output=True, timeout=180)
    if result.returncode:
        # The JS helper only writes sanitized errors; do not emit the payload.
        raise RuntimeError('Kuma setup failed: ' + result.stderr[-1500:])
    status = json.loads(result.stdout)
    for name, content in [('setup-status.json', json.dumps(status, indent=2)+'\n'),
                          ('.configured-admin', 'Administrator and initial monitors configured.\n')]:
        path = root / name
        path.write_text(content)
        os.chmod(path, 0o640)
        os.chown(path, owner.pw_uid, owner.pw_gid)
    print(json.dumps(status))


if __name__ == '__main__':
    main()
