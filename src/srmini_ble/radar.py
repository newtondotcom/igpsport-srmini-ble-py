"""Radar feature switch used by the SR Mini light configuration service."""

from .protocol import build_header, protobuf_bytes, protobuf_varint

SERVICE_BLE_LIGHT = 106
OP_SET = 1
SUBSERVICE_SMART_CONFIG = 4
CONFIG_RADAR = 7
CONFIG_RADAR_WARN = 21
STATUS_ON = 1


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
