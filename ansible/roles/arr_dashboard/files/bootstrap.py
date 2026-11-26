#!/usr/bin/env python3
"""Provision Arr Dashboard without printing or transferring service credentials."""
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

MEDIA_ROOT = Path('/opt/media-stack')
CREDENTIAL_FILE = MEDIA_ROOT / 'admin-credentials.json'
ARR_PORTS = {'Sonarr': 8989, 'Radarr': 7878, 'Lidarr': 8686, 'Prowlarr': 9696}
CLEANUP = {
    'enabled': True,
    'dryRunMode': False,
    'failedEnabled': True,
    'removeFromClient': True,
    'stalledEnabled': False,
    'slowEnabled': False,
    'importPendingEnabled': False,
    'seedingTimeoutEnabled': False,
}
OPENER = urllib.request.build_opener(
    urllib.request.ProxyHandler({}),
    urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()),
)


def request(base, path, body=None, method=None, headers=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        base + path,
        data=data,
        headers={'Origin': base, 'Referer': base + '/',
                 'Content-Type': 'application/json', **(headers or {})},
        method=method,
    )
    try:
        with OPENER.open(req, timeout=40) as response:
            raw = response.read()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as error:
        raise RuntimeError(f'{req.get_method()} {base}{path} returned HTTP {error.code}') from None


def read_credentials(path):
    if path.stat().st_mode & 0o077:
        raise RuntimeError(f'Credential file permissions are too broad: {path}')
    return json.loads(path.read_text())


def credentials(previous_file, setup_required):
    registry = read_credentials(CREDENTIAL_FILE)
    previous = read_credentials(previous_file) if previous_file.exists() else None
    saved = registry.get('arr-dashboard')
    if saved is not None:
        if previous is not None and previous != saved:
            raise RuntimeError('The saved Arr Dashboard credential entries differ')
        return saved
    if previous is None and not setup_required:
        raise RuntimeError('Arr Dashboard is already configured and its saved login is missing')
    account = previous or {'username': 'admin', 'password': secrets.token_urlsafe(32) + 'aA7!'}
    registry['arr-dashboard'] = account
    fd, name = tempfile.mkstemp(prefix='.admin-credentials-', dir=CREDENTIAL_FILE.parent)
    try:
        with os.fdopen(fd, 'w') as file:
            json.dump(registry, file, indent=2)
            file.write('\n')
            file.flush()
            os.fsync(file.fileno())
        os.replace(name, CREDENTIAL_FILE)
    finally:
        Path(name).unlink(missing_ok=True)
    return read_credentials(CREDENTIAL_FILE)['arr-dashboard']


def jellyfin_key(base):
    account = read_credentials(CREDENTIAL_FILE)['jellyfin']
    client = ('MediaBrowser Client="Homelab", Device="Server", '
              'DeviceId="homelab-arr-dashboard", Version="1.0"')
    auth = request(base, '/Users/AuthenticateByName',
                   {'Username': account['username'], 'Pw': account['password']},
                   headers={'Authorization': client})
    headers = {'Authorization': f"{client}, Token=\"{auth['AccessToken']}\""}
    try:
        def keys():
            return [item for item in request(base, '/Auth/Keys', headers=headers)['Items']
                    if item['AppName'] == 'Arr Dashboard']

        found = keys()
        if not found:
            query = urllib.parse.urlencode({'app': 'Arr Dashboard'})
            request(base, '/Auth/Keys?' + query, {}, headers=headers)
            found = keys()
        if len(found) != 1:
            raise RuntimeError('Expected one dedicated Jellyfin key for Arr Dashboard')
        return found[0]['AccessToken']
    finally:
        request(base, '/Sessions/Logout', {}, headers=headers)


def main():
    root, address, base = sys.argv[1:]
    root = Path(root)
    previous_file = root / 'admin-credentials.json'
    setup = request(base, '/auth/setup-required')['required']
    had_saved_account = 'arr-dashboard' in read_credentials(CREDENTIAL_FILE)
    account = credentials(previous_file, setup)
    request(base, '/auth/register' if setup else '/auth/login', account)
    migrated = previous_file.exists()
    previous_file.unlink(missing_ok=True)
    changed = setup or migrated or not had_saved_account
    current = request(base, '/api/services')['services']

    for label, port in {**ARR_PORTS, 'Jellyfin': 8096, 'Seerr': 5055}.items():
        service = label.lower()
        service_url = f'http://{address}:{port}'
        matches = [item for item in current
                   if item['service'].lower() == service and item['baseUrl'] == service_url]
        if len(matches) > 1:
            raise RuntimeError(f'Multiple {label} integrations match {service_url}')
        if not matches:
            if label == 'Jellyfin':
                key = jellyfin_key(service_url)
            elif label == 'Seerr':
                key = json.loads((MEDIA_ROOT / 'config/seerr/settings.json').read_text())['main']['apiKey']
            else:
                key = ET.parse(MEDIA_ROOT / 'config' / service / 'config.xml').findtext('ApiKey')
            request(base, '/api/services',
                    {'label': label, 'baseUrl': service_url, 'service': service, 'apiKey': key})
            changed = True
            matches = [item for item in request(base, '/api/services')['services']
                       if item['service'].lower() == service and item['baseUrl'] == service_url]
        instance, = matches
        if not instance['enabled']:
            raise RuntimeError(f'{label} integration is disabled')
        if not request(base, f"/api/services/{instance['id']}/test", {})['success']:
            raise RuntimeError(f'{label} integration failed its connection test')
        print(f'{label} connection verified', flush=True)

        if label not in ('Sonarr', 'Radarr', 'Lidarr'):
            continue
        configs_path = '/api/queue-cleaner/configs'
        instance_id = instance['id']
        config = next((item for item in request(base, configs_path)['configs']
                       if item and item['instanceId'] == instance_id), None)
        if config is None:
            config = request(base, configs_path, {'instanceId': instance_id})
        if any(config.get(key) != value for key, value in CLEANUP.items()):
            config = request(base, f'{configs_path}/{instance_id}', CLEANUP, 'PATCH')
            changed = True
        if any(config.get(key) != value for key, value in CLEANUP.items()):
            raise RuntimeError(f'{label} cleanup settings did not match after update')
        print(f'{label} automated queue cleanup verified', flush=True)

    (root / '.configured').touch(mode=0o600)
    print(f'changed={str(changed).lower()}')


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, OSError, ValueError, KeyError) as error:
        sys.exit(f'Arr Dashboard setup failed: {error}')
