"""Brake Alert settings command used by the Ride app."""

from .protocol import build_header, protobuf_bytes, protobuf_varint

SERVICE_BLE_LIGHT = 106
OP_SET = 1
SUBSERVICE_RIDE_CONFIG = 9
CONFIG_BRAKE_LIGHT = 2
BRAKE_BRIGHTNESS_LEVELS = {"low": 0, "medium": 1, "high": 2}


def build_brake_alert_frame(
    enabled: bool,
    *,
    mode: str = "steady",
    brightness: str = "low",
    intensity: int = 50,
    pattern_index: int = 0,
) -> bytes:
    """Encode brake alert status and its app light settings."""
    try:
        brightness_level = BRAKE_BRIGHTNESS_LEVELS[brightness.lower()]
    except KeyError as exc:
        raise ValueError("brightness must be low, medium, or high") from exc
    if mode.lower() not in ("steady", "flash"):
        raise ValueError("mode must be steady or flash")
    if not 10 <= intensity <= 100:
        raise ValueError("braking brightness percentage must be between 10 and 100")
    if pattern_index < 0:
        raise ValueError("pattern index must be non-negative")

    # App mode is brake_cfg_msg.flash. Low/Medium/High is intensity_level.
    intensity_level = protobuf_varint(1, brightness_level)
    brake_config = (
        protobuf_varint(1, pattern_index)
        + protobuf_varint(2, int(mode.lower() == "flash"))
        + protobuf_varint(3, intensity)
        + protobuf_bytes(4, intensity_level)
    )
    # ride_cfg_msg: config=1 (BLCS_BRAKE_LIGHT=2), status=2, brake_cfg=3.
    ride_config = (
        protobuf_varint(1, CONFIG_BRAKE_LIGHT)
        + protobuf_varint(2, int(enabled))
        + protobuf_bytes(3, brake_config)
    )
    # blt_message_format.ride_cfg_set is field 17.
    payload = (
        protobuf_varint(1, SERVICE_BLE_LIGHT)
        + protobuf_varint(2, OP_SET)
        + protobuf_varint(3, SUBSERVICE_RIDE_CONFIG)
        + protobuf_bytes(17, ride_config)
    )
    return build_header(
        payload,
        service=SERVICE_BLE_LIGHT,
        subtype=SUBSERVICE_RIDE_CONFIG,
        operation=OP_SET,
    )
