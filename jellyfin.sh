#!/bin/bash
# Full Media Stack Reinstall - Optimized & Rerunnable
# Handles Proxmox 8 + ZFS + Hardware Transcoding + FlareSolverr Fixes

# Load secrets
source ./env.local.secrets.sh
set -e

echo "==> [1/6] CLEANING UP EXISTING DEPLOYMENTS..."
for ID in $JELLYFIN_ID $MEDIA_ID; do
  if pct status $ID >/dev/null 2>&1; then
    echo "    Stopping and destroying Container $ID..."
    pct stop $ID >/dev/null 2>&1 || true
    pct destroy $ID >/dev/null 2>&1 || true
  fi
done

echo "==> [2/6] PREPARING HOST & ZFS..."
for dir in movies tv downloads videos; do
  zfs create -p ${ZFS_POOL}/media/$dir 2>/dev/null || true
done
chown -R 101000:101000 $MEDIA_DIR
chmod -R 775 $MEDIA_DIR

# Ensure LXC Namespace mapping is allowed on host
grep -q "root:101000:1" /etc/subuid || echo "root:101000:1" >> /etc/subuid
grep -q "root:101000:1" /etc/subgid || echo "root:101000:1" >> /etc/subgid

echo "==> [3/6] FETCHING UBUNTU TEMPLATE..."
pveam update >/dev/null 2>&1
TEMPLATE=$(pveam available --section system | grep "ubuntu-22.04-standard" | awk '{print $2}' | head -1)
pveam download $TEMPLATE_STORAGE $TEMPLATE >/dev/null 2>&1 || true
TEMPLATE_PATH="$TEMPLATE_STORAGE:vztmpl/$TEMPLATE"

echo "==> [4/6] INSTALLING JELLYFIN (CT$JELLYFIN_ID)..."
pct create $JELLYFIN_ID "$TEMPLATE_PATH" --hostname jellyfin --rootfs "$STORAGE:10" \
  --cores 2 --memory 2048 --net0 name=eth0,bridge=$BRIDGE,ip=dhcp --nameserver "$DNS_SERVERS" \
  --password "$PASSWORD" --unprivileged 1 --features nesting=1 --onboot 1

# Inject Hardware Accel & Mapping
cat >> /etc/pve/lxc/${JELLYFIN_ID}.conf <<EOF
lxc.cgroup2.devices.allow: c 226:0 rwm
lxc.cgroup2.devices.allow: c 226:128 rwm
lxc.cgroup2.devices.allow: c 10:200 rwm
lxc.mount.entry: /dev/dri/card0 dev/dri/card0 none bind,optional,create=file
lxc.mount.entry: /dev/dri/renderD128 dev/dri/renderD128 none bind,optional,create=file
lxc.mount.entry: /dev/net/tun dev/net/tun none bind,create=file
lxc.idmap: u 0 100000 1000
lxc.idmap: g 0 100000 1000
lxc.idmap: u 1000 101000 1
lxc.idmap: g 1000 101000 1
lxc.idmap: u 1001 101001 64535
lxc.idmap: g 1001 101001 64535
EOF

pct set $JELLYFIN_ID --mp0 $MEDIA_DIR,mp=/media
pct start $JELLYFIN_ID
sleep 8

pct exec $JELLYFIN_ID -- bash -c "
  apt-get update && apt-get install -y curl gnupg
  curl -fsSL https://repo.jellyfin.org/ubuntu/jellyfin_team.gpg.key | gpg --dearmor -o /usr/share/keyrings/jellyfin.gpg
  echo 'deb [signed-by=/usr/share/keyrings/jellyfin.gpg] https://repo.jellyfin.org/ubuntu jammy main' > /etc/apt/sources.list.d/jellyfin.list
  apt-get update && apt-get install -y jellyfin
  groupadd -g 1000 mediagroup 2>/dev/null || true
  usermod -aG mediagroup jellyfin
  curl -fsSL https://tailscale.com/install.sh | sh
  [ -n '$TS_AUTH_KEY' ] && tailscale up --authkey $TS_AUTH_KEY --accept-routes || true
"

echo "==> [5/6] INSTALLING MEDIA STACK (CT$MEDIA_ID)..."
pct create $MEDIA_ID "$TEMPLATE_PATH" --hostname mediastack --rootfs "$STORAGE:15" \
  --cores 2 --memory 4096 --net0 name=eth0,bridge=$BRIDGE,ip=dhcp --nameserver "$DNS_SERVERS" \
  --password "$PASSWORD" --unprivileged 1 --features nesting=1 --onboot 1

cat >> /etc/pve/lxc/${MEDIA_ID}.conf <<EOF
lxc.cgroup2.devices.allow: c 10:200 rwm
lxc.mount.entry: /dev/net/tun dev/net/tun none bind,create=file
lxc.idmap: u 0 100000 1000
lxc.idmap: g 0 100000 1000
lxc.idmap: u 1000 101000 1
lxc.idmap: g 1000 101000 1
lxc.idmap: u 1001 101001 64535
lxc.idmap: g 1001 101001 64535
EOF

pct set $MEDIA_ID --mp0 $MEDIA_DIR,mp=/data
pct start $MEDIA_ID
sleep 8

pct exec $MEDIA_ID -- bash -c "
  apt-get update && apt-get install -y curl software-properties-common sqlite3 xvfb libxi6 libgconf-2-4 libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxext6 libxfixes3 libxrandr2 libgbm1 libpango-1.0-0 libcairo2 libasound2

  groupadd -g 1000 mediagroup 2>/dev/null || true
  useradd -u 1000 -g 1000 -m -s /bin/false mediauser 2>/dev/null || true

  # FlareSolverr - Force Flattened Install
  mkdir -p /opt/flaresolverr/temp
  curl -sL https://github.com/FlareSolverr/FlareSolverr/releases/download/${FLARE_VER}/flaresolverr_linux_x64.tar.gz | tar -xz -C /opt/flaresolverr/temp
  REAL_PATH=\$(find /opt/flaresolverr/temp -name flaresolverr -type f -exec dirname {} \;)
  mv \$REAL_PATH/* /opt/flaresolverr/ && rm -rf /opt/flaresolverr/temp
  chown -R mediauser:mediagroup /opt/flaresolverr && chmod +x /opt/flaresolverr/flaresolverr

  # Arrs
  for app in radarr sonarr prowlarr; do
    mkdir -p /opt/\$app
    case \$app in
      radarr) url='https://radarr.servarr.com/v1/update/master/updatefile?os=linux&runtime=netcore&arch=x64' ;;
      sonarr) url='https://services.sonarr.tv/v1/download/main/latest?version=4&os=linux&arch=x64' ;;
      prowlarr) url='https://prowlarr.servarr.com/v1/update/master/updatefile?os=linux&runtime=netcore&arch=x64' ;;
    esac
    curl -sL \"\$url\" | tar -xz -C /opt/\$app --strip-components=1
    chown -R mediauser:mediagroup /opt/\$app
  done

  # Service Creation
  for app in flaresolverr radarr sonarr prowlarr; do
    case \$app in
      flaresolverr) bin='/opt/flaresolverr/flaresolverr'; env='Environment=LD_LIBRARY_PATH=/opt/flaresolverr' ;;
      radarr) bin='/opt/radarr/Radarr -nobrowser -data=/var/lib/radarr'; env='' ;;
      sonarr) bin='/opt/sonarr/Sonarr -nobrowser -data=/var/lib/sonarr'; env='' ;;
      prowlarr) bin='/opt/prowlarr/Prowlarr -nobrowser -data=/var/lib/prowlarr'; env='' ;;
    esac
    mkdir -p /var/lib/\$app && chown mediauser:mediagroup /var/lib/\$app
    echo -e \"[Unit]\nDescription=\$app\nAfter=network.target\n[Service]\nUser=mediauser\nGroup=mediagroup\nWorkingDirectory=/opt/\$app\n\$env\nExecStart=\$bin\nRestart=always\n[Install]\nWantedBy=multi-user.target\" > /etc/systemd/system/\$app.service
    systemctl enable \$app && systemctl start \$app
  done

  # Transmission
  add-apt-repository -y ppa:transmissionbt/ppa && apt-get update && apt-get install -y transmission-daemon
  systemctl stop transmission-daemon
  mkdir -p /etc/systemd/system/transmission-daemon.service.d
  echo -e '[Service]\nUser=mediauser\nGroup=mediagroup' > /etc/systemd/system/transmission-daemon.service.d/override.conf
  systemctl daemon-reload && systemctl start transmission-daemon

  curl -fsSL https://tailscale.com/install.sh | sh
  [ -n '$TS_AUTH_KEY' ] && tailscale up --authkey $TS_AUTH_KEY --accept-routes || true
"

echo "==> [6/6] FETCHING LIVE CONNECTION DATA..."
JF_IP_LIVE=$(pct exec $JELLYFIN_ID -- ip -4 addr show eth0 | grep -oP '(?<=inet\s)\d+(\.\d+){3}')
MS_IP_LIVE=$(pct exec $MEDIA_ID -- ip -4 addr show eth0 | grep -oP '(?<=inet\s)\d+(\.\d+){3}')

echo "-----------------------------------------------------"
echo " SERVER REINSTALL COMPLETE "
echo "-----------------------------------------------------"
echo " Jellyfin:     http://${JF_IP_LIVE}:8096"
echo " Transmission: http://${MS_IP_LIVE}:9091"
echo " Radarr:       http://${MS_IP_LIVE}:7878"
echo " Sonarr:       http://${MS_IP_LIVE}:8989"
echo " Prowlarr:     http://${MS_IP_LIVE}:9696"
echo " FlareSolverr: http://${MS_IP_LIVE}:8191"
echo "-----------------------------------------------------"
echo " Tip: Use Prowlarr to add YTS and link it to Radarr."
