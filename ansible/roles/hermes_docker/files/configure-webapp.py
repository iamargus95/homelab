#!/usr/bin/env python3
"""Prepare a password-protected Hermes Webapp; never print credentials."""
import argparse
import json
import os
from pathlib import Path
import secrets
import tempfile
import urllib.parse
import yaml


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', default='/opt/hermes')
    parser.add_argument('--public-url', required=True)
    parser.add_argument('--port', type=int, default=9120)
    args = parser.parse_args()
    url = urllib.parse.urlsplit(args.public_url)
    if url.scheme not in ['http', 'https'] or not url.hostname or url.username or url.password:
        raise RuntimeError('Expected a service URL without embedded credentials')
    data = Path(args.root) / 'data'
    owner = data.stat()
    changed = False

    def write_private(path, content):
        nonlocal changed
        if path.exists() and path.read_text() == content:
            return
        info = path.stat() if path.exists() else owner
        fd, temporary = tempfile.mkstemp(prefix='.hermes-config-', dir=path.parent)
        try:
            with os.fdopen(fd, 'w') as f:
                os.fchmod(f.fileno(), 0o600)
                if os.geteuid() == 0:
                    os.fchown(f.fileno(), info.st_uid, info.st_gid)
                f.write(content)
            os.replace(temporary, path)
        finally:
            Path(temporary).unlink(missing_ok=True)
        changed = True

    env_path = data / '.env'
    lines = env_path.read_text().splitlines()
    values = {line.split('=', 1)[0]: line.split('=', 1)[1]
              for line in lines if '=' in line and not line.startswith('#')}
    if values.get('HERMES_DASHBOARD_BASIC_AUTH_PASSWORD_HASH', '').strip('"\''):
        raise RuntimeError('Preserving existing password-hash authentication; configure its credentials explicitly')
    credential_path = data / 'admin-credentials.json'
    master_path = Path('/opt/media-stack/admin-credentials.json')
    master = json.loads(master_path.read_text()) if master_path.exists() else {}
    if credential_path.exists():
        credential = json.loads(credential_path.read_text())
    elif 'hermes' in master:
        credential = master['hermes']
    else:
        credential = {'username': 'admin', 'password': secrets.token_urlsafe(36)}
    if not credential.get('username') or not credential.get('password'):
        raise RuntimeError('Webapp credentials are incomplete')
    write_private(credential_path, json.dumps(credential, indent=2)+'\n')
    if master_path.exists() and 'hermes' not in master:
        master['hermes'] = credential
        write_private(master_path, json.dumps(master, indent=2)+'\n')
    settings = {
        'HERMES_DASHBOARD_BASIC_AUTH_USERNAME': credential['username'],
        'HERMES_DASHBOARD_BASIC_AUTH_PASSWORD': credential['password'],
        'HERMES_DASHBOARD_BASIC_AUTH_SECRET': values.get('HERMES_DASHBOARD_BASIC_AUTH_SECRET') or secrets.token_urlsafe(48),
    }
    if any(values.get(k) != v for k, v in settings.items()):
        retained = [line for line in lines if line.split('=', 1)[0] not in settings]
        retained.extend(k+'='+v for k, v in settings.items())
        write_private(env_path, '\n'.join(retained)+'\n')
    config_path = data / 'config.yaml'
    config = yaml.safe_load(config_path.read_text()) or {}
    webapp = {'enabled': True, 'host': '0.0.0.0', 'port': args.port,
              'public_url': args.public_url.rstrip('/')}
    current_webapp = config.setdefault('webapp', {})
    if any(current_webapp.get(k) != v for k, v in webapp.items()):
        current_webapp.update(webapp)
        write_private(config_path, yaml.safe_dump(config, sort_keys=False))
    print(json.dumps({'changed': changed, 'webapp_url': args.public_url,
                      'authentication': 'username_password', 'credential_entry': 'hermes',
                      'gateway_recreation_required': changed}))


if __name__ == '__main__':
    main()
