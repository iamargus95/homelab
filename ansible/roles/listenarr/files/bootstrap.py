#!/usr/bin/env python3
"""Connect Listenarr to the existing homelab services."""
import fcntl
import http.cookiejar
import json
import os
from pathlib import Path
import secrets
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

CREDENTIALS = Path('/opt/media-stack/admin-credentials.json')
LIBRARY = '/data/library/audiobooks'
DOWNLOADS = '/data/downloads/torrents/audiobooks'
INDEXERS = ('Knaben', 'The Pirate Bay')


def request(opener, base, path, *, payload=None, headers=None, form=False, timeout=30, method=None):
    headers = dict(headers or {})
    data = None
    if payload is not None:
        headers['Content-Type'] = 'application/x-www-form-urlencoded' if form else 'application/json'
        data = (urllib.parse.urlencode(payload) if form else json.dumps(payload)).encode()
    req = urllib.request.Request(base + path, data=data, headers=headers, method=method)
    try:
        with opener.open(req, timeout=timeout) as response:
            if response.headers.get_content_type() == 'application/json':
                return json.load(response)
            return response.read().decode()
    except urllib.error.HTTPError as error:
        if error.code == 401 and path.endswith('/account/login'):
            return None
        raise RuntimeError(f'{req.get_method()} {path} returned HTTP {error.code}') from None


def save_account(registry):
    account = {'username': 'admin', 'password': secrets.token_urlsafe(32) + 'aA7!'}
    registry['listenarr'] = account
    fd, name = tempfile.mkstemp(prefix='.admin-credentials-', dir=CREDENTIALS.parent)
    try:
        with os.fdopen(fd, 'w') as out:
            json.dump(registry, out, indent=2)
            out.write('\n')
            out.flush()
            os.fsync(out.fileno())
        os.replace(name, CREDENTIALS)
    finally:
        Path(name).unlink(missing_ok=True)
    return account


def configure_category(host, account):
    base = f'http://{host}:8080'
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}), urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()),
    )
    headers = {'Origin': base, 'Referer': base + '/'}
    request(opener, base, '/api/v2/auth/login', payload=account, headers=headers, form=True)
    categories = request(opener, base, '/api/v2/torrents/categories', headers=headers)
    if 'audiobooks' not in categories:
        request(opener, base, '/api/v2/torrents/createCategory',
                payload={'category': 'audiobooks', 'savePath': DOWNLOADS}, headers=headers, form=True)
        return True
    if categories['audiobooks']['savePath'].rstrip('/') != DOWNLOADS:
        raise RuntimeError('The existing qBittorrent audiobook category has a different save path')
    return False


def configure(base, root, host):
    if CREDENTIALS.is_symlink() or CREDENTIALS.stat().st_mode & 0o077:
        raise RuntimeError('Expected the private shared credential file')
    registry = json.loads(CREDENTIALS.read_text())
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    startup = json.loads((Path(root) / 'config/config.json').read_text())
    api_key = startup.get('ApiKey') or startup['apiKey']

    def listen(path, payload=None, auth=True, method=None):
        return request(opener, base, '/api/v1/' + path, payload=payload,
                       headers={'X-Api-Key': api_key} if auth else None, timeout=60, method=method)

    secured = listen('configuration/bootstrap', auth=False)['authenticationRequired']
    if secured and 'listenarr' not in registry:
        raise RuntimeError('Listenarr already requires authentication without a saved account')
    account = registry.get('listenarr') or save_account(registry)
    settings = listen('configuration/settings')
    changed = not secured or settings.get('completedFileAction') != 'hardlink/copy'
    if changed:
        settings['completedFileAction'] = 'hardlink/copy'
        if not secured:
            settings.update(adminUsername=account['username'], adminPassword=account['password'])
        listen('configuration/settings', settings)
    if not secured:
        listen('configuration/startupconfig', {'AuthenticationRequired': 'true'})
    if not listen('configuration/bootstrap', auth=False)['authenticationRequired']:
        raise RuntimeError('Listenarr authentication was not enabled')
    login = listen('account/login', account, auth=False)
    if not login or login.get('authType') != 'session':
        raise RuntimeError('Listenarr rejected the shared admin credentials')

    library = next((item for item in listen('rootfolders') if item['path'] == LIBRARY), None)
    if library is None:
        listen('rootfolders', {'name': 'Audiobookshelf', 'path': LIBRARY, 'isDefault': True})
        changed = True
    elif not library['isDefault']:
        listen(f"rootfolders/{library['id']}", {
            'name': library['name'], 'isDefault': True,
            'caseSensitivityMode': library['caseSensitivityMode'],
        }, method='PATCH')
        changed = True

    qb = registry['qbittorrent']
    changed |= configure_category(host, qb)
    clients = listen('download-clients')
    matches = [client for client in clients if client['type'].lower() == 'qbittorrent']
    if not matches:
        client = {
            'name': 'qBittorrent', 'type': 'qbittorrent', 'host': host, 'port': 8080,
            'username': qb['username'], 'password': qb['password'], 'downloadPath': DOWNLOADS,
            'isEnabled': True, 'removeCompletedDownloads': 'none', 'settings': {'category': 'audiobooks'},
        }
        if not listen('download-clients/test', client)['success']:
            raise RuntimeError('Listenarr could not authenticate to qBittorrent')
        listen('download-clients', client)
        changed = True
    elif len(matches) != 1 or matches[0].get('settings', {}).get('category') != 'audiobooks':
        raise RuntimeError('Existing Listenarr qBittorrent client uses a different category')

    prowlarr = f'http://{host}:9696'
    key = ET.parse(CREDENTIALS.parent / 'config/prowlarr/config.xml').findtext('ApiKey')
    upstream = request(opener, prowlarr, '/api/v1/indexer', headers={'X-Api-Key': key})
    existing = {idx['name'] for idx in listen('indexers')}
    verified = []
    for name in INDEXERS:
        display_name = name + ' (Prowlarr)'
        source = next((idx for idx in upstream if idx['name'] == name and idx['enable']), None)
        if not source:
            continue
        if display_name not in existing:
            indexer = {
                'name': display_name, 'type': 'Torrent', 'implementation': 'Torznab',
                'url': f"{prowlarr}/{source['id']}/api", 'apiKey': key, 'categories': '3030',
            }
            try:
                test = listen('indexers/test', indexer)
            except (OSError, RuntimeError):
                continue
            if not test.get('success'):
                continue
            listen('indexers', indexer)
            changed = True
        verified.append(display_name)
    if not verified:
        raise RuntimeError('No Prowlarr audiobook indexer passed the Listenarr test')
    print(json.dumps({'changed': changed, 'configured_indexers': verified}))


if __name__ == '__main__':
    try:
        lock = os.open(CREDENTIALS.parent / '.listenarr-bootstrap.lock',
                       os.O_CREAT | os.O_NOFOLLOW | os.O_WRONLY, 0o600)
        with os.fdopen(lock, 'w') as file:
            fcntl.flock(file, fcntl.LOCK_EX)
            configure(*sys.argv[1:])
    except (OSError, RuntimeError, ValueError, KeyError) as error:
        sys.exit(str(error))
