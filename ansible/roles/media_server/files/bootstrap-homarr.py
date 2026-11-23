#!/usr/bin/env python3
"""First-run Homarr v2 setup through its onboarding/session APIs.
Run on the Alienware host. Credentials never leave the server.
"""
import http.cookiejar, json, os, secrets, time, urllib.error, urllib.parse, urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
import yaml
from configobj import ConfigObj

root=Path('/opt/media-stack')
base='http://192.168.1.243:7575'
marker=root/'.configured-homarr'
starter_marker=root/'.homarr-starter-cleaned'
if marker.exists() and starter_marker.exists():
    print('Homarr already configured; preserving dashboard.')
    raise SystemExit(0)
credentials_path=root/'admin-credentials.json'
credentials=json.loads(credentials_path.read_text())
if 'homarr' not in credentials:
    credentials['homarr']={'username':'admin','password':secrets.token_urlsafe(24)}
    credentials_path.write_text(json.dumps(credentials,indent=2)+'\n')
    os.chmod(credentials_path,0o600)
admin=credentials['homarr']
jar=http.cookiejar.CookieJar()
opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

def request(path,body=None,form=False,method=None):
    headers={'Origin':base,'Referer':base+'/init','Accept':'application/json'}
    data=None
    if body is not None:
        data=(urllib.parse.urlencode(body) if form else json.dumps(body)).encode()
        headers['Content-Type']='application/x-www-form-urlencoded' if form else 'application/json'
    req=urllib.request.Request(base+path,data=data,headers=headers,method=method)
    try:
        with opener.open(req,timeout=90) as response:
            raw=response.read()
            try:return json.loads(raw)
            except ValueError:return raw.decode()
    except urllib.error.HTTPError as e:
        # Do not log request bodies: they contain service credentials.
        raise RuntimeError(f'Homarr {path.split("?")[0]} returned HTTP {e.code}') from None

def trpc(name,body=None,mutation=False):
    data={'json':body}
    if body is None:data['meta']={'values':['undefined']}
    if mutation:
        result=request('/api/trpc/'+name,data)
    else:
        result=request('/api/trpc/'+name+'?input='+urllib.parse.quote(json.dumps(data)))
    return result.get('result',{}).get('data',{}).get('json')

for attempt in range(90):
    try:
        step=trpc('onboard.currentStep')['current']
        break
    except Exception:
        time.sleep(2)
else:raise RuntimeError('Homarr did not become ready')

if step!='finish':
    request('/api/onboarding/claim',{})
if step=='start':
    trpc('onboard.nextStep',mutation=True)
    step=trpc('onboard.currentStep')['current']
if step=='user':
    trpc('user.initUser',{'username':'admin','password':admin['password'],
                         'confirmPassword':admin['password'],'email':''},True)

csrf=request('/api/auth/csrf')['csrfToken']
request('/api/auth/callback/credentials',{'csrfToken':csrf,'name':'admin',
       'password':admin['password'],'callbackUrl':base,'json':'true'},form=True)
session=request('/api/auth/session')
if not session.get('user'):raise RuntimeError('Homarr administrator login failed')
print('Homarr administrator login verified',flush=True)
step=trpc('onboard.currentStep')['current']
if step=='setup':
    services=[('jellyfin','Jellyfin',8096,'jellyfin','Watch movies, TV and music'),
              ('seerr','Seerr',5055,'seerr','Request movies and TV shows'),
              ('sonarr','Sonarr',8989,'sonarr','TV library'),
              ('radarr','Radarr',7878,'radarr','Movie library'),
              ('lidarr','Lidarr',8686,'lidarr','Music library'),
              ('prowlarr','Prowlarr',9696,'prowlarr','Indexer management'),
              ('bazarr','Bazarr',6767,'bazarr','Subtitles'),
              ('qbittorrent','qBittorrent',8080,'qBittorrent','Torrent downloads'),
              ('sabnzbd','SABnzbd',8081,'sabNzbd','Usenet downloads')]
    integrations=[]
    for app,name,port,kind,description in services:
        if app in ['sonarr','radarr','lidarr','prowlarr']:
            key=ET.parse(root/'config'/app/'config.xml').getroot().findtext('ApiKey')
        elif app=='bazarr':
            key=yaml.safe_load((root/'config/bazarr/config/config.yaml').read_text())['auth']['apikey']
        elif app=='sabnzbd':
            key=ConfigObj(str(root/'config/sabnzbd/sabnzbd.ini'))['misc']['api_key']
        elif app=='seerr':
            key=json.loads((root/'config/seerr/settings.json').read_text())['main']['apiKey']
        if app in ['jellyfin','qbittorrent']:
            secret_values=[{'kind':k,'value':v} for k,v in credentials[app].items()]
        else:secret_values=[{'kind':'apiKey','value':key}]
        icon=app
        entry={'sourceId':'alienware-'+app,'name':name,'url':f'http://192.168.1.243:{port}',
               'kind':kind,'secrets':secret_values,'description':description,
               'iconUrl':f'https://cdn.jsdelivr.net/gh/homarr-labs/dashboard-icons@master/svg/{icon}.svg'}
        test=trpc('onboard.testIntegration',entry,True)
        print(name+': integration '+('OK' if test.get('success') else 'needs attention'),flush=True)
        integrations.append(entry)
    payload={'server':{'defaultLocale':'en','defaultColorScheme':'dark','themeId':'default','analyticsEnabled':False},
             'board':{'name':'homelab','layoutPreset':'balanced','columnCount':10,'leftSidebar':False,'rightSidebar':False},
             'integrations':integrations,'apps':[],'selectedIntegrationIds':[], 'selectedAppIds':[],
             'selectedDockerSourceIds':[],'selectedWidgetKinds':['clock']}
    trpc('onboard.completeSetup',payload,True)
if trpc('onboard.currentStep')['current']!='finish':raise RuntimeError('Homarr onboarding did not finish')
# Remove only Homarr's starter placeholders from this new board.
if not starter_marker.exists():
    board=trpc('board.getBoardByName',{'name':'homelab'})
    apps=trpc('app.all')
    starter_ids={app['id'] for app in apps if app['name'] in
                 ['Help Translate','Homarr Docs','Homarr GitHub','Support Homarr']}
    for item in board['items']:
        options=item.get('options') or {}
        if isinstance(options,str):
            options=json.loads(options).get('json',{})
        remove=(item['kind']=='app' and options.get('appId') in starter_ids)
        remove=remove or (item['kind']=='weather' and not options.get('location'))
        remove=remove or (item['kind']=='bookmarks' and options.get('title')=='Useful Links')
        remove=remove or (item['kind']=='stats' and not options)
        if remove:trpc('board.deleteItem',{'boardId':board['id'],'itemId':item['id']},True)
    starter_marker.touch(mode=0o600)
marker.touch(mode=0o600)
print('Homarr homelab board configured with all nine media services',flush=True)
