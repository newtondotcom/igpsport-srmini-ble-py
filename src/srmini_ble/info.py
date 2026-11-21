"""Read and decode the SR Mini's public and app-level device information."""

from __future__ import annotations

import asyncio
from collections import defaultdict

from bleak import BleakClient
from bleak.exc import BleakError

from .client import UART_RX_UUID, UART_TX_UUID
from .protocol import build_header, crc8, protobuf_varint

INFO_SERVICE = 101
INFO_ALL = 31
GET = 2
LIGHT_SERVICE = 106
LIGHT_LEFT_TIME = 5

DEVICE_INFO_CHARS = {
    "manufacturer": "00002a29-0000-1000-8000-00805f9b34fb",
    "firmware": "00002a26-0000-1000-8000-00805f9b34fb",
    "hardware": "00002a27-0000-1000-8000-00805f9b34fb",
    "software": "00002a28-0000-1000-8000-00805f9b34fb",
    "serial": "00002a25-0000-1000-8000-00805f9b34fb",
    "battery": "00002a19-0000-1000-8000-00805f9b34fb",
    "clock": "00002a2b-0000-1000-8000-00805f9b34fb",
}


def _read_varint(data: bytes, offset: int) -> tuple[int, int]:
    result = shift = 0
    while offset < len(data):
        byte = data[offset]
        offset += 1
        result |= (byte & 0x7F) << shift
        if byte < 0x80:
            return result, offset
        shift += 7
        if shift >= 70:
            break
    raise ValueError("invalid/truncated protobuf varint")


def parse_fields(data: bytes) -> dict[int, list[int | bytes]]:
    """Parse protobuf wire types 0 and 2, which cover the info message."""
    fields: dict[int, list[int | bytes]] = defaultdict(list)
    offset = 0
    while offset < len(data):
        tag, offset = _read_varint(data, offset)
        number, wire = tag >> 3, tag & 7
        if not number:
            raise ValueError("invalid protobuf field number 0")
        if wire == 0:
            value, offset = _read_varint(data, offset)
        elif wire == 2:
            size, offset = _read_varint(data, offset)
            end = offset + size
            if end > len(data):
                raise ValueError("truncated protobuf bytes field")
            value = data[offset:end]
            offset = end
        elif wire == 1:
            end = offset + 8
            if end > len(data):
                raise ValueError("truncated protobuf fixed64 field")
            value = data[offset:end]
            offset = end
        elif wire == 5:
            end = offset + 4
            if end > len(data):
                raise ValueError("truncated protobuf fixed32 field")
            value = data[offset:end]
            offset = end
        else:
            raise ValueError(f"unsupported protobuf wire type {wire}")
        fields[number].append(value)
    return dict(fields)


def _one(fields: dict[int, list[int | bytes]], number: int):
    values = fields.get(number, [])
    return values[0] if values else None


def _text(value: int | bytes | None) -> str | None:
    if not isinstance(value, bytes):
        return None
    decoded = value.decode("utf-8", errors="replace").strip("\x00\x20")
    return decoded or None


def parse_info_payload(payload: bytes) -> dict[str, object]:
    """Decode PeripheralInfo.peripheral_info_format and its nested messages."""
    envelope = parse_fields(payload)
    message_bytes = _one(envelope, 5)
    if not isinstance(message_bytes, bytes):
        raise ValueError("info response has no message")
    message = parse_fields(message_bytes)

    result: dict[str, object] = {}
    for key, number in (("name", 2), ("version", 3), ("power", 16),
                        ("temperature", 17), ("memory", 18), ("id", 11)):
        nested_bytes = _one(message, number)
        if isinstance(nested_bytes, bytes):
            result[key] = parse_fields(nested_bytes)
    return result


def build_info_request() -> bytes:
    # PeripheralInfo format: service_type=1, operate_type=2,
    # sub_service_type=3 (PIS_ALL_INFO=31), no message body.
    payload = (protobuf_varint(1, INFO_SERVICE)
               + protobuf_varint(2, GET)
               + protobuf_varint(3, INFO_ALL))
    return build_header(payload, service=INFO_SERVICE, subtype=INFO_ALL,
                        operation=GET)


async def _read_standard_characteristics(client: BleakClient) -> dict[str, str | int]:
    values: dict[str, str | int] = {}
    for name, uuid in DEVICE_INFO_CHARS.items():
        try:
            raw = bytes(await client.read_gatt_char(uuid))
        except Exception:
            continue
        if name == "battery" and raw:
            values[name] = raw[0]
        elif name == "clock" and len(raw) >= 7:
            year = int.from_bytes(raw[0:2], "little")
            month, day, hour, minute, second = raw[2:7]
            values[name] = (f"{year:04d}-{month:02d}-{day:02d} "
                            f"{hour:02d}:{minute:02d}:{second:02d}")
        elif raw:
            value = raw.decode("utf-8", errors="replace").strip("\x00\r\n ")
            if value:
                values[name] = value
    return values


async def _read_response_payload(
    client: BleakClient,
    request: bytes,
    *,
    service: int,
    subtype: int,
    operation: int,
    timeout: float,
) -> bytes:
    packets: asyncio.Queue[bytes] = asyncio.Queue()

    def on_notification(_characteristic, data: bytearray) -> None:
        packets.put_nowait(bytes(data))

    await client.start_notify(UART_TX_UUID, on_notification)
    chunk_size = max(1, client.mtu_size - 3)
    for offset in range(0, len(request), chunk_size):
        await client.write_gatt_char(UART_RX_UUID,
                                     request[offset:offset + chunk_size],
                                     response=True)

    buffer = bytearray()
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        remaining = deadline - asyncio.get_running_loop().time()
        if remaining <= 0:
            raise TimeoutError("no SR Mini info response")
        buffer.extend(await asyncio.wait_for(packets.get(), remaining))

        while len(buffer) >= 20:
            # Skip unsolicited status packets and re-sync on the response
            # matching this service, subtype, and operation.
            if (buffer[0] not in (1, 2)
                    or buffer[1] != service
                    or buffer[2] != subtype
                    or buffer[4] != operation):
                if buffer[0] == 3 and len(buffer) >= 20:
                    del buffer[:20]
                else:
                    del buffer[0]
                continue
            if crc8(bytes(buffer[:19])) != buffer[19]:
                del buffer[0]
                continue
            size = int.from_bytes(buffer[7:9], "big")
            total = 20 + size
            if len(buffer) < total:
                break
            frame = bytes(buffer[:total])
            del buffer[:total]
            if crc8(frame[20:]) != frame[9]:
                continue
            await client.stop_notify(UART_TX_UUID)
            return frame[20:]


async def _read_app_info(client: BleakClient, timeout: float) -> dict[str, object]:
    payload = await _read_response_payload(
        client, build_info_request(), service=INFO_SERVICE, subtype=INFO_ALL,
        operation=GET, timeout=timeout,
    )
    return parse_info_payload(payload)


def build_remaining_runtime_request() -> bytes:
    # Ride app: PST_BLE_LIGHT/POT_GET/BLS_LEFT_TIME (service 106, subtype 5).
    payload = (protobuf_varint(1, LIGHT_SERVICE)
               + protobuf_varint(2, GET)
               + protobuf_varint(3, LIGHT_LEFT_TIME))
    return build_header(payload, service=LIGHT_SERVICE,
                        subtype=LIGHT_LEFT_TIME, operation=GET)


async def _read_remaining_runtime(client: BleakClient, timeout: float) -> int | None:
    payload = await _read_response_payload(
        client, build_remaining_runtime_request(), service=LIGHT_SERVICE,
        subtype=LIGHT_LEFT_TIME, operation=GET, timeout=timeout,
    )
    envelope = parse_fields(payload)
    left_time = _one(envelope, 14)
    if not isinstance(left_time, bytes):
        raise ValueError("SR Mini runtime response has no left_time field")
    minutes = _one(parse_fields(left_time), 1)
    if not isinstance(minutes, int):
        raise ValueError("SR Mini runtime response has no time value")
    # The app treats uint64 max as signed -1, meaning unavailable.
    return None if minutes == 0xFFFFFFFFFFFFFFFF else minutes


async def read_device_info(address: str, *, timeout: float = 5.0) -> dict[str, object]:
    """Read standard BLE fields, app info, and estimated remaining runtime."""
    async with BleakClient(address) as client:
        standard = await _read_standard_characteristics(client)
        try:
            app_info = await _read_app_info(client, timeout)
            app_error = None
        except (TimeoutError, ValueError, BleakError, OSError) as exc:
            app_info = {}
            app_error = str(exc)
            try:
                await client.stop_notify(UART_TX_UUID)
            except Exception:
                pass
        try:
            runtime_minutes = await _read_remaining_runtime(client, timeout)
            runtime_error = None
        except (TimeoutError, ValueError, BleakError, OSError) as exc:
            runtime_minutes = None
            runtime_error = str(exc)
    return {
        "standard": standard,
        "app": app_info,
        "app_error": app_error,
        "runtime_minutes": runtime_minutes,
        "runtime_error": runtime_error,
    }


def format_device_info(data: dict[str, object]) -> str:
    standard = data.get("standard", {})
    app = data.get("app", {})
    if not isinstance(standard, dict):
        standard = {}
    if not isinstance(app, dict):
        app = {}

    names = app.get("name", {})
    versions = app.get("version", {})
    power = app.get("power", {})
    temperature = app.get("temperature", {})
    memory = app.get("memory", {})
    for key, value in (("names", names), ("versions", versions), ("power", power),
                       ("temperature", temperature), ("memory", memory)):
        if not isinstance(value, dict):
            if key == "names": names = {}
            elif key == "versions": versions = {}
            elif key == "power": power = {}
            elif key == "temperature": temperature = {}
            else: memory = {}

    def get_text(name: str, fields: dict[int, list[int | bytes]], field: int) -> str:
        return str(standard.get(name) or _text(_one(fields, field)) or "not reported")

    manufacturer = get_text("manufacturer", names, 3)
    hardware = get_text("hardware", versions, 4)
    firmware = standard.get("firmware")
    if not firmware:
        fw_parts = []
        for label, number in (("MCU", 1), ("app", 2), ("boot", 3)):
            value = _one(versions, number)
            if isinstance(value, int):
                fw_parts.append(f"{label} {value}")
        firmware = ", ".join(fw_parts) if fw_parts else "not reported"
    serial = standard.get("serial", "not reported")
    battery_level = standard.get("battery")
    app_percent = _one(power, 2)
    if battery_level is None and isinstance(app_percent, int):
        battery_level = app_percent
    # voltage = _one(power, 1)
    # voltage_text = (f"{voltage} mV" if isinstance(voltage, int)
    #                 else "not reported")
    battery_text = (f"{battery_level}%" if isinstance(battery_level, int)
                    else "not reported")

    runtime_minutes = data.get("runtime_minutes")
    if isinstance(runtime_minutes, int):
        days, remainder = divmod(runtime_minutes, 1440)
        hours, minutes = divmod(remainder, 60)
        if days:
            runtime_text = f"{days}d" + (f"{hours}h" if hours else "")
        elif hours:
            runtime_text = f"{hours}h" + (f"{minutes}min" if minutes else "")
        else:
            runtime_text = f"{minutes}min"
    else:
        runtime_text = "not reported"

    output = [
        "🏷️ Device info",
        f"  Manufacturer: {manufacturer}",
        f"  Hardware revision: {hardware}",
        f"  Firmware: {firmware}",
        f"  Serial: {serial}",
        # "  Protocol version: not separately reported by the SR Mini info response",
        "🔋 Battery",
        f"  Level: {battery_text}",
        f"  Predicted runtime: {runtime_text}",
        # f"  Voltage: {voltage_text}",
        # "🌡️ Sensors",
    ]
    runtime_error = data.get("runtime_error")
    if runtime_error:
        output.append(f"  Runtime estimate unavailable: {runtime_error}")
    app_error = data.get("app_error")
    if app_error:
        output.append(f"  SR Mini protocol info unavailable: {app_error}")
    # temp = _one(temperature, 1)
    # output.append(f"  Internal temperature: {temp} (device units)"
    #               if isinstance(temp, int) else "  Internal temperature: not reported")
    # memory_labels = (("Free internal flash", 1), ("Free external flash", 3),
    #                  ("Free internal RAM", 5), ("Free external RAM", 7))
    # memory_lines = [f"  {label}: {_one(memory, field)} (device units)"
    #                 for label, field in memory_labels
    #                 if isinstance(_one(memory, field), int)]
    # output.extend(memory_lines or ["  Free memory: not reported"])
    # output.append(f"  Device clock: {standard.get('clock', 'not reported')}")
    return "\n".join(output)
