"""Smart configuration commands used by the Ride app's light settings."""

from .protocol import build_header, protobuf_bytes, protobuf_varint

SERVICE_BLE_LIGHT = 106
OP_SET = 1
SUBSERVICE_SMART_CONFIG = 4
CONFIG_AUTO_SLEEP = 4


def build_auto_sleep_frame(enabled: bool, timeout_seconds: int) -> bytes:
    """Encode the app's BLCS_AUTO_SLEEP setting and timeout slider value."""
    if not 30 <= timeout_seconds <= 1200 or timeout_seconds % 30:
        raise ValueError("sleep timeout must be 30–1200 seconds in 30-second steps")

    # blt_smt_cfg: config=1, status=2, user_data=3; user_data.data=1.
    user_data = protobuf_varint(1, timeout_seconds)
    smart_config = (
        protobuf_varint(1, CONFIG_AUTO_SLEEP)
        + protobuf_varint(2, int(enabled))
        + protobuf_bytes(3, user_data)
    )
    payload = (
        protobuf_varint(1, SERVICE_BLE_LIGHT)
        + protobuf_varint(2, OP_SET)
        + protobuf_varint(3, SUBSERVICE_SMART_CONFIG)
        # blt_message_format.cfg_set is protobuf field 10.
        + protobuf_bytes(10, smart_config)
    )
    return build_header(payload, service=SERVICE_BLE_LIGHT,
                        subtype=SUBSERVICE_SMART_CONFIG, operation=OP_SET)
