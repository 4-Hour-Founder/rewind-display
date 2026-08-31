#!/usr/bin/env bash
# Read-only host assessment for a prospective Rewind Display appliance.
# It deliberately collects every available field and does not fail merely
# because the host is incomplete or unhealthy.
set -u

value_or_unknown() {
  local value=${1:-}
  if [[ -n ${value} ]]; then
    printf '%s' "${value}"
  else
    printf 'unknown'
  fi
}

systemd_state() {
  local action=$1
  local unit=$2
  local state=""
  if command -v systemctl >/dev/null 2>&1; then
    state=$(systemctl "${action}" "${unit}" 2>/dev/null || true)
    value_or_unknown "${state}"
  else
    printf 'unavailable'
  fi
}

read_os_release() {
  local key=$1
  if [[ -r /etc/os-release ]]; then
    sed -n "s/^${key}=//p" /etc/os-release | head -n 1 | tr -d '"'
  fi
}

printf 'preflight_schema=retail-rewind-public-display-v1\n'
printf 'hostname=%s\n' "$(value_or_unknown "$(hostname 2>/dev/null)")"

model=""
if [[ -r /proc/device-tree/model ]]; then
  model=$(tr -d '\000' </proc/device-tree/model 2>/dev/null)
fi
printf 'model=%s\n' "$(value_or_unknown "${model}")"

architecture=""
if command -v dpkg >/dev/null 2>&1; then
  architecture=$(dpkg --print-architecture 2>/dev/null)
else
  architecture=$(uname -m 2>/dev/null)
fi
printf 'architecture=%s\n' "$(value_or_unknown "${architecture}")"
printf 'os_id=%s\n' "$(value_or_unknown "$(read_os_release ID)")"
printf 'os_version=%s\n' "$(value_or_unknown "$(read_os_release VERSION_ID)")"
printf 'kernel=%s\n' "$(value_or_unknown "$(uname -r 2>/dev/null)")"

root_available_kib=$(df -Pk / 2>/dev/null | awk 'NR == 2 {print $4}')
memory_total_kib=""
if [[ -r /proc/meminfo ]]; then
  memory_total_kib=$(awk '/^MemTotal:/ {print $2}' /proc/meminfo)
fi
printf 'root_available_kib=%s\n' "$(value_or_unknown "${root_available_kib}")"
printf 'memory_total_kib=%s\n' "$(value_or_unknown "${memory_total_kib}")"

printf 'ssh_active=%s\n' "$(systemd_state is-active ssh)"
printf 'ssh_enabled=%s\n' "$(systemd_state is-enabled ssh)"
printf 'lightdm_active=%s\n' "$(systemd_state is-active lightdm)"
printf 'lightdm_enabled=%s\n' "$(systemd_state is-enabled lightdm)"

cloudflared_version=""
if command -v cloudflared >/dev/null 2>&1; then
  cloudflared_version=$(cloudflared --version 2>/dev/null | head -n 1)
fi
printf 'cloudflared_version=%s\n' "$(value_or_unknown "${cloudflared_version}")"
printf 'cloudflared_active=%s\n' "$(systemd_state is-active cloudflared)"
printf 'cloudflared_enabled=%s\n' "$(systemd_state is-enabled cloudflared)"

if [[ -r /etc/retailrewind/display-appliance.env ]]; then
  printf 'appliance_metadata=present\n'
  while IFS='=' read -r key value; do
    case "${key}" in
      DISPLAY_PROFILE|REWIND_DISPLAY_COMMIT|CLOUDFLARED_OWNERSHIP)
        printf '%s=%s\n' "$(printf '%s' "${key}" | tr '[:upper:]' '[:lower:]')" "${value}"
        ;;
    esac
  done </etc/retailrewind/display-appliance.env
else
  printf 'appliance_metadata=absent\n'
fi

if [[ -e /etc/opensurv/monitor1.yml ]]; then
  printf 'monitor1_config=present\n'
else
  printf 'monitor1_config=absent\n'
fi

mpv_count=""
if command -v pgrep >/dev/null 2>&1; then
  mpv_count=$(pgrep -x mpv 2>/dev/null | wc -l | tr -d ' ')
fi
printf 'mpv_processes=%s\n' "$(value_or_unknown "${mpv_count}")"

connected_outputs=""
for status_file in /sys/class/drm/*/status; do
  [[ -r ${status_file} ]] || continue
  if [[ $(<"${status_file}") == connected ]]; then
    output=${status_file%/status}
    output=${output##*/}
    connected_outputs="${connected_outputs}${connected_outputs:+,}${output}"
  fi
done
printf 'connected_display_outputs=%s\n' "$(value_or_unknown "${connected_outputs}")"

temperature=""
if command -v vcgencmd >/dev/null 2>&1; then
  temperature=$(vcgencmd measure_temp 2>/dev/null | sed 's/^temp=//')
elif [[ -r /sys/class/thermal/thermal_zone0/temp ]]; then
  temperature=$(awk '{printf "%.1fC", $1 / 1000}' /sys/class/thermal/thermal_zone0/temp)
fi
printf 'temperature=%s\n' "$(value_or_unknown "${temperature}")"

printf 'preflight_complete=yes\n'
exit 0
