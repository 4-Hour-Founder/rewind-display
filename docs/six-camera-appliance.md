# Six-camera public-display appliance

This is the repeatable Retail Rewind Raspberry Pi display profile derived from
the Bethel Church beta display. It preserves the useful display behavior while
removing Bethel-specific camera addresses, credentials, and labels.

## Contract

The version 1 profile is:

- a dedicated Debian arm64 display appliance, preferably Raspberry Pi 5;
- one 3840x2160 display when the monitor supports it;
- one non-rotating screen with six camera slots;
- automatic three-column by two-row placement;
- H.264 go2rtc substreams served by the site's Retail Rewind NVR;
- RTSP over TCP with MPV's low-latency profile;
- no audio, embedded camera credentials, or fixed coordinates; and
- host-level Cloudflare Tunnel plus Cloudflare Access for direct management.

Bethel currently uses direct-camera RTSP URLs. Those URLs are legacy
site-specific inputs and are not part of this profile. New displays should use
NVR/go2rtc restreams so camera credentials remain on the NVR.

## Division of responsibility

The agent handles discovery and site-specific judgment:

1. Identify the target Pi, NVR, monitor, and approved camera views.
2. Resolve six manager-facing camera names to six go2rtc substream names.
3. Confirm that each substream is H.264 and reachable from the display LAN.
4. Prepare a site-specific config from the versioned template.
5. Establish the display's unique Cloudflare Tunnel and Access application.
6. Visually confirm the resulting camera order and public suitability.

The scripts handle repeatable mechanics:

- `deploy/validate_monitor_config.py` enforces the six-camera contract without
  printing stream URLs.
- `deploy/install_display_appliance.sh` installs packages and the branded
  runtime, backs up an existing config, installs the supplied profile,
  configures LightDM autologin, and installs host-level `cloudflared` without
  enabling an unprotected connector.

Do not have an agent improvise a different package list, runtime path, layout,
or startup mechanism when the target satisfies this contract. Change the
versioned contract and scripts first if the standard itself needs to change.

## Prepare a site config

Copy the template outside the repository so customer-specific values cannot be
committed accidentally:

```sh
cp examples/retail-rewind-six-camera.yml /tmp/site-monitor1.yml
```

Replace `NVR_HOST`, `STREAM_SLOT_1` through `STREAM_SLOT_6`, and the six display
labels. Use only approved go2rtc substreams. Then validate:

```sh
python3 deploy/validate_monitor_config.py \
  --profile six-camera /tmp/site-monitor1.yml
```

The validator rejects embedded credentials, non-RTSP sources, the wrong stream
count, unexpected layout settings, and missing reliability options. It never
prints configured URLs.

## Install or update a Pi

On a dedicated display appliance:

```sh
git clone https://github.com/FFTY50/rewind-display
cd rewind-display
sudo deploy/install_display_appliance.sh \
  --monitor-config /tmp/site-monitor1.yml
```

The default does not restart the visible session. Review the reported backup
path and start the display explicitly:

```sh
sudo systemctl restart lightdm
```

For a fresh, attended install where an immediate restart is intended, add
`--start` to the installer command.

## Direct management

Each Pi needs a unique `<device>-ssh.micromanagers.net` hostname and its own
named Cloudflare Tunnel. The appliance installer places `cloudflared` on the
host but deliberately does not enable an unprotected connector. Create the
Access application and attach the existing human-operator Allow policy and
fleet-automation Service Auth policy before enabling `cloudflared.service`.
Do not add it to Docker.

Follow make-before-break on an existing box: preserve the current route, prove
key authentication, create Access protection, enable the connector, prove a
new direct SSH session, and only then switch the normal alias.

## Acceptance checks

```sh
python3 deploy/validate_monitor_config.py \
  --profile six-camera /etc/opensurv/monitor1.yml
systemctl is-active lightdm cloudflared
systemctl is-enabled lightdm cloudflared
pgrep -cx mpv
sudo -u opensurv env DISPLAY=:0 \
  XAUTHORITY=/home/opensurv/.Xauthority xrandr --current
```

Accept the device only when:

- the validator passes and reports no credentials;
- six MPV processes remain running after the initial connection period;
- the connected monitor uses the intended resolution;
- all six views appear in the approved order with no sensitive view exposed;
- load and temperature remain stable; and
- direct Access SSH works without an NVR ProxyJump.

## Rollback

The installer records the previous `/home/opensurv/etc` directory under
`/var/backups/rewind-display`. To roll back a configuration, stop LightDM,
restore the selected backup as `/home/opensurv/etc`, confirm the
`/etc/opensurv` symlink, and start LightDM again. Preserve the direct-management
fallback until the new appliance has passed its soak period.
