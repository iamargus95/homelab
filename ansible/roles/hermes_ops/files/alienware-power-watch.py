#!/usr/bin/env python3
"""Alert once per AC outage and once at or below 20% during discharge."""
import json
import os
from pathlib import Path

root = Path(os.environ.get('POWER_SUPPLY_ROOT', '/sys/class/power_supply'))
state_path = Path(os.environ.get('POWER_WATCH_STATE', '/opt/data/power-watch/state.json'))

def read(path):
    return path.read_text().strip()

try:
    devices = list(root.iterdir())
    mains = [d for d in devices if (d / 'type').exists() and read(d / 'type') == 'Mains']
    batteries = [d for d in devices if (d / 'type').exists() and read(d / 'type') == 'Battery']
    if not mains or not batteries:
        raise ValueError('AC or battery device not visible')
    online = any(read(d / 'online') == '1' for d in mains)
    capacity = min(int(read(d / 'capacity')) for d in batteries)
    if not 0 <= capacity <= 100:
        raise ValueError('invalid battery capacity')
    try:
        state = json.loads(state_path.read_text())
    except FileNotFoundError:
        state = {}
    messages = []
    if not online and not state.get('outage_alerted'):
        messages.append(f'⚠️ Alienware external power disconnected. Battery: {capacity}%.')
    if not online and capacity <= 20 and not state.get('low_alerted'):
        messages.append(f'🚨 Alienware battery is at {capacity}% with external power disconnected. Plug it in now.')
    state = {'outage_alerted': not online, 'low_alerted': not online and (capacity <= 20 or state.get('low_alerted', False))}
    state_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = state_path.with_suffix('.tmp')
    tmp.write_text(json.dumps(state))
    tmp.replace(state_path)
    if messages:
        print('\n'.join(messages))
except Exception as exc:
    print(f'⚠️ Alienware power monitor could not read power status: {exc}')
