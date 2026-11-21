"""SR Mini light commands and mode identifiers."""

from enum import IntEnum

from .protocol import (
    OP_SET,
    SERVICE_BLE_LIGHT,
    SUBSERVICE_CURRENT_MODE,
    build_header,
    protobuf_bytes,
    protobuf_varint,
)


class LightMode(IntEnum):
    OFF = 0
    HIGH_ALWAYS = 1
    MID_ALWAYS = 2
    LOW_ALWAYS = 3
    HIGH_BLINK = 4
    LOW_BLINK = 5
    GRADIENT = 6
    HIGH_LEVEL_1 = 7
    HIGH_LEVEL_2 = 8
    HIGH_LEVEL_3 = 9
    LOW_LEVEL_1 = 10
    LOW_LEVEL_2 = 11
    LOW_LEVEL_3 = 12
    ROTATION = 13
    LEFT_TURN = 14
    RIGHT_TURN = 15
    SUPERHIGH = 16
    SOS = 17
    COMET = 18
    WATERFALL = 19
    PINWHEEL = 20


def parse_mode(value: str | int) -> LightMode:
    """Accept a numeric mode ID or a case-insensitive enum name."""
    if isinstance(value, int) or value.isdecimal():
        return LightMode(int(value))
    normalized = value.strip().upper().replace("-", "_").replace(" ", "_")
    try:
        return LightMode[normalized]
    except KeyError as exc:
        raise ValueError(f"unknown mode {value!r}; use a mode ID or one of: "
                         + ", ".join(mode.name.lower() for mode in LightMode)) from exc


def build_set_mode_frame(mode: LightMode | int) -> bytes:
    """Encode switchLightMode: top-level field 13, nested mode field 1."""
    selected = LightMode(mode)
    nested_current_mode = protobuf_varint(1, int(selected))
    body = (
        protobuf_varint(1, SERVICE_BLE_LIGHT)
        + protobuf_varint(2, OP_SET)
        + protobuf_varint(3, SUBSERVICE_CURRENT_MODE)
        + protobuf_bytes(13, nested_current_mode)
    )
    return build_header(body, service=SERVICE_BLE_LIGHT,
                        subtype=SUBSERVICE_CURRENT_MODE, operation=OP_SET)
