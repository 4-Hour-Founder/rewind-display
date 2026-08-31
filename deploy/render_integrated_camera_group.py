#!/usr/bin/env python3
"""Render a protected Rewind Display config from a Frigate camera group."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlencode
from urllib.parse import urlsplit, urlunsplit


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def yaml_string(value: str) -> str:
    # JSON strings are valid YAML scalars and correctly escape credentials.
    return json.dumps(value, ensure_ascii=False)


def load_config(path: str) -> dict:
    try:
        if path == "-":
            loaded = json.load(sys.stdin)
        else:
            loaded = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        fail(f"cannot read Frigate JSON config: {error}")
    if not isinstance(loaded, dict):
        fail("Frigate config root must be an object")
    return loaded


def select_direct_substream(config: dict, camera: str) -> str:
    streams = ((config.get("go2rtc") or {}).get("streams") or {})
    sources = streams.get(f"{camera}_sub")
    if isinstance(sources, str):
        sources = [sources]
    if not isinstance(sources, list):
        fail(f"camera {camera} has no go2rtc substream source")

    direct_sources = []
    for source in sources:
        if not isinstance(source, str):
            continue
        parsed = urlsplit(source)
        if parsed.scheme == "rtsp" and parsed.hostname and parsed.path:
            direct_sources.append(urlunsplit(parsed._replace(fragment="")))
    if len(direct_sources) != 1:
        fail(
            f"camera {camera} must have exactly one direct RTSP substream source; "
            f"found {len(direct_sources)}"
        )
    return direct_sources[0]


def render_group(
    config: dict,
    group_name: str,
    restream_cameras: set[str] | None = None,
    diagnostic_log_cameras: set[str] | None = None,
) -> tuple[str, list[str]]:
    groups = config.get("camera_groups") or {}
    group = groups.get(group_name)
    if not isinstance(group, dict):
        fail(f"camera group {group_name!r} does not exist")
    cameras = group.get("cameras")
    if not isinstance(cameras, list) or len(cameras) != 4:
        count = len(cameras) if isinstance(cameras, list) else 0
        fail(f"camera group {group_name!r} must contain exactly 4 cameras; found {count}")
    if len(set(cameras)) != 4 or not all(isinstance(name, str) for name in cameras):
        fail(f"camera group {group_name!r} contains invalid or duplicate camera names")
    restream_cameras = restream_cameras or set()
    diagnostic_log_cameras = diagnostic_log_cameras or set()
    unknown_restreams = restream_cameras.difference(cameras)
    if unknown_restreams:
        fail(
            "restream cameras are not members of the selected group: "
            + ", ".join(sorted(unknown_restreams))
        )
    invalid_diagnostic_cameras = diagnostic_log_cameras.difference(
        restream_cameras
    )
    if invalid_diagnostic_cameras:
        fail(
            "diagnostic logs are allowed only for credential-free loopback "
            "restream cameras: "
            + ", ".join(sorted(invalid_diagnostic_cameras))
        )

    lines = [
        "essentials:",
        "  screens:",
        "    - duration: 0",
        "      nr_of_columns: 2",
        "      streams:",
    ]
    direct_options = (
        "--rtsp-transport=tcp --profile=low-latency "
        "--hwdec=auto-copy --no-terminal"
    )
    restream_options = (
        "--profile=low-latency --hwdec=auto-copy --no-terminal "
        "--vo=gpu --gpu-context=x11egl"
    )
    for index, camera in enumerate(cameras, start=1):
        if camera in restream_cameras:
            source_url = "http://127.0.0.1:1984/api/stream.mp4?" + urlencode(
                {"src": f"{camera}_sub"}
            )
            options = restream_options
            if camera in diagnostic_log_cameras:
                options += (
                    " --log-file="
                    f"/home/opensurv/logs/mpv-loopback-{index}.log"
                )
        else:
            source_url = select_direct_substream(config, camera)
            options = direct_options
        label = camera.replace("_", " ").title()
        lines.extend(
            [
                f"        - url: {yaml_string(source_url)}",
                f"          name: {yaml_string(label)}",
                "          probe_timeout: 10",
                "          timeout_waiting_for_init_stream: 12",
                f"          freeform_advanced_mpv_options: {yaml_string(options)}",
            ]
        )
    return "\n".join(lines) + "\n", cameras


def write_protected(path: Path, content: str, force: bool) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    if not force:
        flags |= os.O_EXCL
    try:
        descriptor = os.open(path, flags, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
        path.chmod(0o600)
    except FileExistsError:
        fail(f"output already exists: {path}; pass --force to replace it")
    except OSError as error:
        fail(f"cannot write protected output: {error}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="-", help="Frigate API JSON file or -")
    parser.add_argument("--group", default="display")
    parser.add_argument(
        "--restream-camera",
        action="append",
        default=[],
        help="group camera that must use the loopback go2rtc MP4 endpoint",
    )
    parser.add_argument(
        "--diagnostic-log-camera",
        action="append",
        default=[],
        help=(
            "credential-free loopback camera whose MPV output should be "
            "written to a per-slot diagnostic log"
        ),
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    config = load_config(args.config)
    rendered, cameras = render_group(
        config,
        args.group,
        restream_cameras=set(args.restream_camera),
        diagnostic_log_cameras=set(args.diagnostic_log_camera),
    )
    write_protected(args.output, rendered, args.force)
    print(
        f"OK: rendered group {args.group!r} with {len(cameras)} cameras: "
        + ", ".join(cameras)
    )
    if args.restream_camera:
        print("Loopback restream cameras: " + ", ".join(args.restream_camera))
    if args.diagnostic_log_camera:
        print(
            "MPV diagnostic logs enabled for loopback cameras: "
            + ", ".join(args.diagnostic_log_camera)
        )
    print(f"Output is mode 0600: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
