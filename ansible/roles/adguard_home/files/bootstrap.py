#!/usr/bin/env python3
"""Provision AdGuard Home without printing authentication material."""
import base64
import json
import os
from pathlib import Path
import secrets
import sys
import tempfile
import urllib.error
import urllib.request

CREDENTIAL_FILE = Path('/opt/media-stack/admin-credentials.json')
UPSTREAMS = ['https://dns.quad9.net/dns-query']
BOOTSTRAP_DNS = ['9.9.9.9', '149.112.112.112']
FILTERS = {
    'HaGeZi Pro': 'https://adguardteam.github.io/HostlistsRegistry/assets/filter_48.txt',
    'HaGeZi Samsung Tracker': 'https://adguardteam.github.io/HostlistsRegistry/assets/filter_61.txt',
    'HaGeZi LG webOS Tracker': 'https://adguardteam.github.io/HostlistsRegistry/assets/filter_72.txt',
}


def save_credentials():
    if CREDENTIAL_FILE.stat().st_mode & 0o077:
        raise RuntimeError('Shared credential file permissions are too broad')
    registry = json.loads(CREDENTIAL_FILE.read_text())
    if 'adguard-home' in registry:
        return registry['adguard-home']
    account = {'username': 'admin', 'password': secrets.token_urlsafe(32) + 'aA7!'}
    registry['adguard-home'] = account
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
    return account


def main(base):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(base + '/', timeout=15) as root:
        first_install = root.geturl().endswith('/install.html')
    account = save_credentials()
    auth = base64.b64encode(f"{account['username']}:{account['password']}".encode()).decode()

    def api(path, body=None, authenticated=True, timeout=25):
        headers = {'Content-Type': 'application/json', 'Origin': base}
        if authenticated:
            headers['Authorization'] = 'Basic ' + auth
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(base + '/control' + path, data=data, headers=headers)
        try:
            with opener.open(req, timeout=timeout) as response:
                if response.headers.get_content_type() != 'application/json':
                    return None
                return json.load(response)
        except urllib.error.HTTPError as error:
            raise RuntimeError(f'{req.get_method()} {path} returned HTTP {error.code}') from None

    if first_install:
        api('/install/configure', {
            **account,
            'web': {'ip': '0.0.0.0', 'port': 3000},
            'dns': {'ip': '0.0.0.0', 'port': 53},
        }, authenticated=False)
    info = api('/dns_info')
    if info is None:
        raise RuntimeError('AdGuard Home did not accept the saved credentials')
    changed = first_install
    desired = {'upstream_dns': UPSTREAMS, 'bootstrap_dns': BOOTSTRAP_DNS}
    if any(info.get(key) != value for key, value in desired.items()):
        api('/dns_config', desired)
        info = api('/dns_info')
        changed = True
    if any(info.get(key) != value for key, value in desired.items()):
        raise RuntimeError('Encrypted upstream settings did not match after update')
    if not api('/status')['protection_enabled'] or not api('/filtering/status')['enabled']:
        raise RuntimeError('AdGuard Home DNS filtering is disabled')
    if api('/dhcp/status')['enabled']:
        raise RuntimeError('AdGuard Home DHCP must be disabled with the ISP router on this LAN')
    existing = {entry['url']: entry for entry in api('/filtering/status')['filters']}
    for name, url in FILTERS.items():
        entry = existing.get(url)
        if entry is None:
            api('/filtering/add_url', {'name': name, 'url': url, 'whitelist': False}, timeout=120)
            changed = True
        elif not entry['enabled']:
            api('/filtering/set_url', {
                'url': url, 'whitelist': False,
                'data': {'name': entry['name'], 'url': url, 'enabled': True},
            }, timeout=120)
            changed = True

    loaded = {entry['url']: entry for entry in api('/filtering/status')['filters']}
    for name, url in FILTERS.items():
        if not loaded[url]['enabled'] or loaded[url]['rules_count'] < 1:
            raise RuntimeError(f'{name} is enabled but has no loaded rules')
        print(f"{name}: {loaded[url]['rules_count']} rules loaded")
    print(f'AdGuard Home authentication and configuration verified. changed={str(changed).lower()}')


if __name__ == '__main__':
    try:
        main(sys.argv[1])
    except (OSError, ValueError, RuntimeError, KeyError) as error:
        sys.exit(str(error))
