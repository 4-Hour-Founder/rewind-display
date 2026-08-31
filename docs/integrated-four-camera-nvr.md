# Integrated four-camera NVR display

This profile replaces an unreliable Chromium kiosk with Rewind Display on the
same Debian AMD64 host that runs Retail Rewind NVR. It renders one existing
four-camera Frigate group as a fixed 2x2 display.

The integrated profile differs from a separate display appliance:

- it uses the four cameras' direct RTSP substreams rather than looping through
  the local Frigate/go2rtc container;
- it explicitly enables MPV's safe automatic hardware decoding;
- it reuses the NVR's existing host-level Cloudflare identity; and
- it preserves the old Chromium kiosk files as rollback material.

Direct camera credentials remain on the NVR. Never copy the generated monitor
file off the box, print it, commit it, or inspect MPV command lines in status
output.

## Discover and render the group

Confirm the intended group contains exactly four cameras, then render the
credential-bearing config directly on the NVR:

```sh
curl -fsS http://127.0.0.1:5000/api/config \
  | python3 deploy/render_integrated_camera_group.py \
      --group display \
      --output /tmp/retail-rewind-display-monitor1.yml
```

The renderer selects each camera's single direct `*_sub` RTSP source, removes
go2rtc-only URL fragments, preserves group order, writes mode `0600`, and
prints only camera identifiers. It refuses ambiguous direct sources.

If a camera demonstrably cannot serve a second direct RTSP consumer while
Frigate/go2rtc holds its working session, route only that camera through the
already-published loopback MP4 endpoint:

```sh
curl -fsS http://127.0.0.1:5000/api/config \
  | python3 deploy/render_integrated_camera_group.py \
      --group display \
      --restream-camera <camera_id> \
      --output /tmp/retail-rewind-display-monitor1.yml
```

This exception does not publish another port or add another camera connection.
The validator permits only `127.0.0.1:1984/api/stream.mp4` with a named
`*_sub` source; arbitrary HTTP streams remain invalid.

Validate without printing URLs:

```sh
python3 deploy/validate_monitor_config.py \
  --profile integrated-four-camera \
  /tmp/retail-rewind-display-monitor1.yml
```

## Stage without interruption

```sh
sudo deploy/install_display_appliance.sh \
  --profile integrated-four-camera \
  --monitor-config /tmp/retail-rewind-display-monitor1.yml
```

The installer installs the display runtime but does not restart LightDM unless
`--start` is supplied. It backs up existing LightDM configuration and the
Retail Rewind Chromium launcher beneath `/var/backups/rewind-display`, leaves
the original kiosk files in place, grants the runtime user access to the host's
`video` and `render` devices, and does not modify cloudflared.

## Cut over

During an approved display interruption:

```sh
sudo systemctl restart lightdm
```

Do not run Chromium and Rewind Display concurrently. Validate with commands
that cannot disclose RTSP credentials:

```sh
systemctl is-active lightdm cloudflared
pgrep -cx mpv
curl -fsS http://127.0.0.1:5000/api/stats > /tmp/frigate-stats.json
```

Confirm four MPV processes remain stable, all four views are visible in group
order, Frigate cameras and recording remain healthy, and CPU temperature does
not regress. MPV hardware decoding uses `--hwdec=auto-copy`, which selects a
safe hardware decoder while copying decoded frames back to system memory for
reliable compatibility with the X11 multi-window layout. It falls back to
software decoding if no safe hardware path is available.

## Chromium rollback

The original `50-retailrewind-kiosk.conf` and Chromium launcher remain on the
host. To select the old kiosk again without deleting the Rewind Display file:

```sh
sudo mv /etc/lightdm/lightdm.conf.d/50-rewind-display.conf \
  /etc/lightdm/lightdm.conf.d/50-rewind-display.conf.disabled
sudo systemctl restart lightdm
```

To retry Rewind Display, move the file back and restart LightDM. The precise
pre-install backup path is recorded in
`/etc/retailrewind/display-appliance.env`.
