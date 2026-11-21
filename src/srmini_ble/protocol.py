"""Wire framing and protobuf helpers for the iGPSPORT BLE light service."""

HEADER_SIZE = 20
SERVICE_BLE_LIGHT = 106
OP_SET = 1
SUBSERVICE_CURRENT_MODE = 2


def encode_varint(value: int) -> bytes:
    if value < 0:
        raise ValueError("protobuf enum/varint values must be non-negative")
    out = bytearray()
    while value > 0x7F:
        out.append((value & 0x7F) | 0x80)
        value >>= 7
    out.append(value)
    return bytes(out)


def protobuf_varint(field_number: int, value: int) -> bytes:
    return encode_varint(field_number << 3) + encode_varint(value)


def protobuf_bytes(field_number: int, payload: bytes) -> bytes:
    return (encode_varint((field_number << 3) | 2)
            + encode_varint(len(payload)) + payload)


def crc8(data: bytes) -> int:
    """CRC-8/MAXIM, reflected polynomial 0x8C, init/xorout zero."""
    crc = 0
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ (0x8C if crc & 1 else 0)
    return crc


def build_header(payload: bytes, *, service: int, subtype: int,
                 operation: int) -> bytes:
    """Build the app's 20-byte command header followed by its protobuf body."""
    if len(payload) > 0xFFFF:
        raise ValueError("payload is too large for the protocol header")
    header = bytearray([0xFF] * HEADER_SIZE)
    header[0] = 1
    header[1] = service
    header[2] = subtype
    header[4] = operation
    header[7:9] = len(payload).to_bytes(2, "big")
    header[9] = crc8(payload)
    header[10] = 1
    header[19] = crc8(header[:19])
    return bytes(header) + payload
