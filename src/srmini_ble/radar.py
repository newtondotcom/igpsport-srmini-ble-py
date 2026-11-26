"""Radar feature and detection stream protocol helpers."""

from .protocol import build_header, protobuf_bytes, protobuf_varint

SERVICE_BLE_LIGHT = 106
OP_SET = 1
SUBSERVICE_SMART_CONFIG = 4
CONFIG_RADAR = 7
CONFIG_RADAR_WARN = 21
STATUS_ON = 1
SERVICE_CONFIG = 102
SUBSERVICE_DATA_BROADCAST = 7
SERVICE_RADAR = 104
OP_RADAR_TARGET = 1


def build_radar_switch_frame(enabled: bool, *, alert: bool = False) -> bytes:
    """Encode the app's radar or Radar Alert smart configuration."""
    # setRadarSwitch uses BLCS_RADAR; setRadarWarnSwitch uses BLCS_RADAR_WARN.
    config = CONFIG_RADAR_WARN if alert else CONFIG_RADAR
    # blt_smt_cfg fields: config=1, status=2 (ON=1/OFF=0).
    # Proto3 omits the default OFF value, as in the app's generated schema.
    smart_config = protobuf_varint(1, config)
    if enabled:
        smart_config += protobuf_varint(2, STATUS_ON)
    payload = (
        protobuf_varint(1, SERVICE_BLE_LIGHT)
        + protobuf_varint(2, OP_SET)
        + protobuf_varint(3, SUBSERVICE_SMART_CONFIG)
        # blt_message_format.cfg_set is protobuf field 10 (wire key 0x52).
        + protobuf_bytes(10, smart_config)
    )
    return build_header(
        payload,
        service=SERVICE_BLE_LIGHT,
        subtype=SUBSERVICE_SMART_CONFIG,
        operation=OP_SET,
    )


def build_radar_broadcast_frame(enabled: bool) -> bytes:
    """Enable or disable the app's radar detection data broadcast."""
    # peripheral_config_message.dataService is field 4; its dataSwitch is field 1.
    broadcast = protobuf_varint(1, int(enabled))
    message = protobuf_bytes(4, broadcast)
    payload = (
        protobuf_varint(1, SERVICE_CONFIG)
        + protobuf_varint(2, OP_SET)
        + protobuf_varint(3, SUBSERVICE_DATA_BROADCAST)
        + protobuf_bytes(5, message)
    )
    return build_header(
        payload,
        service=SERVICE_CONFIG,
        subtype=SUBSERVICE_DATA_BROADCAST,
        operation=OP_SET,
    )


def _protobuf_fields(data: bytes):
    """Yield (field number, wire type, value) for protobuf wire fields.

    Empty radar broadcasts end with a truncated field-5 tag (`2a` with no
    length). Stop cleanly there instead of raising, so callers see no targets.
    """
    pos = 0

    def varint() -> int | None:
        nonlocal pos
        value = shift = 0
        start = pos
        while pos < len(data):
            byte = data[pos]
            pos += 1
            value |= (byte & 0x7F) << shift
            if byte < 0x80:
                return value
            shift += 7
            if shift > 63:
                break
        pos = start
        return None

    while pos < len(data):
        key = varint()
        if key is None:
            return
        field, wire = key >> 3, key & 7
        if not field:
            raise ValueError("invalid protobuf field number")
        if wire == 0:
            value = varint()
            if value is None:
                return
        elif wire == 1:
            if pos + 8 > len(data):
                return
            value = data[pos : pos + 8]
            pos += 8
        elif wire == 2:
            length = varint()
            if length is None or pos + length > len(data):
                return
            value = data[pos : pos + length]
            pos += length
        elif wire == 5:
            if pos + 4 > len(data):
                return
            value = data[pos : pos + 4]
            pos += 4
        else:
            raise ValueError(f"unsupported protobuf wire type {wire}")
        yield field, wire, value


def decode_radar_payload(payload: bytes) -> list[dict[str, int]]:
    """Decode a Radar service protobuf body into raw target field values."""
    message = None
    for field, wire, value in _protobuf_fields(payload):
        if field == 5 and wire == 2:
            message = value
            break
    if message is None:
        return []
    targets = []
    for field, wire, value in _protobuf_fields(message):
        if field != 6 or wire != 2:
            continue
        target: dict[int, int] = {}
        for number, value_wire, item in _protobuf_fields(value):
            if value_wire == 0 and number in (6, 7, 8):
                target[number] = item
        targets.append(target)
    return targets
