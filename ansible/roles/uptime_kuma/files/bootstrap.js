// Uses the socket.io-client dependency bundled in Kuma's image.
const fs = require('fs');
const http = require('node:http');
const https = require('node:https');
const { Resolver } = require('node:dns/promises');
const { io } = require('socket.io-client');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const socket = io(input.kumaUrl || 'http://127.0.0.1:3001', { transports: ['websocket'], reconnection: false });
let monitors = {};
socket.on('monitorList', value => { monitors = value; });
const rpc = (event, ...args) => new Promise((resolve, reject) => {
    socket.timeout(15000).emit(event, ...args, (error, result) => {
        if (error) return reject(new Error('Timeout on ' + event));
        if (result && result.ok === false) return reject(new Error(event + ': ' + result.msg));
        resolve(result);
    });
});
const timeout = setTimeout(() => { console.error('Monitoring setup timed out'); process.exit(1); }, 150000);
(async () => {
    await new Promise((resolve, reject) => {
        // The transport can connect before Kuma finishes registering its handlers.
        socket.once('loginRequired', resolve);
        socket.once('connect_error', () => reject(new Error('Could not connect to Kuma')));
    });
    if (!input.monitor && await rpc('needSetup')) await rpc('setup', input.username, input.password);
    const login = await rpc('login', { username: input.username, password: input.password, token: '' });
    if (!login?.ok) throw new Error('Kuma administrator login did not complete');
    await rpc('getMonitorList');
    const httpMonitor = {
        type: 'http', method: 'GET', interval: 60, retryInterval: 20, maxretries: 2,
        timeout: 15, resendInterval: 0, accepted_statuscodes: ['200-299'],
        ignoreTls: false, upsideDown: false, maxredirects: 5,
        notificationIDList: {}, conditions: [], active: true,
    };
    if (input.monitor) {
        const { name, type = 'http', url, headers = {}, hostname, resolver, expectedStatus } = input.monitor;
        let target;
        if (type === 'dns') {
            const dns = new Resolver({ timeout: 5000, tries: 2 });
            dns.setServers([resolver]);
            const answers = await dns.resolve4(hostname);
            if (!answers.some(address => address !== '0.0.0.0')) {
                throw new Error(name + ' did not resolve ' + hostname);
            }
            target = { type, hostname, port: 53, dns_resolve_server: resolver, dns_resolve_type: 'A' };
        } else if (type === 'http') {
            const endpoint = new URL(url);
            const transport = endpoint.protocol === 'https:' ? https : http;
            const status = await new Promise((resolve, reject) => {
                const request = transport.get(endpoint, { headers, signal: AbortSignal.timeout(10000) }, response => {
                    response.resume();
                    resolve(response.statusCode);
                });
                request.on('error', reject);
            });
            if (status !== (expectedStatus ?? 200)) {
                throw new Error('Could not reach ' + name + ' from Kuma: HTTP ' + status);
            }
            target = { type, url, headers: JSON.stringify(headers) };
            if (expectedStatus !== undefined) target.accepted_statuscodes = [String(expectedStatus)];
        } else {
            throw new Error('Unsupported monitor type: ' + type);
        }
        const matching = () => Object.values(monitors).filter(monitor => monitor.name === name);
        const existing = matching();
        if (!existing.length) {
            await rpc('add', { ...httpMonitor, name, ...target });
            await rpc('getMonitorList');
        }
        const [saved] = matching();
        const matchesTarget = saved && (type === 'dns'
            ? saved.hostname === hostname && Number(saved.port) === 53 &&
              saved.dns_resolve_server === resolver && saved.dns_resolve_type === 'A'
            : saved.url === url && JSON.parse(saved.headers || '{}').Host === headers.Host &&
              (expectedStatus === undefined ||
                JSON.stringify(saved.accepted_statuscodes) === JSON.stringify(target.accepted_statuscodes)));
        if (matching().length !== 1 || saved.type !== type || !matchesTarget || !saved.active) {
            throw new Error(name + ' monitor conflicts with the deployment settings');
        }
        process.stdout.write(JSON.stringify({ monitor_id: saved.id, monitors_created: existing.length ? 0 : 1 }));
        return;
    }
    const definitions = [
        ['Jellyfin', 8096, '/health'], ['Sonarr', 8989, '/ping'],
        ['Radarr', 7878, '/ping'], ['Lidarr', 8686, '/ping'],
        ['Prowlarr', 9696, '/ping'], ['Bazarr', 6767, '/'],
        ['qBittorrent', 8080, '/'], ['SABnzbd', 8081, '/'],
        ['Seerr', 5055, '/api/v1/status'], ['Homarr', 7575, '/'],
    ];
    const existing = new Set(Object.values(monitors).map(x => x.name));
    let created = 0;
    for (const [name, port, path] of definitions) {
        if (existing.has(name)) continue;
        await rpc('add', {
            ...httpMonitor, name, url: `http://${input.address}:${port}${path}`,
        });
        created++;
    }
    if (!existing.has('Alienware SSH')) {
        await rpc('add', {
            name: 'Alienware SSH', type: 'port', hostname: input.address, port: 22,
            interval: 60, retryInterval: 20, maxretries: 2, timeout: 15,
            accepted_statuscodes: ['200-299'], notificationIDList: {}, conditions: [], active: true,
        });
        created++;
    }
    process.stdout.write(JSON.stringify({ administrator_configured: true, monitors_created: created, expected_monitors: 11 }));
})().catch(error => {
    console.error(error.message);
    process.exitCode = 1;
}).finally(() => {
    socket.disconnect();
    clearTimeout(timeout);
});
