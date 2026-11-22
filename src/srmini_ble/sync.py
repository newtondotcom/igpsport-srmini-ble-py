"""Smart configuration switches for Ride's intelligent light settings."""

from .protocol import build_header, protobuf_bytes, protobuf_varint

SERVICE_BLE_LIGHT = 106
OP_SET = 1
SUBSERVICE_SMART_CONFIG = 4
CONFIG_SMART_LIGHT_SYNC = 5  # BLCS_SYNC_OFF in the app's enum.
CONFIG_TEAM_SYNC = 6  # BLCS_TEAM_RIDE.


def build_sync_switch_frame(config: int, enabled: bool) -> bytes:
    """Encode a status-only smart config setting."""
    smart_config = protobuf_varint(1, config)
    if enabled:
        smart_config += protobuf_varint(2, 1)
    payload = (
        protobuf_varint(1, SERVICE_BLE_LIGHT)
        + protobuf_varint(2, OP_SET)
        + protobuf_varint(3, SUBSERVICE_SMART_CONFIG)
        + protobuf_bytes(10, smart_config)
    )
    return build_header(
        payload,
        service=SERVICE_BLE_LIGHT,
        subtype=SUBSERVICE_SMART_CONFIG,
        operation=OP_SET,
    )
