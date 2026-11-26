"""Command line interface for SR Mini light control."""

from __future__ import annotations

import argparse
import asyncio

from .client import find_srmini, send_frame, stream_radar
from .brake import build_brake_alert_frame
from .info import format_device_info, read_device_info
from .function_config import build_auto_sleep_frame
from .light import LightMode, build_set_mode_frame, parse_mode
from .radar import build_radar_switch_frame
from .sync import (
    CONFIG_SMART_LIGHT_SYNC,
    CONFIG_TEAM_SYNC,
    build_sync_switch_frame,
)


def _mode_listing() -> str:
    return "\n".join(f"{mode.value:>2}  {mode.name.lower()}" for mode in LightMode)


async def _run(args: argparse.Namespace) -> int:
    if args.command == "modes":
        print(_mode_listing())
        return 0

    if args.command == "info":
        address = args.address
        if not address:
            devices = await find_srmini(timeout=args.timeout)
            if not devices:
                print(
                    "No device named SR Mini found. Wake the light or pass --address."
                )
                return 1
            if len(devices) > 1:
                print("More than one SR Mini found; pass --address to choose one:")
                for device, advertisement in devices:
                    name = advertisement.local_name or device.name or "SR Mini"
                    print(f"  {name}  {device.address}")
                return 2
            address = devices[0][0].address
        info = await read_device_info(address, timeout=args.timeout)
        print(format_device_info(info))
        return 0

    if args.command == "scan":
        devices = await find_srmini(timeout=args.timeout)
        if not devices:
            print("No device named SR Mini found. Wake the light and scan again.")
            return 1
        for device, advertisement in devices:
            name = advertisement.local_name or device.name or "SR Mini"
            print(f"{name}  {device.address}  RSSI={advertisement.rssi}")
        return 0

    if args.command == "radar-stream":
        address = args.address
        if not address:
            devices = await find_srmini(timeout=args.timeout)
            if not devices:
                print("No device named SR Mini found. Wake the light or pass --address.")
                return 1
            if len(devices) > 1:
                print("More than one SR Mini found; pass --address to choose one:")
                for device, advertisement in devices:
                    name = advertisement.local_name or device.name or "SR Mini"
                    print(f"  {name}  {device.address}")
                return 2
            address = devices[0][0].address

        def show_targets(targets: list[dict[int, int]]) -> None:
            if not targets:
                print("Radar update: no targets")
                return
            for index, target in enumerate(targets, start=1):
                values = "  ".join(
                    f"{name}={target[field]}"
                    for field, name in ((6, "level"), (7, "range"), (8, "speed"))
                    if field in target
                )
                print(f"Target {index}: {values or '(empty target)'}")

        print(f"Streaming radar detections from {address}; press Ctrl+C to stop.")
        try:
            await stream_radar(address, show_targets)
        except asyncio.CancelledError:
            print("Radar stream stopped; broadcast disabled.")
        except KeyboardInterrupt:
            print("Radar stream stopped; broadcast disabled.")
        return 0

    if args.command in ("manufacture-data", "manufacturer-data"):
        devices = await find_srmini(timeout=args.timeout)
        if args.address:
            devices = [
                (device, advertisement)
                for device, advertisement in devices
                if device.address.lower() == args.address.lower()
            ]
        if not devices:
            print("No matching SR Mini found. Wake the light and scan again.")
            return 1
        if len(devices) > 1:
            print("More than one SR Mini found; pass --address to choose one:")
            for device, advertisement in devices:
                name = advertisement.local_name or device.name or "SR Mini"
                print(f"  {name}  {device.address}")
            return 2
        device, advertisement = devices[0]
        name = advertisement.local_name or device.name or "SR Mini"
        if not advertisement.manufacturer_data:
            print(f"No manufacturer-specific data found for {name} ({device.address}).")
            return 1
        company_id, payload = next(iter(advertisement.manufacturer_data.items()))
        # The Ride app sends only the manufacturer payload, as lowercase hex
        # bytes separated by underscores; the company ID is not included.
        print(f"{name}  {device.address}")
        print(f"manufactureData: {bytes(payload).hex('_')}")
        print(f"Company ID: 0x{company_id:04x}")
        return 0

    if args.command in (
        "radar",
        "radar-alert",
        "auto-sleep",
        "brake-alert",
        "smart-light-sync",
        "team-sync",
    ):
        if args.command == "auto-sleep":
            if args.action == "timeout":
                if args.value is None:
                    print("Provide the timeout in seconds: auto-sleep timeout 300")
                    return 2
                enabled = args.enabled == "on"
                try:
                    timeout_seconds = int(args.value)
                    frame = build_auto_sleep_frame(enabled, timeout_seconds)
                except ValueError as exc:
                    print(exc)
                    return 2
                feature = "Auto Sleep timeout"
                state = f"{timeout_seconds}s (Auto Sleep {'on' if enabled else 'off'})"
            else:
                if args.value is not None:
                    print("Only the timeout action takes a value.")
                    return 2
                enabled = args.action == "on"
                timeout_seconds = args.timeout_seconds
                try:
                    frame = build_auto_sleep_frame(enabled, timeout_seconds)
                except ValueError as exc:
                    print(exc)
                    return 2
                feature = "Auto Sleep"
                state = "on" if enabled else "off"
        elif args.command in ("smart-light-sync", "team-sync"):
            enabled = args.action == "on"
            config = (
                CONFIG_SMART_LIGHT_SYNC
                if args.command == "smart-light-sync"
                else CONFIG_TEAM_SYNC
            )
            feature = (
                "Smart Light Sync"
                if args.command == "smart-light-sync"
                else "Team Sync"
            )
            frame = build_sync_switch_frame(config, enabled)
            state = "on" if enabled else "off"
        elif args.command == "brake-alert":
            enabled = args.action == "on"
            try:
                frame = build_brake_alert_frame(
                    enabled,
                    mode=args.mode,
                    brightness=args.brightness,
                    intensity=args.intensity,
                    pattern_index=args.pattern_index,
                )
            except ValueError as exc:
                print(exc)
                return 2
            feature = "Brake Alert"
            state = "on" if enabled else "off"
        else:
            enabled = args.action == "on"
            alert = args.command == "radar-alert"
            feature = "Radar Alert" if alert else "Radar"
            frame = build_radar_switch_frame(enabled, alert=alert)
            state = "on" if enabled else "off"
        address = args.address
        if not address:
            devices = await find_srmini(timeout=args.timeout)
            if not devices:
                print(
                    "No device named SR Mini found. Wake the light or pass --address."
                )
                return 1
            if len(devices) > 1:
                print("More than one SR Mini found; pass --address to choose one:")
                for device, advertisement in devices:
                    name = advertisement.local_name or device.name or "SR Mini"
                    print(f"  {name}  {device.address}")
                return 2
            address = devices[0][0].address

        def show_notification(data: bytes) -> None:
            print(f"Notification: {data.hex(' ')}")

        status = await send_frame(
            address,
            frame,
            notification_callback=show_notification,
            expected_reply=(106, 9 if args.command == "brake-alert" else 4, 1),
        )
        if status is None:
            print(f"No {feature.lower()} reply received; {state} is unconfirmed.")
            return 1
        if status != 0:
            print(
                f"SR Mini rejected {feature.lower()} setting {state} (status {status})."
            )
            return 1
        print(f"SR Mini acknowledged {feature.lower()} setting {state}.")
        return 0

    try:
        mode = parse_mode(args.mode)
    except (ValueError, KeyError) as exc:
        print(exc)
        return 2
    frame = build_set_mode_frame(mode)
    if args.dry_run:
        print(f"Mode: {mode.value} ({mode.name.lower()})")
        print(f"Frame ({len(frame)} bytes): {frame.hex(' ')}")
        return 0
    address = args.address
    if not address:
        devices = await find_srmini(timeout=args.timeout)
        if not devices:
            print("No device named SR Mini found. Wake the light or pass --address.")
            return 1
        if len(devices) > 1:
            print("More than one SR Mini found; pass --address to choose one:")
            for device, advertisement in devices:
                name = advertisement.local_name or device.name or "SR Mini"
                print(f"  {name}  {device.address}")
            return 2
        address = devices[0][0].address

    def show_notification(data: bytes) -> None:
        print(f"Notification: {data.hex(' ')}")

    await send_frame(address, frame, notification_callback=show_notification)
    print(f"Sent mode {mode.value} ({mode.name.lower()}) to {address}.")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="srmini", description="Control iGPSPORT SR Mini light modes over BLE"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan = subparsers.add_parser("scan", help="find nearby SR Mini devices")
    scan.add_argument("--timeout", type=float, default=8.0)

    manufacturer_data = subparsers.add_parser(
        "manufacture-data",
        aliases=("manufacturer-data",),
        help="read the SR Mini BLE advertising manufacturer data",
    )
    manufacturer_data.add_argument(
        "--address", help="BLE address/identifier; otherwise scan for SR Mini"
    )
    manufacturer_data.add_argument("--timeout", type=float, default=8.0)

    subparsers.add_parser("modes", help="list the mode IDs found in the app")

    info = subparsers.add_parser(
        "info", help="read SR Mini device, battery, and sensor info"
    )
    info.add_argument(
        "--address", help="BLE address/identifier; otherwise scan for SR Mini"
    )
    info.add_argument(
        "--timeout",
        type=float,
        default=5.0,
        help="seconds to wait for the app-protocol info response",
    )
    radar = subparsers.add_parser(
        "radar", help="enable or disable the SR Mini radar feature"
    )
    radar.add_argument(
        "action", choices=("on", "off"), help="turn the radar feature on or off"
    )
    radar.add_argument(
        "--address", help="BLE address/identifier; otherwise scan for SR Mini"
    )
    radar.add_argument("--timeout", type=float, default=8.0)

    radar_stream = subparsers.add_parser(
        "radar-stream", help="stream and decode live SR Mini radar detections"
    )
    radar_stream.add_argument(
        "--address", help="BLE address/identifier; otherwise scan for SR Mini"
    )
    radar_stream.add_argument("--timeout", type=float, default=8.0)

    radar_alert = subparsers.add_parser(
        "radar-alert", help="enable or disable the SR Mini Radar Alert feature"
    )
    radar_alert.add_argument(
        "action", choices=("on", "off"), help="turn Radar Alert on or off"
    )
    radar_alert.add_argument(
        "--address", help="BLE address/identifier; otherwise scan for SR Mini"
    )
    radar_alert.add_argument("--timeout", type=float, default=8.0)

    auto_sleep = subparsers.add_parser(
        "auto-sleep", help="configure SR Mini Auto Sleep and its timeout"
    )
    auto_sleep.add_argument("action", choices=("on", "off", "timeout"))
    auto_sleep.add_argument(
        "value", nargs="?", help="timeout in seconds when action is 'timeout'"
    )
    auto_sleep.add_argument(
        "--enabled",
        choices=("on", "off"),
        default="on",
        help="Auto Sleep state when setting a timeout (default: on)",
    )
    auto_sleep.add_argument(
        "--timeout-seconds",
        type=int,
        default=30,
        help="timeout to retain when turning Auto Sleep on or off (default: 30)",
    )
    auto_sleep.add_argument(
        "--address", help="BLE address/identifier; otherwise scan for SR Mini"
    )
    auto_sleep.add_argument(
        "--timeout", type=float, default=8.0, help="BLE scan timeout in seconds"
    )

    brake_alert = subparsers.add_parser(
        "brake-alert", help="configure and enable or disable SR Mini Brake Alert"
    )
    brake_alert.add_argument("action", choices=("on", "off"))
    brake_alert.add_argument(
        "--mode",
        choices=("steady", "flash"),
        default="steady",
        help="brake alert mode (default: steady)",
    )
    brake_alert.add_argument(
        "--brightness",
        choices=("low", "medium", "high"),
        default="low",
        help="brake brightness level (default: low)",
    )
    brake_alert.add_argument(
        "--intensity",
        type=int,
        default=50,
        help="separate braking brightness slider, 10–100 percent (default: 50)",
    )
    brake_alert.add_argument(
        "--pattern-index",
        type=int,
        default=0,
        help="device brake pattern index (default: 0)",
    )
    brake_alert.add_argument(
        "--address", help="BLE address/identifier; otherwise scan for SR Mini"
    )
    brake_alert.add_argument(
        "--timeout", type=float, default=8.0, help="BLE scan timeout in seconds"
    )

    smart_light_sync = subparsers.add_parser(
        "smart-light-sync", help="enable or disable Smart Light Sync"
    )
    smart_light_sync.add_argument("action", choices=("on", "off"))
    smart_light_sync.add_argument(
        "--address", help="BLE address/identifier; otherwise scan for SR Mini"
    )
    smart_light_sync.add_argument(
        "--timeout", type=float, default=8.0, help="BLE scan timeout in seconds"
    )

    team_sync = subparsers.add_parser("team-sync", help="enable or disable Team Sync")
    team_sync.add_argument("action", choices=("on", "off"))
    team_sync.add_argument(
        "--address", help="BLE address/identifier; otherwise scan for SR Mini"
    )
    team_sync.add_argument(
        "--timeout", type=float, default=8.0, help="BLE scan timeout in seconds"
    )

    set_mode = subparsers.add_parser("set-mode", help="send a light mode to an SR Mini")
    set_mode.add_argument(
        "mode", help="mode ID or name; run 'srmini modes' to list them"
    )
    set_mode.add_argument(
        "--address", help="BLE address/identifier; otherwise scan for SR Mini"
    )
    set_mode.add_argument("--timeout", type=float, default=8.0)
    set_mode.add_argument(
        "--dry-run",
        action="store_true",
        help="print the encoded frame without connecting",
    )

    args = parser.parse_args()
    raise SystemExit(asyncio.run(_run(args)))


if __name__ == "__main__":
    main()
