# Headless Raspberry Pi bootstrap

This is the starting point for a new Retail Rewind public-display appliance.
The Pi does not need a desktop image, keyboard, mouse, or local setup wizard.
Raspberry Pi Imager prepares the boot media and SSH access; the versioned
Rewind Display installer adds the graphical display runtime later.

## Before writing the boot media

Have these inputs ready:

- a supported Raspberry Pi, preferably a Raspberry Pi 5;
- a suitable power supply, boot media, monitor, and HDMI cable;
- wired Ethernet where possible;
- a unique fleet device ID and hostname such as `rr-display-<site>`;
- the operator's SSH public key; and
- a unique recovery password stored in the approved password manager.

Writing boot media erases it. Confirm the exact removable drive before
continuing. Do not reimage an existing fleet device as part of an upgrade.

## Write Raspberry Pi OS Lite

Use the current [Raspberry Pi Imager](https://www.raspberrypi.com/software/)
and select the current 64-bit Raspberry Pi OS Lite image offered for the
hardware. In Imager customisation:

1. Set the unique hostname, locale, keyboard layout, and time zone.
2. Create the `rradmin` operator account unless the Fleet Registry defines a
   different identity for this device.
3. Configure Wi-Fi only when wired Ethernet is unavailable.
4. Enable SSH under Remote Access and choose public-key authentication.
5. Add the operator's public key and write the image to the verified device.

Raspberry Pi's official [getting-started guide](https://www.raspberrypi.com/documentation/computers/getting-started.html)
documents the Lite image, OS customisation, and SSH settings. Its
[remote-access guide](https://www.raspberrypi.com/documentation/computers/remote-access.html)
documents key-based SSH provisioning through Imager.

## First boot and trusted access

1. Insert the boot media and connect Ethernet, HDMI, and power.
2. Find the Pi by its reserved DHCP address or trusted local hostname.
3. Confirm the device identity on the expected LAN before accepting its SSH
   host key. Record the resulting host-key fingerprint in the Fleet Registry.
4. Connect with `ssh rradmin@<hostname>.local` or the reserved LAN address.

Run the read-only preflight from a trusted checkout:

```sh
ssh rradmin@<hostname>.local 'bash -s' \
  < deploy/preflight_display_host.sh
```

The preflight reports every fact it can obtain and exits successfully even
when optional services are absent. A fresh Lite host is expected to report no
LightDM, display profile, monitor config, or cloudflared service yet.

## Fresh-host acceptance

Before appliance installation, confirm:

- the hostname and physical device match the intended Fleet Registry entry;
- the OS is current Raspberry Pi OS Lite 64-bit on `arm64`;
- time, storage, memory, and temperature are reasonable;
- SSH is active and the operator key works in a second session; and
- the site, NVR, six approved H.264 go2rtc substreams, and display order are
  known.

Then continue with the [six-camera appliance runbook](six-camera-appliance.md).
That installer adds the minimal graphical runtime, Rewind Display, and the
host-level cloudflared package. It does not enable a tunnel before Cloudflare
Access protection exists and does not restart the visible session unless
explicitly requested.
