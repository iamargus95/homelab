#!/usr/bin/env python3
"""Initialize Audiobookshelf and verify its account and libraries."""
import fcntl
import json
import os
from pathlib import Path
import secrets
import sys
import tempfile
import urllib.error
import urllib.request

CREDENTIAL_FILE = Path('/opt/media-stack/admin-credentials.json')
LIBRARIES = (
    ('Audiobooks', 'book', '/audiobooks'),
    ('Podcasts', 'podcast', '/podcasts'),
)


def credentials(initializing):
    if CREDENTIAL_FILE.is_symlink() or CREDENTIAL_FILE.stat().st_mode & 0o077:
        raise RuntimeError('Expected the private, regular shared credential file')
    shared = json.loads(CREDENTIAL_FILE.read_text())
    if 'audiobookshelf' in shared:
        return shared['audiobookshelf']
    if not initializing:
        raise RuntimeError('Audiobookshelf is already initialized without a saved account')
    account = {'username': 'admin', 'password': secrets.token_urlsafe(32)}
    shared['audiobookshelf'] = account
    fd, name = tempfile.mkstemp(prefix='.admin-credentials-', dir=CREDENTIAL_FILE.parent)
    try:
        with os.fdopen(fd, 'w') as file:
            json.dump(shared, file, indent=2)
            file.write('\n')
            file.flush()
            os.fsync(file.fileno())
        os.replace(name, CREDENTIAL_FILE)
    finally:
        Path(name).unlink(missing_ok=True)
    return account


def configure(base):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    token = None

    def api(path, payload=None):
        headers = {'Accept': 'application/json'}
        data = None
        if payload is not None:
            headers['Content-Type'] = 'application/json'
            data = json.dumps(payload).encode()
        if token:
            headers['Authorization'] = f'Bearer {token}'
        req = urllib.request.Request(base + path, data=data, headers=headers)
        try:
            with opener.open(req, timeout=30) as response:
                return json.load(response) if response.headers.get_content_type() == 'application/json' else None
        except urllib.error.HTTPError as error:
            raise RuntimeError(f'{req.get_method()} {path} returned HTTP {error.code}') from None

    status = api('/status')
    if status.get('app') != 'audiobookshelf' or not isinstance(status.get('isInit'), bool):
        raise RuntimeError('Unexpected Audiobookshelf server status')
    initializing = not status['isInit']
    account = credentials(initializing)
    if initializing:
        api('/init', {'newRoot': account})
    user = api('/login', account)['user']
    if user.get('username') != account['username'] or user.get('type') != 'root':
        raise RuntimeError('Saved Audiobookshelf account is not the root account')
    token = user['accessToken']
    if not token:
        raise RuntimeError('Audiobookshelf login did not return an access token')

    existing = api('/api/libraries')['libraries']
    changed = initializing
    for name, media_type, path in LIBRARIES:
        matches = [lib for lib in existing if lib['name'] == name or any(
            folder.get('fullPath') == path for folder in lib['folders']
        )]
        if not matches:
            library = api('/api/libraries', {
                'name': name, 'mediaType': media_type, 'folders': [{'fullPath': path}],
            })
            matches = [library]
            changed = True
        if len(matches) != 1 or matches[0]['mediaType'] != media_type or not any(
            folder.get('fullPath') == path for folder in matches[0]['folders']
        ):
            raise RuntimeError(f'Existing library conflicts with the {name} mount')
    print(json.dumps({'changed': changed, 'libraries_verified': len(LIBRARIES)}))


if __name__ == '__main__':
    try:
        lock_path = CREDENTIAL_FILE.parent / '.audiobookshelf-bootstrap.lock'
        lock = os.open(lock_path, os.O_CREAT | os.O_NOFOLLOW | os.O_WRONLY, 0o600)
        with os.fdopen(lock, 'w') as file:
            fcntl.flock(file, fcntl.LOCK_EX)
            configure(sys.argv[1])
    except (OSError, RuntimeError, ValueError, KeyError) as error:
        sys.exit(str(error))
