#!/usr/bin/env python3
"""Read-only cgroup-v2 resource sample. Run on the Alienware; no Docker socket needed.
Prints sanitized JSON, not process arguments, environment variables or credentials.
"""
import argparse
import datetime as dt
import json
import os
from pathlib import Path
import socket
import subprocess
import time
from zoneinfo import ZoneInfo

APPS = ('jellyfin', 'sonarr', 'radarr', 'lidarr', 'prowlarr', 'bazarr',
        'qbittorrent', 'sabnzbd', 'seerr', 'homarr')

def read(path):
    return Path(path).read_text().strip()

def counters(path):
    return {k: int(v) for k, v in (line.split() for line in read(path).splitlines())}

def identify(cgroup):
    matches = set()
    for pid in read(cgroup / 'cgroup.procs').split():
        proc = Path('/proc') / pid
        try:
            args = (proc / 'cmdline').read_bytes().decode(errors='replace').lower()
            comm = read(proc / 'comm').lower()
        except (OSError, ProcessLookupError):
            continue
        try:
            cwd = os.readlink(proc / 'cwd')
        except OSError:
            cwd = ''
        if '/opt/hermes/' in args or comm.startswith('hermes'):
            matches.add('hermes')
        for app in APPS[:-2]:
            if app in args or app in comm:
                matches.add(app)
        if cwd == '/app/apps/nextjs' and 'next-server' in comm:
            matches.add('homarr')
        if comm == 'uptime-kuma' or (cwd == '/app' and 'server/server.js' in args):
            matches.add('uptime-kuma')
        elif cwd == '/app' and comm == 'node' and 'extra/healthcheck' not in args:
            matches.add('seerr')
    if len(matches) != 1:
        raise RuntimeError(f'Cannot identify {cgroup.name}: {sorted(matches)}')
    return matches.pop()

def io_totals(cgroup):
    totals = {'rbytes': 0, 'wbytes': 0}
    for line in read(cgroup / 'io.stat').splitlines():
        for pair in line.split()[1:]:
            key, value = pair.split('=')
            if key in totals:
                totals[key] += int(value)
    return totals

def sample(cgroup):
    memory = counters(cgroup / 'memory.stat')
    current = int(read(cgroup / 'memory.current'))
    return {'cpu_usage_usec': counters(cgroup / 'cpu.stat')['usage_usec'],
            'memory_current_bytes': current,
            'memory_working_estimate_bytes': max(0, current-memory.get('inactive_file', 0)),
            'memory_anon_bytes': memory.get('anon', 0),
            'memory_file_bytes': memory.get('file', 0),
            'swap_current_bytes': int(read(cgroup / 'memory.swap.current')),
            'tasks': int(read(cgroup / 'pids.current')),
            'io': io_totals(cgroup)}

def host_cpu():
    fields = [int(v) for v in read('/proc/stat').splitlines()[0].split()[1:9]]
    return {'total': sum(fields), 'idle': fields[3], 'iowait': fields[4]}

def host_memory():
    return {line.split(':')[0]: int(line.split()[1])*1024
            for line in read('/proc/meminfo').splitlines() if line.endswith('kB')}

def disk(path):
    v = os.statvfs(path)
    return {'path': path, 'total_bytes': v.f_blocks*v.f_frsize,
            'used_bytes': (v.f_blocks-v.f_bfree)*v.f_frsize,
            'available_bytes': v.f_bavail*v.f_frsize}

def directory_size(path):
    if not Path(path).exists():
        return None
    result = subprocess.run(['du', '-s', '-B1', path], text=True, capture_output=True)
    return int(result.stdout.split()[0]) if result.returncode == 0 else None

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--duration', type=float, default=30)
    parser.add_argument('--interval', type=float, default=5)
    parser.add_argument('--allow-missing', nargs='*', choices=APPS, default=[],
                        help='Explicitly acknowledge intentionally stopped media services')
    args = parser.parse_args()
    if args.duration <= 0 or args.interval <= 0:
        parser.error('duration and interval must be positive')
    groups = {identify(cg): cg for cg in
              sorted(Path('/sys/fs/cgroup/system.slice').glob('docker-*.scope'))}
    if not (set(APPS)-set(args.allow_missing)).issubset(groups) or set(groups)-set(APPS)-{'uptime-kuma', 'hermes'}:
        raise RuntimeError(f'Expected media apps and optional Kuma/Hermes, found {sorted(groups)}')
    start_time = dt.datetime.now(dt.timezone.utc)
    start_cpu = host_cpu()
    readings = [(time.monotonic(), {app: sample(cg) for app, cg in groups.items()})]
    deadline = readings[0][0]+args.duration
    while time.monotonic() < deadline:
        time.sleep(min(args.interval, max(0, deadline-time.monotonic())))
        readings.append((time.monotonic(), {app: sample(cg) for app, cg in groups.items()}))
    elapsed = readings[-1][0]-readings[0][0]
    end_cpu = host_cpu()
    cpu_delta = end_cpu['total']-start_cpu['total']
    idle_delta = end_cpu['idle']-start_cpu['idle']
    wait_delta = end_cpu['iowait']-start_cpu['iowait']
    memory = host_memory()
    identities = set()
    for section in read('/proc/cpuinfo').split('\n\n'):
        fields = dict(line.split(':', 1) for line in section.splitlines() if ':' in line)
        fields = {k.strip(): v.strip() for k, v in fields.items()}
        if 'physical id' in fields and 'core id' in fields:
            identities.add((fields['physical id'], fields['core id']))
    applications = []
    for app in sorted(groups):
        cg = groups[app]
        first, last = readings[0][1][app], readings[-1][1][app]
        cpu_equivalent = (last['cpu_usage_usec']-first['cpu_usage_usec'])/(elapsed*1e6)
        peaks = [(b[1][app]['cpu_usage_usec']-a[1][app]['cpu_usage_usec'])/((b[0]-a[0])*1e6)
                 for a, b in zip(readings, readings[1:])]
        applications.append({'app': app,
            'cpu_logical_equivalents_average': cpu_equivalent,
            'cpu_logical_equivalents_max_interval': max(peaks),
            'host_cpu_capacity_percent_average': cpu_equivalent/os.cpu_count()*100,
            'memory_working_estimate_bytes_end': last['memory_working_estimate_bytes'],
            'memory_working_estimate_bytes_max_sample': max(r[1][app]['memory_working_estimate_bytes'] for r in readings),
            'memory_current_bytes_end': last['memory_current_bytes'],
            'memory_anon_bytes_end': last['memory_anon_bytes'],
            'memory_file_bytes_end': last['memory_file_bytes'],
            'swap_current_bytes_end': last['swap_current_bytes'],
            'tasks_end': last['tasks'],
            'block_read_bytes_per_second': (last['io']['rbytes']-first['io']['rbytes'])/elapsed,
            'block_write_bytes_per_second': (last['io']['wbytes']-first['io']['wbytes'])/elapsed,
            'config_allocated_bytes': directory_size({'uptime-kuma': '/opt/uptime-kuma/data',
                'hermes': '/opt/hermes/data'}.get(app, '/opt/media-stack/config/'+app)),
            'cpu_max': read(cg/'cpu.max'),
            'cpuset_effective': read(cg/'cpuset.cpus.effective'),
            'memory_max': read(cg/'memory.max'),
            'pids_max': read(cg/'pids.max')})
    output = {'schema_version': 1, 'hostname': socket.gethostname(),
        'explicitly_allowed_missing_apps': sorted(set(args.allow_missing)-set(groups)),
        'started_at_utc': start_time.isoformat(),
        'started_at_ist': start_time.astimezone(ZoneInfo('Asia/Kolkata')).isoformat(),
        'ended_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
        'sample_duration_seconds': elapsed, 'sample_count': len(readings),
        'source': 'cgroup v2 counters; /proc; statvfs; du allocated directory sizes',
        'host': {'logical_cpus': os.cpu_count(), 'physical_cores': len(identities),
            'cpu_busy_percent': (cpu_delta-idle_delta-wait_delta)/cpu_delta*100,
            'cpu_iowait_percent': wait_delta/cpu_delta*100,
            'load_average': list(os.getloadavg()),
            'memory_total_bytes': memory['MemTotal'],
            'memory_available_bytes': memory['MemAvailable'],
            'memory_used_estimate_bytes': memory['MemTotal']-memory['MemAvailable'],
            'swap_total_bytes': memory['SwapTotal'],
            'swap_used_bytes': memory['SwapTotal']-memory['SwapFree']},
        'disks': [disk(p) for p in ['/', '/srv/media', '/srv/ssd']],
        'jellyfin_cache_allocated_bytes': directory_size('/opt/media-stack/cache/jellyfin'),
        'applications': applications}
    print(json.dumps(output, indent=2))

if __name__ == '__main__':
    main()
