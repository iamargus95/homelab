#!/usr/bin/env python3
"""Add Kuma to an existing private media credential file without printing secrets."""
import argparse
import json
import os
from pathlib import Path
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', default='/opt/uptime-kuma/admin-credentials.json')
    parser.add_argument('--destination', default='/opt/media-stack/admin-credentials.json')
    args = parser.parse_args()
    destination = Path(args.destination)
    if not destination.exists():
        print(json.dumps({'changed': False, 'reason': 'No media credential file present'}))
        return
    if destination.is_symlink():
        raise RuntimeError('Refusing to replace a symlinked credential file')
    credentials = json.loads(Path(args.source).read_text())
    if not credentials.get('username') or not credentials.get('password'):
        raise RuntimeError('Kuma credentials are incomplete')
    current = json.loads(destination.read_text())
    if 'uptime-kuma' in current:
        print(json.dumps({'changed': False, 'entry': 'uptime-kuma'}))
        return
    info = destination.stat()
    current['uptime-kuma'] = credentials
    fd, temporary = tempfile.mkstemp(prefix='.credentials-', dir=destination.parent)
    try:
        with os.fdopen(fd, 'w') as f:
            os.fchmod(f.fileno(), 0o600)
            if os.geteuid() == 0:
                os.fchown(f.fileno(), info.st_uid, info.st_gid)
            json.dump(current, f, indent=2)
            f.write('\n')
        os.replace(temporary, destination)
    finally:
        Path(temporary).unlink(missing_ok=True)
    print(json.dumps({'changed': True, 'entry': 'uptime-kuma'}))


if __name__ == '__main__':
    main()
