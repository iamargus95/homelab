#!/usr/bin/env python3
"""Enable Jellyfin behind an explicitly configured public reverse proxy.
No Cloudflare credentials are used here; DNS/tunnel routing is managed separately.
"""
import argparse
import ipaddress
import json
import os
from pathlib import Path
import urllib.request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--hostname', required=True)
    parser.add_argument('--local-url', default='http://192.168.1.243:8096')
    parser.add_argument('--known-proxies', required=True, help='Comma-separated exact proxy IP addresses')
    parser.add_argument('--root', default='/opt/media-stack')
    args = parser.parse_args()
    proxies = [str(ipaddress.ip_address(p.strip())) for p in args.known_proxies.split(',') if p.strip()]
    if not proxies:
        parser.error('At least one observed proxy address is required')
    root = Path(args.root)
    credentials = json.loads((root/'admin-credentials.json').read_text())['jellyfin']
    auth = urllib.request.Request(args.local_url+'/Users/AuthenticateByName',
        data=json.dumps({'Username': credentials['username'], 'Pw': credentials['password']}).encode(),
        headers={'Content-Type': 'application/json',
                 'Authorization': 'MediaBrowser Client="Homelab", Device="Public config", DeviceId="homelab-public-config", Version="1.0"'})
    with urllib.request.urlopen(auth, timeout=20) as response:
        token = json.load(response)['AccessToken']
    def api(path, body=None):
        request = urllib.request.Request(args.local_url+path,
            data=json.dumps(body).encode() if body is not None else None,
            headers={'Content-Type': 'application/json', 'Authorization': 'MediaBrowser Token="'+token+'"'})
        with urllib.request.urlopen(request, timeout=20) as response:
            data = response.read()
            return json.loads(data) if data else None
    network = api('/System/Configuration/network')
    desired_proxies = list(dict.fromkeys(network.get('KnownProxies', [])+proxies))
    changed = not network.get('EnableRemoteAccess') or desired_proxies != network.get('KnownProxies', [])
    if changed:
        backup = root/'jellyfin-network-before-tunnel.json'
        if not backup.exists():
            fd = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, 'w') as stream:
                json.dump(network, stream, indent=2)
        network.update(EnableRemoteAccess=True, KnownProxies=desired_proxies)
        api('/System/Configuration/network', network)
    actual = api('/System/Configuration/network')
    assert actual['EnableRemoteAccess'] and all(p in actual['KnownProxies'] for p in proxies)
    print(json.dumps({'changed': changed, 'hostname': args.hostname,
                      'remote_access': actual['EnableRemoteAccess'], 'known_proxies': actual['KnownProxies']}))


if __name__ == '__main__':
    main()
