"""Async Bleak client for finding and sending commands to an SR Mini."""

from __future__ import annotations

import asyncio
from collections.abc import Callable

from bleak import BleakClient, BleakScanner

UART_SERVICE_UUID = "6e400001-b5a3-f393-e0a9-e50e24dcca9e"
UART_RX_UUID = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"
UART_TX_UUID = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"


async def discover(timeout: float = 8.0):
    """Discover nearby BLE devices; callers can filter the results."""
    return await BleakScanner.discover(timeout=timeout, return_adv=True)


async def find_srmini(timeout: float = 8.0):
    """Return (BLEDevice, AdvertisementData) pairs whose name looks like SR Mini."""
    found = await discover(timeout)
    matches = []
    for device, advertisement in found.values():
        name = advertisement.local_name or device.name or ""
        if "sr mini" in name.lower() or "srmini" in name.lower():
            matches.append((device, advertisement))
    return matches


async def send_frame(address: str, frame: bytes, *,
                     notification_callback: Callable[[bytes], None] | None = None,
                     listen_seconds: float = 0.5) -> None:
    """Connect, optionally listen for TX notifications, and write one frame."""
    def on_notification(_characteristic, data: bytearray) -> None:
        if notification_callback:
            notification_callback(bytes(data))

    async with BleakClient(address) as client:
        if notification_callback:
            await client.start_notify(UART_TX_UUID, on_notification)
        # The Android client writes this UART stream through Nordic's split
        # request, using the negotiated ATT payload size for each chunk.
        chunk_size = max(1, client.mtu_size - 3)
        for offset in range(0, len(frame), chunk_size):
            await client.write_gatt_char(
                UART_RX_UUID, frame[offset:offset + chunk_size], response=True
            )
        if notification_callback and listen_seconds > 0:
            await asyncio.sleep(listen_seconds)
