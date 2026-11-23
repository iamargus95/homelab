#!/usr/bin/env python3
"""Add service shortcuts to the existing private Homarr board; preserve its layout."""
import argparse
import http.cookiejar
import json
from pathlib import Path
import urllib.error
import urllib.parse
import urllib.request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--hermes-url', default='http://192.168.1.243:9120')
    parser.add_argument('--kuma-url', default='http://192.168.1.243:3001')
    parser.add_argument('--board', default='homelab')
    parser.add_argument('--kuma-only', action='store_true')
    args = parser.parse_args()
    base = 'http://192.168.1.243:7575'
    credentials = json.loads(Path('/opt/media-stack/admin-credentials.json').read_text())['homarr']
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def request(path, body=None, form=False):
        headers = {'Origin': base, 'Referer': base+'/auth/login', 'Accept': 'application/json'}
        data = None
        if body is not None:
            data = (urllib.parse.urlencode(body) if form else json.dumps(body)).encode()
            headers['Content-Type'] = 'application/x-www-form-urlencoded' if form else 'application/json'
        try:
            with opener.open(urllib.request.Request(base+path, data=data, headers=headers), timeout=30) as response:
                raw = response.read()
                try:
                    return json.loads(raw)
                except ValueError:
                    return None
        except urllib.error.HTTPError as error:
            raise RuntimeError('Homarr '+path.split('?')[0]+' returned HTTP '+str(error.code)) from None

    def trpc(name, body=None, mutation=False):
        payload = {'json': body}
        if body is None:
            payload['meta'] = {'values': ['undefined']}
        result = request('/api/trpc/'+name, payload) if mutation else request(
            '/api/trpc/'+name+'?input='+urllib.parse.quote(json.dumps(payload)))
        return result['result']['data']['json']

    csrf = request('/api/auth/csrf')['csrfToken']
    request('/api/auth/callback/credentials', {
        'csrfToken': csrf, 'name': credentials['username'], 'password': credentials['password'],
        'callbackUrl': base, 'json': 'true'}, form=True)
    if not request('/api/auth/session').get('user'):
        raise RuntimeError('Homarr login failed')
    board = trpc('board.getBoardByName', {'name': args.board})
    if board['isPublic']:
        raise RuntimeError('Expected the private Homarr board')
    original_items = {item['id']: item for item in board['items']}
    apps = trpc('app.all')
    services = [
        ('Uptime Kuma', args.kuma_url, 'Availability monitoring for the media services and SSH',
         'https://cdn.jsdelivr.net/gh/homarr-labs/dashboard-icons@master/svg/uptime-kuma.svg'),
    ]
    if not args.kuma_only:
        services.append(('Hermes Agent', args.hermes_url,
                         'Password-protected Hermes workspace; ChatGPT/Codex provider',
                         'https://raw.githubusercontent.com/NousResearch/hermes-agent/v0.23.3/apps/desktop/assets/appx/Square150x150Logo.png'))
    added = []
    for name, href, description, icon in services:
        existing = [app for app in apps if app['name'].casefold() == name.casefold()]
        if len(existing) > 1:
            raise RuntimeError('Multiple existing apps named '+name)
        if existing:
            app = existing[0]
            if app['href'] != href:
                raise RuntimeError('Preserving a different existing URL for '+name)
        else:
            app = trpc('app.create', {'name': name, 'href': href, 'description': description,
                                    'iconUrl': icon, 'pingUrl': None}, True)
            apps.append(app)
        app_id = app['id']
        if not any(item['kind'] == 'app' and item['options'].get('appId') == app_id
                   for item in board['items']):
            tile = trpc('board.addItem', {'boardId': board['id'], 'kind': 'app',
                        'options': {'appId': app_id, 'openIn': 'newTab', 'showTitle': True},
                        'size': {'width': 1, 'height': 1}, 'integrationIds': []}, True)
            added.append({'name': name, 'item_id': tile['itemId']})
    saved = trpc('board.getBoardByName', {'name': args.board})
    saved_items = {item['id']: item for item in saved['items']}
    if saved['isPublic'] or any(saved_items.get(key) != item for key, item in original_items.items()):
        raise RuntimeError('Existing board items or privacy changed unexpectedly')
    for name, href, *_ in services:
        app = next(app for app in apps if app['name'] == name)
        tiles = [item for item in saved['items']
                 if item['kind'] == 'app' and item['options'].get('appId') == app['id']]
        if len(tiles) != 1 or len(tiles[0]['layouts']) != len(saved['layouts']):
            raise RuntimeError('Could not verify all layout placements for '+name)
    print(json.dumps({'board': args.board, 'is_public': saved['isPublic'],
                      'added_tiles': added, 'services': [name for name, *_ in services],
                      'existing_items_preserved': True}))


if __name__ == '__main__':
    main()
