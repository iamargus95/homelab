#!/usr/bin/env python3
"""Initialize local media apps. Run on host as root before LAN publication.
Secrets stay on the server; existing accounts/configuration are preserved.
"""
import json, os, secrets, time, urllib.request, urllib.parse, urllib.error, http.cookiejar
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path('/opt/media-stack')
secret_file = ROOT / 'admin-credentials.json'
if secret_file.exists():
    creds = json.loads(secret_file.read_text())
else:
    creds = {app: {'username': 'admin', 'password': secrets.token_urlsafe(24)} for app in
             ['jellyfin', 'sonarr', 'radarr', 'lidarr', 'prowlarr', 'bazarr', 'qbittorrent', 'sabnzbd']}
    fd = os.open(secret_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as f:
        json.dump(creds, f, indent=2)
    os.chown(secret_file, 1000, 1000)

def api(port, path, body=None, method=None, key=None, form=False, opener=None):
    headers = {"Referer": f"http://127.0.0.1:{port}/", "Origin": f"http://127.0.0.1:{port}"}
    if key:
        headers['X-Api-Key'] = key
    data = None
    if body is not None:
        if form:
            data = urllib.parse.urlencode(body).encode()
            headers['Content-Type'] = 'application/x-www-form-urlencoded'
        else:
            data = json.dumps(body).encode()
            headers['Content-Type'] = 'application/json'
    req = urllib.request.Request(f'http://127.0.0.1:{port}{path}', data=data,
                                 headers=headers, method=method)
    with (opener.open if opener else urllib.request.urlopen)(req, timeout=30) as r:
        data = r.read().decode()
        try:
            return json.loads(data)
        except ValueError:
            return data

def marker(name, action):
    p = ROOT / ('.configured-' + name)
    if not p.exists():
        action()
        p.touch(mode=0o600)
    print(name + ': configured', flush=True)

ports = {'sonarr':8989, 'radarr':7878, 'lidarr':8686, 'prowlarr':9696}
keys = {}
for app, port in ports.items():
    config_path = ROOT / 'config' / app / 'config.xml'
    for attempt in range(60):
        if config_path.exists(): break
        time.sleep(2)
    keys[app] = ET.parse(config_path).getroot().findtext('ApiKey')
    for attempt in range(60):
        try:
            api(port, '/api/v1/system/status' if app == 'prowlarr' else '/api/v3/system/status' if app != 'lidarr' else '/api/v1/system/status', key=keys[app])
            break
        except Exception:
            time.sleep(2)
    else:
        raise RuntimeError(app + ' did not become ready')

# Download client login and paths. Initial password is read internally from logs.
def qbit():
    import subprocess, re
    log = subprocess.check_output(['docker','compose','-f',str(ROOT/'compose.yml'),'logs','--no-color','qbittorrent'], text=True)
    matches = re.findall(r'temporary password is provided for this session: (\S+)', log)
    jar = http.cookiejar.CookieJar()
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    for password in [creds['qbittorrent']['password']] + matches[::-1]:
        try:
            if api(8080, '/api/v2/auth/login', {'username':'admin','password':password}, form=True, opener=op) != 'Fails.':
                break
        except urllib.error.HTTPError:
            continue
    else:
        raise RuntimeError('qBittorrent authentication failed')
    prefs = {'web_ui_username':'admin', 'web_ui_password':creds['qbittorrent']['password'],
             'save_path':'/data/downloads/torrents', 'temp_path_enabled':True,
             'temp_path':'/data/downloads/torrents/incomplete', 'upnp':False,
             'dont_count_slow_torrents':True,
             'bypass_local_auth':False, 'bypass_auth_subnet_whitelist_enabled':False,
             'web_ui_csrf_protection_enabled':True}
    api(8080, '/api/v2/app/setPreferences', {'json':json.dumps(prefs)}, form=True, opener=op)
    existing = api(8080, '/api/v2/torrents/categories', opener=op)
    for category in ['movies','tv','music']:
        if category not in existing:
            api(8080, '/api/v2/torrents/createCategory', {'category':category,'savePath':'/data/downloads/torrents/'+category}, form=True, opener=op)
marker('qbittorrent', qbit)

for app,port in ports.items():
    prefix='/api/v1' if app in ['prowlarr','lidarr'] else '/api/v3'
    def call(path, body=None, method=None):
        return api(port,prefix+path,body,method,keys[app])
    def configure():
        if app != 'prowlarr':
            category={'sonarr':'tv','radarr':'movies','lidarr':'music'}[app]
            if app != 'lidarr':
                folder='/data/library/'+category
                if not any(x['path']==folder for x in call('/rootfolder')):
                    call('/rootfolder',{'path':folder})
            if not any(x['name']=='qBittorrent' for x in call('/downloadclient')):
                schema=next(x for x in call('/downloadclient/schema') if x['implementation']=='QBittorrent')
                schema.update(name='qBittorrent',enable=True,priority=1)
                vals={'host':'qbittorrent','port':8080,'username':'admin','password':creds['qbittorrent']['password'],
                      'movieCategory':category,'tvCategory':category,'musicCategory':category,'useSsl':False}
                for field in schema['fields']:
                    if field['name'] in vals: field['value']=vals[field['name']]
                call('/downloadclient',schema)
            mm=call('/config/mediamanagement')
            mm['copyUsingHardlinks']=True
            call('/config/mediamanagement',mm,'PUT')
        host=call('/config/host')
        host.update(authenticationMethod='forms',authenticationRequired='enabled',
                    username='admin',password=creds[app]['password'],passwordConfirmation=creds[app]['password'])
        call('/config/host',host,'PUT')
    marker(app,configure)

# Prowlarr distributes future user-selected indexers to each library manager.
def prowlarr_apps():
    existing=api(9696,'/api/v1/applications',key=keys['prowlarr'])
    schemas=api(9696,'/api/v1/applications/schema',key=keys['prowlarr'])
    for app in ['sonarr','radarr','lidarr']:
        if any(x['name'].lower()==app for x in existing): continue
        model=next(x for x in schemas if x['implementation'].lower()==app)
        model.update(name=app.title(),syncLevel='fullSync')
        vals={'prowlarrUrl':'http://prowlarr:9696','baseUrl':f'http://{app}:{ports[app]}','apiKey':keys[app]}
        for field in model['fields']:
            if field['name'] in vals: field['value']=vals[field['name']]
        api(9696,'/api/v1/applications',model,key=keys['prowlarr'])
marker('prowlarr-applications',prowlarr_apps)

# Jellyfin's supported first-run API, followed by authenticated library creation.
def jellyfin():
    info=api(8096,'/System/Info/Public')
    if not info.get('StartupWizardCompleted'):
        api(8096,'/Startup/Configuration',{'UICulture':'en-US','MetadataCountryCode':'IN','PreferredMetadataLanguage':'en'})
        api(8096,'/Startup/FirstUser')
        api(8096,'/Startup/User',{'Name':'admin','Password':creds['jellyfin']['password']})
        api(8096,'/Startup/RemoteAccess',{'EnableRemoteAccess':False,'EnableAutomaticPortMapping':False})
        api(8096,'/Startup/Complete',{},'POST')
    req=urllib.request.Request('http://127.0.0.1:8096/Users/AuthenticateByName',
        data=json.dumps({'Username':'admin','Pw':creds['jellyfin']['password']}).encode(),
        headers={'Content-Type':'application/json','Authorization':'MediaBrowser Client="Homelab", Device="Server", DeviceId="homelab", Version="1.0"'})
    with urllib.request.urlopen(req) as r: token=json.load(r)['AccessToken']
    for name,kind,folder in [('Movies','movies','movies'),('TV Shows','tvshows','tv'),('Music','music','music')]:
        query=urllib.parse.urlencode({'name':name,'collectionType':kind,'refreshLibrary':'false'})
        req=urllib.request.Request('http://127.0.0.1:8096/Library/VirtualFolders?'+query,
            data=json.dumps({'LibraryOptions':{'PathInfos':[{'Path':'/media/'+folder}],'EnableRealtimeMonitor':True}}).encode(),
            headers={'Content-Type':'application/json','Authorization':'MediaBrowser Token="'+token+'"'},method='POST')
        urllib.request.urlopen(req).close()
    refresh = urllib.request.Request('http://127.0.0.1:8096/Library/Refresh', data=b'',
        headers={'Authorization':'MediaBrowser Token="'+token+'"'}, method='POST')
    urllib.request.urlopen(refresh).close()
marker('jellyfin',jellyfin)

# Stop these two apps while writing their first-run configuration.
def extras():
    import subprocess, hashlib, yaml
    from configobj import ConfigObj
    compose=['docker','compose','-f',str(ROOT/'compose.yml')]
    subprocess.run(compose+['stop','bazarr','sabnzbd'],check=True,stdout=subprocess.DEVNULL)
    try:
        path=ROOT/'config/bazarr/config/config.yaml'
        cfg=yaml.safe_load(path.read_text())
        cfg.setdefault('auth',{}).update(type='form',username='admin',password=hashlib.md5(creds['bazarr']['password'].encode()).hexdigest())
        cfg.setdefault('general',{}).update(use_sonarr=True,use_radarr=True)
        for app in ['sonarr','radarr']:
            cfg.setdefault(app,{}).update(ip=app,port=ports[app],apikey=keys[app],ssl=False)
        path.write_text(yaml.safe_dump(cfg,sort_keys=False))
        os.chown(path,1000,1000)
        path=ROOT/'config/sabnzbd/sabnzbd.ini'
        cfg=ConfigObj(str(path))
        cfg['misc'].update({'username':'admin','password':creds['sabnzbd']['password'],
                           'download_dir':'/data/downloads/usenet/incomplete',
                           'complete_dir':'/data/downloads/usenet/complete',
                           'host_whitelist':['sabnzbd','alienware','192.168.1.243']})
        cfg.write()
        os.chown(path,1000,1000)
    finally:
        subprocess.run(compose+['start','bazarr','sabnzbd'],check=True,stdout=subprocess.DEVNULL)
marker('extras',extras)

def lidarr_root():
    base='/api/v1'
    if not api(8686,base+'/rootfolder',key=keys['lidarr']):
        profiles=api(8686,base+'/qualityprofile',key=keys['lidarr'])
        metadata=api(8686,base+'/metadataprofile',key=keys['lidarr'])
        api(8686,base+'/rootfolder',{'name':'Music','path':'/data/library/music',
            'defaultQualityProfileId':profiles[0]['id'],'defaultMetadataProfileId':metadata[0]['id'],
            'defaultMonitorOption':'all','defaultNewItemMonitorOption':'all'},key=keys['lidarr'])
marker('lidarr-root',lidarr_root)

def jf_authenticated():
    req=urllib.request.Request('http://127.0.0.1:8096/Users/AuthenticateByName',
        data=json.dumps({'Username':'admin','Pw':creds['jellyfin']['password']}).encode(),
        headers={'Content-Type':'application/json','Authorization':'MediaBrowser Client="Homelab", Device="Server", DeviceId="homelab", Version="1.0"'})
    with urllib.request.urlopen(req) as r: token=json.load(r)['AccessToken']
    def call(path,body=None,method=None):
        req=urllib.request.Request('http://127.0.0.1:8096'+path,
            data=json.dumps(body).encode() if body is not None else None,
            headers={'Content-Type':'application/json','Authorization':'MediaBrowser Token="'+token+'"'},method=method)
        with urllib.request.urlopen(req) as r:
            data=r.read()
            return json.loads(data) if data else None
    return call

def hardware():
    import subprocess
    subprocess.run(['docker','compose','-f',str(ROOT/'compose.yml'),'exec','-T','jellyfin',
        '/usr/lib/jellyfin-ffmpeg/ffmpeg','-hide_banner','-loglevel','error',
        '-init_hw_device','vaapi=va:/dev/dri/renderD128','-filter_hw_device','va',
        '-f','lavfi','-i','testsrc2=size=1280x720:rate=30','-vf','format=nv12,hwupload',
        '-c:v','h264_vaapi','-t','2','-f','null','-'],check=True)
    call=jf_authenticated()
    cfg=call('/System/Configuration/encoding')
    cfg.update(HardwareAccelerationType='vaapi',VaapiDevice='/dev/dri/renderD128',
               EnableHardwareEncoding=True,HardwareDecodingCodecs=['h264','hevc','mpeg2video','vc1','vp8','vp9'])
    call('/System/Configuration/encoding',cfg,'POST')
marker('hardware',hardware)

# Notify Jellyfin directly after imports, with container path translation.
def jellyfin_import_notification():
    call = jf_authenticated()
    tokens = call('/Auth/Keys')['Items']
    if not any(x.get('AppName') == 'Sonarr' for x in tokens):
        call('/Auth/Keys?app=Sonarr', {}, 'POST')
        tokens = call('/Auth/Keys')['Items']
    token = next(x['AccessToken'] for x in tokens if x.get('AppName') == 'Sonarr')
    def sonarr(path, body=None):
        return api(8989, '/api/v3/' + path, body, key=keys['sonarr'])
    if any(x.get('name') == 'Jellyfin library update' for x in sonarr('notification')):
        return
    model = next(x for x in sonarr('notification/schema') if x['implementation'] == 'MediaBrowser')
    model.update(name='Jellyfin library update', onDownload=True, onUpgrade=True, onRename=True, tags=[])
    values = {'host': 'jellyfin', 'port': 8096, 'useSsl': False, 'urlBase': '',
              'apiKey': token, 'notify': False, 'updateLibrary': True,
              'mapFrom': '/data/library/tv', 'mapTo': '/media/tv'}
    for field in model['fields']:
        if field['name'] in values:
            field['value'] = values[field['name']]
    sonarr('notification/test', model)
    sonarr('notification', model)
marker('jellyfin-notification', jellyfin_import_notification)


def seerr():
    jar=http.cookiejar.CookieJar()
    op=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    settings=json.loads((ROOT/'config/seerr/settings.json').read_text())
    body={'username':'admin','password':creds['jellyfin']['password']}
    if not settings.get('jellyfin',{}).get('ip'):
        body.update(hostname='jellyfin',port=8096,useSsl=False,urlBase='',serverType=2)
    api(5055,'/api/v1/auth/jellyfin',body,opener=op)
    for app,folder in [('radarr','movies'),('sonarr','tv')]:
        path='/api/v1/settings/'+app
        if api(5055,path,opener=op): continue
        profile=api(ports[app],'/api/v3/qualityprofile',key=keys[app])[0]
        body={'name':app.title(),'hostname':app,'port':ports[app],'apiKey':keys[app],
              'useSsl':False,'baseUrl':'','activeProfileId':profile['id'],
              'activeProfileName':profile['name'],'activeDirectory':'/data/library/'+folder,
              'is4k':False,'isDefault':True,'syncEnabled':True,'preventSearch':False,
              'minimumAvailability':'released','enableSeasonFolders':True,'seriesType':'standard'}
        api(5055,path,body,opener=op)
    libraries=api(5055,'/api/v1/settings/jellyfin/library/sync',{},opener=op)
    for library in libraries:
        api(5055,'/api/v1/settings/jellyfin/library/'+library['id'],{'enabled':True},'PUT',opener=op)
    api(5055,'/api/v1/settings/initialize',{},opener=op)
marker('seerr',seerr)
(ROOT/'.configured-secure').touch(mode=0o600)
