#!/usr/bin/env python3
"""Configure a private Hermes gateway without importing or printing credentials."""
import argparse
import json
import os
from pathlib import Path
import secrets
import yaml

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--root', required=True)
args = parser.parse_args()
data = Path(args.root) / 'data'
path = data / '.env'
lines = path.read_text().splitlines() if path.exists() else []
values = {line.split('=', 1)[0]: line.split('=', 1)[1]
          for line in lines if '=' in line and not line.startswith('#')}
key = values.get('API_SERVER_KEY', '').strip('"\'')
desired = {'API_SERVER_ENABLED': 'true', 'API_SERVER_HOST': '127.0.0.1',
           'API_SERVER_PORT': '8642', 'API_SERVER_MODEL_NAME': 'homelab-hermes',
           'API_SERVER_KEY': key if len(key) >= 32 else secrets.token_urlsafe(48),
           'WHATSAPP_ENABLED': 'false'}
changed = any(values.get(k) != v for k, v in desired.items())
if changed:
    retained = [line for line in lines if line.split('=', 1)[0] not in desired]
    retained.extend(k+'='+v for k, v in desired.items())
    path.write_text('\n'.join(retained)+'\n')
config_path = data / 'config.yaml'
config = yaml.safe_load(config_path.read_text()) if config_path.exists() else {}
config = config or {}
for section, settings in {'model': {'provider': 'openai-codex', 'default': 'gpt-6-sol'},
                          'auth': {'adopt_external_logins': False}}.items():
    current = config.setdefault(section, {})
    for k, v in settings.items():
        if current.get(k) != v:
            current[k] = v
            changed = True
if changed or not config_path.exists():
    config_path.write_text(yaml.safe_dump(config, sort_keys=False))
for target in [path, config_path]:
    os.chmod(target, 0o600)
print(json.dumps({'changed': changed, 'api_bind': '127.0.0.1:8642',
                  'provider': 'openai-codex', 'provider_login': 'user_action_required'}))
