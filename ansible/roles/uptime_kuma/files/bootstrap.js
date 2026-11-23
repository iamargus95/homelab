// Runs inside Kuma's image, using its own socket.io-client dependency.
const fs = require('fs');
const { io } = require('socket.io-client');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const socket = io('http://127.0.0.1:3001', { transports: ['websocket'], reconnection: false });
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
    if (await rpc('needSetup')) await rpc('setup', input.username, input.password);
    await rpc('login', { username: input.username, password: input.password, token: '' });
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
            name, type: 'http', url: `http://${input.address}:${port}${path}`,
            method: 'GET', interval: 60, retryInterval: 20, maxretries: 2,
            timeout: 15, resendInterval: 0, accepted_statuscodes: ['200-299'],
            ignoreTls: false, upsideDown: false, maxredirects: 5,
            notificationIDList: {}, conditions: [], active: true,
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
    socket.disconnect();
    clearTimeout(timeout);
})().catch(error => {
    console.error(error.message);
    socket.disconnect();
    clearTimeout(timeout);
    process.exitCode = 1;
});
