#!/usr/bin/env bash
set -Eeuo pipefail

usage() {
  cat <<'EOF'
Usage:
  sudo deploy/install_display_appliance.sh --monitor-config PATH [--start]

Installs or updates the deterministic Rewind Display runtime. The supplied
monitor config must satisfy the six-camera profile. By default the script does
not restart the visible display session; pass --start to enable and restart it.
EOF
}

monitor_config=""
start_display=false

while (($#)); do
  case "$1" in
    --monitor-config)
      [[ $# -ge 2 ]] || { usage >&2; exit 2; }
      monitor_config=$2
      shift 2
      ;;
    --start)
      start_display=true
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "ERROR: unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ ${EUID} -ne 0 ]]; then
  echo "ERROR: run as root with sudo" >&2
  exit 2
fi
if [[ -z ${monitor_config} || ! -f ${monitor_config} ]]; then
  echo "ERROR: --monitor-config must name an existing file" >&2
  exit 2
fi

script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
repo_dir=$(cd "${script_dir}/.." && pwd)
source_dir="${repo_dir}/surveillance"
monitor_config=$(realpath "${monitor_config}")

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y \
  ca-certificates \
  curl \
  ffmpeg \
  gnupg \
  lightdm \
  mpv \
  openssh-server \
  python3-pygame \
  python3-xlib \
  python3-yaml \
  rsync \
  unclutter \
  wmctrl \
  x11-xserver-utils \
  xdotool \
  xfce4

install -d -m 0755 /usr/share/keyrings
curl -fsSL https://pkg.cloudflare.com/cloudflare-main.gpg \
  | tee /usr/share/keyrings/cloudflare-main.gpg >/dev/null
printf '%s\n' \
  'deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] https://pkg.cloudflare.com/cloudflared any main' \
  > /etc/apt/sources.list.d/cloudflared.list
apt-get update
apt-get install -y cloudflared

python3 "${script_dir}/validate_monitor_config.py" \
  --profile six-camera "${monitor_config}"

if id opensurv >/dev/null 2>&1; then
  opensurv_home=$(getent passwd opensurv | cut -d: -f6)
  if [[ ${opensurv_home} != /home/opensurv ]]; then
    echo "ERROR: existing opensurv user has unexpected home: ${opensurv_home}" >&2
    exit 1
  fi
else
  useradd --create-home --home-dir /home/opensurv --shell /bin/bash opensurv
fi

install -d -m 0755 /var/backups/rewind-display
if [[ -d /home/opensurv/etc ]]; then
  backup_dir="/var/backups/rewind-display/etc-$(date -u +%Y%m%dT%H%M%SZ)"
  cp -a /home/opensurv/etc "${backup_dir}"
  echo "Existing config backed up to ${backup_dir}"
fi

install -d -o opensurv -g opensurv -m 0755 \
  /home/opensurv/bin \
  /home/opensurv/etc \
  /home/opensurv/lib \
  /home/opensurv/logs \
  /home/opensurv/.config/mpv

rsync -a "${source_dir}/core/" /home/opensurv/lib/core/
rsync -a "${source_dir}/demo/" /home/opensurv/lib/demo/
rsync -a "${source_dir}/images/" /home/opensurv/lib/images/
install -m 0755 "${source_dir}/surveillance.py" /home/opensurv/lib/surveillance.py
install -m 0755 "${repo_dir}/opensurv" /home/opensurv/bin/opensurv
install -m 0644 "${repo_dir}/opensurv.desktop" /usr/share/xsessions/opensurv.desktop

for config_name in general.yml logging.yml monitor2.yml; do
  if [[ ! -f /home/opensurv/etc/${config_name} ]]; then
    install -m 0644 \
      "${source_dir}/etc/${config_name}" \
      "/home/opensurv/etc/${config_name}"
  fi
done
install -m 0600 "${monitor_config}" /home/opensurv/etc/monitor1.yml
printf '%s\n' 'msg-level=all=fatal' > /home/opensurv/.config/mpv/mpv.conf

if [[ -e /etc/opensurv && ! -L /etc/opensurv ]]; then
  echo "ERROR: /etc/opensurv exists and is not a symlink; refusing to replace it" >&2
  exit 1
fi
ln -sfn /home/opensurv/etc /etc/opensurv

install -d -m 0755 /etc/lightdm/lightdm.conf.d
install -m 0644 \
  "${script_dir}/files/50-rewind-display.conf" \
  /etc/lightdm/lightdm.conf.d/50-rewind-display.conf

install -d -m 0755 /etc/retailrewind
source_commit=$(git -C "${repo_dir}" rev-parse HEAD 2>/dev/null || echo unknown)
printf '%s\n' \
  'DISPLAY_PROFILE=retail-rewind-six-camera-v1' \
  "REWIND_DISPLAY_COMMIT=${source_commit}" \
  'CLOUDFLARED_OWNERSHIP=host-systemd' \
  > /etc/retailrewind/display-appliance.env
chmod 0644 /etc/retailrewind/display-appliance.env

chown -R opensurv:opensurv /home/opensurv
systemctl daemon-reload
systemctl enable lightdm
systemctl set-default graphical.target

if [[ ${start_display} == true ]]; then
  systemctl restart lightdm
  echo "Rewind Display restarted"
else
  echo "Rewind Display installed; visible session was not restarted"
  echo "Start when ready: sudo systemctl restart lightdm"
fi

echo "Installed profile: retail-rewind-six-camera-v1"
echo "cloudflared is installed on the host; configure Access before enabling its connector"
