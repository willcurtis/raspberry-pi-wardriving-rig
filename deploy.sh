#!/usr/bin/env bash
set -euo pipefail

RECONFIGURE=0
NONINTERACTIVE=0
for arg in "$@"; do
  case "$arg" in
    --reconfigure) RECONFIGURE=1 ;;
    --non-interactive) NONINTERACTIVE=1 ;;
    --help)
      cat <<'EOF'
Usage: sudo ./deploy.sh [--reconfigure] [--non-interactive]

Environment overrides:
  WIRELESS_INTERFACE  Capture interface
  GPS_DEVICE          GPS serial device (default: /dev/ttyACM0)
  WEB_USERNAME        Dashboard username (default: wardrive)
  WEB_PASSWORD        Required for new non-interactive installs
  WIGLE_API_NAME      Required for new non-interactive installs
  WIGLE_API_TOKEN     Required for new non-interactive installs
EOF
      exit 0 ;;
    *) echo "Unknown option: $arg" >&2; exit 2 ;;
  esac
done

if [[ ${EUID} -ne 0 ]]; then
  echo "Run this installer with sudo." >&2
  exit 1
fi

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR=/opt/wardrive
CONFIG_DIR=/etc/wardrive
CAPTURE_DIR=/var/lib/wardrive/captures
DEVICE_HOSTNAME=wardriver

detect_wireless() {
  local route_interface candidate
  route_interface="$(ip route show default 2>/dev/null | awk 'NR==1 {print $5}')"
  while IFS= read -r candidate; do
    [[ -n "$candidate" && "$candidate" != "$route_interface" ]] && { echo "$candidate"; return; }
  done < <(iw dev 2>/dev/null | awk '$1=="Interface" {print $2}')
  iw dev 2>/dev/null | awk '$1=="Interface" {print $2; exit}'
}

prompt_value() {
  local variable_name=$1 prompt=$2 secret=${3:-0} current
  current="${!variable_name:-}"
  if [[ -n "$current" ]]; then return; fi
  if [[ $NONINTERACTIVE -eq 1 ]]; then
    echo "$variable_name is required in non-interactive mode" >&2
    exit 2
  fi
  if [[ "$secret" -eq 1 ]]; then
    read -r -s -p "$prompt: " current
    echo
  else
    read -r -p "$prompt: " current
  fi
  [[ -n "$current" ]] || { echo "$variable_name cannot be empty" >&2; exit 2; }
  printf -v "$variable_name" '%s' "$current"
}

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y kismet gpsd gpsd-clients iw python3 curl ca-certificates avahi-daemon

# Give the appliance a predictable LAN identity and advertise it over mDNS.
hostnamectl set-hostname "$DEVICE_HOSTNAME"
if grep -qE '^127\.0\.1\.1[[:space:]]' /etc/hosts; then
  sed -i -E "s/^(127\\.0\\.1\\.1)[[:space:]].*/\\1\\t${DEVICE_HOSTNAME}/" /etc/hosts
else
  printf '127.0.1.1\t%s\n' "$DEVICE_HOSTNAME" >> /etc/hosts
fi

WIRELESS_INTERFACE="${WIRELESS_INTERFACE:-$(detect_wireless)}"
prompt_value WIRELESS_INTERFACE "Wireless capture interface"
GPS_DEVICE="${GPS_DEVICE:-/dev/ttyACM0}"
WEB_USERNAME="${WEB_USERNAME:-wardrive}"

install -d -m 0755 "$INSTALL_DIR/app" "$INSTALL_DIR/scripts" "$CONFIG_DIR"
getent group wardrive >/dev/null || groupadd --system wardrive
getent group wardrive-web >/dev/null || groupadd --system wardrive-web
id kismet >/dev/null 2>&1 || useradd --system --home /var/lib/kismet --shell /usr/sbin/nologin kismet
id wardrive-web >/dev/null 2>&1 || useradd --system --gid wardrive-web --home "$CAPTURE_DIR" --shell /usr/sbin/nologin wardrive-web
usermod -a -G wardrive kismet
usermod -a -G wardrive wardrive-web
install -d -o kismet -g wardrive -m 2775 "$CAPTURE_DIR"
install -m 0755 "$PROJECT_DIR/app/server.py" "$INSTALL_DIR/app/server.py"
install -m 0755 "$PROJECT_DIR/scripts/upload_wigle.py" "$INSTALL_DIR/scripts/upload_wigle.py"

sed "s/__WIRELESS_INTERFACE__/${WIRELESS_INTERFACE//\//\\/}/g" \
  "$PROJECT_DIR/config/kismet_site.conf.template" > /etc/kismet/kismet_wardrive.conf
chown root:kismet /etc/kismet/kismet_wardrive.conf
chmod 0640 /etc/kismet/kismet_wardrive.conf

if [[ ! -s "$CONFIG_DIR/web.env" || $RECONFIGURE -eq 1 ]]; then
  prompt_value WEB_PASSWORD "Dashboard password" 1
  PASSWORD_HASH="$(WEB_PASSWORD_VALUE="$WEB_PASSWORD" python3 - <<'PY'
import hashlib, os, secrets
salt = secrets.token_bytes(16)
iterations = 310000
value = hashlib.pbkdf2_hmac("sha256", os.environ["WEB_PASSWORD_VALUE"].encode(), salt, iterations)
print(f"{iterations}${salt.hex()}${value.hex()}")
PY
)"
  {
    printf 'WEB_USERNAME=%s\n' "$WEB_USERNAME"
    printf 'WEB_PASSWORD_HASH=%s\n' "$PASSWORD_HASH"
    printf 'WEB_BIND=0.0.0.0\nWEB_PORT=8080\n'
  } > "$CONFIG_DIR/web.env"
  chown root:wardrive-web "$CONFIG_DIR/web.env"
  chmod 0640 "$CONFIG_DIR/web.env"
fi

if [[ ! -s "$CONFIG_DIR/wigle.env" || $RECONFIGURE -eq 1 ]]; then
  prompt_value WIGLE_API_NAME "WiGLE API name"
  prompt_value WIGLE_API_TOKEN "WiGLE API token" 1
  {
    printf 'WIGLE_API_NAME=%s\n' "$WIGLE_API_NAME"
    printf 'WIGLE_API_TOKEN=%s\n' "$WIGLE_API_TOKEN"
    printf 'WIGLE_UPLOAD_URL=https://api.wigle.net/api/v2/file/upload\n'
  } > "$CONFIG_DIR/wigle.env"
  chown root:root "$CONFIG_DIR/wigle.env"
  chmod 0600 "$CONFIG_DIR/wigle.env"
fi

if [[ -e "$GPS_DEVICE" ]]; then
  sed -i "s|^DEVICES=.*|DEVICES=\"$GPS_DEVICE\"|" /etc/default/gpsd
  sed -i 's|^GPSD_OPTIONS=.*|GPSD_OPTIONS=\"-n\"|' /etc/default/gpsd
else
  echo "Warning: $GPS_DEVICE is not present; configure /etc/default/gpsd when attached." >&2
fi

install -m 0644 "$PROJECT_DIR/systemd/"*.service /etc/systemd/system/
cat > /etc/sudoers.d/wardrive-web <<'EOF'
wardrive-web ALL=(root) NOPASSWD: /bin/systemctl start wardrive-kismet.service
wardrive-web ALL=(root) NOPASSWD: /bin/systemctl stop wardrive-kismet.service
wardrive-web ALL=(root) NOPASSWD: /bin/systemctl restart wardrive-kismet.service
wardrive-web ALL=(root) NOPASSWD: /bin/systemctl kill --signal=SIGKILL wardrive-kismet.service
wardrive-web ALL=(root) NOPASSWD: /bin/systemctl start wardrive-upload.service
wardrive-web ALL=(root) NOPASSWD: /bin/systemctl start gpsd.socket gpsd.service
wardrive-web ALL=(root) NOPASSWD: /bin/systemctl stop gpsd.service gpsd.socket
wardrive-web ALL=(root) NOPASSWD: /bin/systemctl restart gpsd.socket gpsd.service
wardrive-web ALL=(root) NOPASSWD: /bin/systemctl start avahi-daemon.service
wardrive-web ALL=(root) NOPASSWD: /bin/systemctl stop avahi-daemon.service
wardrive-web ALL=(root) NOPASSWD: /bin/systemctl restart avahi-daemon.service
EOF
chmod 0440 /etc/sudoers.d/wardrive-web
visudo -cf /etc/sudoers.d/wardrive-web >/dev/null

systemctl daemon-reload
systemctl enable --now avahi-daemon.service gpsd.socket wardrive-web.service
systemctl restart avahi-daemon.service
systemctl restart gpsd.service
systemctl enable wardrive-kismet.service
systemctl restart wardrive-web.service

if command -v ufw >/dev/null && ufw status | grep -q '^Status: active'; then
  ufw allow 5353/udp comment 'mDNS discovery'
  ufw allow 8080/tcp comment 'Wardrive dashboard'
fi

echo
echo "Wardrive rig installed."
echo "Hostname: ${DEVICE_HOSTNAME}"
echo "Dashboard: http://${DEVICE_HOSTNAME}.local:8080"
echo "Capture interface: $WIRELESS_INTERFACE"
echo "GPS device: $GPS_DEVICE"
