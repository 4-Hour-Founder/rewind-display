#!/usr/bin/env python3
"""Validate a Rewind Display monitor config without printing stream URLs."""

from __future__ import annotations

import argparse
import shlex
import sys
from pathlib import Path
from urllib.parse import urlparse

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML is required (Debian package: python3-yaml)", file=sys.stderr)
    raise SystemExit(2)


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def require_mapping(value: object, label: str) -> dict:
    if not isinstance(value, dict):
        fail(f"{label} must be a mapping")
    return value


def require_list(value: object, label: str) -> list:
    if not isinstance(value, list):
        fail(f"{label} must be a list")
    return value


def validate_six_camera(config: dict) -> None:
    essentials = require_mapping(config.get("essentials"), "essentials")
    screens = require_list(essentials.get("screens"), "essentials.screens")
    if len(screens) != 1:
        fail("six-camera profile requires exactly one screen")

    screen = require_mapping(screens[0], "screen 1")
    if screen.get("duration") != 0:
        fail("six-camera screen duration must be 0 (no rotation)")
    if screen.get("nr_of_columns") != 3:
        fail("six-camera screen must use exactly three columns")
    if screen.get("rotate90", False):
        fail("six-camera profile does not support display rotation")

    streams = require_list(screen.get("streams"), "screen 1 streams")
    if len(streams) != 6:
        fail(f"six-camera profile requires 6 streams; found {len(streams)}")

    for index, raw_stream in enumerate(streams, start=1):
        stream = require_mapping(raw_stream, f"stream {index}")
        url = stream.get("url")
        if not isinstance(url, str) or not url:
            fail(f"stream {index} must have a non-empty URL")
        parsed = urlparse(url)
        if parsed.scheme != "rtsp" or not parsed.hostname:
            fail(f"stream {index} must use an RTSP URL with a hostname")
        if parsed.username is not None or parsed.password is not None:
            fail(f"stream {index} contains embedded credentials")
        try:
            port = parsed.port
        except ValueError:
            fail(f"stream {index} has an invalid RTSP port")
        if port != 8554:
            fail(f"stream {index} must use the go2rtc RTSP port 8554")
        if not parsed.path or parsed.path == "/":
            fail(f"stream {index} must name a go2rtc stream")

        label = stream.get("name")
        if not isinstance(label, str) or not label.strip():
            fail(f"stream {index} must have a display label")
        if stream.get("probe_timeout") != 10:
            fail(f"stream {index} probe_timeout must be 10")
        if stream.get("timeout_waiting_for_init_stream") != 12:
            fail(f"stream {index} timeout_waiting_for_init_stream must be 12")
        if stream.get("force_coordinates", False):
            fail(f"stream {index} must use automatic layout, not force_coordinates")
        if stream.get("enableaudio", False):
            fail(f"stream {index} must not enable audio on a public display")

        options = stream.get("freeform_advanced_mpv_options", "")
        if "--rtsp-transport=tcp" not in options:
            fail(f"stream {index} must force RTSP over TCP")
        if "--profile=low-latency" not in options:
            fail(f"stream {index} must use the low-latency MPV profile")


def validate_integrated_four_camera(config: dict) -> None:
    essentials = require_mapping(config.get("essentials"), "essentials")
    screens = require_list(essentials.get("screens"), "essentials.screens")
    if len(screens) != 1:
        fail("integrated four-camera profile requires exactly one screen")

    screen = require_mapping(screens[0], "screen 1")
    if screen.get("duration") != 0:
        fail("integrated four-camera screen duration must be 0 (no rotation)")
    if screen.get("nr_of_columns") != 2:
        fail("integrated four-camera screen must use exactly two columns")
    if screen.get("rotate90", False):
        fail("integrated four-camera profile does not support display rotation")

    streams = require_list(screen.get("streams"), "screen 1 streams")
    if len(streams) != 4:
        fail(
            "integrated four-camera profile requires 4 streams; "
            f"found {len(streams)}"
        )

    for index, raw_stream in enumerate(streams, start=1):
        stream = require_mapping(raw_stream, f"stream {index}")
        url = stream.get("url")
        if not isinstance(url, str) or not url:
            fail(f"stream {index} must have a non-empty URL")
        parsed = urlparse(url)
        if parsed.scheme != "rtsp" or not parsed.hostname:
            fail(f"stream {index} must use a direct RTSP URL with a hostname")
        try:
            parsed.port
        except ValueError:
            fail(f"stream {index} has an invalid RTSP port")
        if not parsed.path or parsed.path == "/":
            fail(f"stream {index} must name a camera RTSP path")
        if parsed.fragment:
            fail(f"stream {index} must not retain a go2rtc source fragment")

        label = stream.get("name")
        if not isinstance(label, str) or not label.strip():
            fail(f"stream {index} must have a display label")
        if stream.get("probe_timeout") != 10:
            fail(f"stream {index} probe_timeout must be 10")
        if stream.get("timeout_waiting_for_init_stream") != 12:
            fail(f"stream {index} timeout_waiting_for_init_stream must be 12")
        if stream.get("force_coordinates", False):
            fail(f"stream {index} must use automatic layout, not force_coordinates")
        if stream.get("enableaudio", False):
            fail(f"stream {index} must not enable audio on a public display")

        options = stream.get("freeform_advanced_mpv_options", "")
        if not isinstance(options, str):
            fail(f"stream {index} MPV options must be a string")
        try:
            option_tokens = shlex.split(options)
        except ValueError:
            fail(f"stream {index} has invalid MPV option quoting")
        required = {
            "--rtsp-transport=tcp",
            "--profile=low-latency",
            "--hwdec=auto",
            "--no-terminal",
        }
        missing = required.difference(option_tokens)
        if missing:
            fail(
                f"stream {index} is missing required MPV options: "
                + ", ".join(sorted(missing))
            )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("config", type=Path)
    parser.add_argument(
        "--profile",
        choices=("six-camera", "integrated-four-camera"),
        default="six-camera",
    )
    args = parser.parse_args()

    try:
        loaded = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    except OSError as error:
        fail(f"cannot read config: {error}")
    except yaml.YAMLError as error:
        mark = getattr(error, "problem_mark", None)
        if mark is None:
            fail("invalid YAML")
        fail(f"invalid YAML at line {mark.line + 1}, column {mark.column + 1}")

    config = require_mapping(loaded, "document root")
    if args.profile == "six-camera":
        validate_six_camera(config)
        result = "six-camera monitor config is structurally valid and credential-free"
    else:
        validate_integrated_four_camera(config)
        result = (
            "integrated four-camera monitor config is structurally valid; "
            "protect the credential-bearing file as mode 0600"
        )

    print(f"OK: {result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
