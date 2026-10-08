"""Versioned vEtherTunel datagram envelope for the userspace prototype."""

from __future__ import annotations

from dataclasses import dataclass
import struct

MAGIC = b"VETH"
VERSION = 1
PAYLOAD_TEXT = 1
PAYLOAD_IPV4 = 2
PAYLOAD_IPV6 = 3
MAX_DATAGRAM_SIZE = 1100
_HEADER = struct.Struct("!4sBBBBBH")
_MAX_ID_SIZE = 64


class ProtocolError(ValueError):
    """Raised when an envelope is malformed or unsupported."""


@dataclass(frozen=True, slots=True)
class Envelope:
    vether_id: str
    source_node_id: str
    destination_node_id: str
    payload_type: int
    payload: bytes

    def encode(self) -> bytes:
        ids = (self.vether_id, self.source_node_id, self.destination_node_id)
        if any(not isinstance(value, str) for value in ids):
            raise ProtocolError("identifiers must be strings")
        if not isinstance(self.payload, bytes):
            raise ProtocolError("payload must be bytes")
        encoded_ids = tuple(value.encode("utf-8") for value in ids)
        if any(not value or len(value) > _MAX_ID_SIZE for value in encoded_ids):
            raise ProtocolError("identifiers must be 1..64 UTF-8 bytes")
        if self.payload_type not in (PAYLOAD_TEXT, PAYLOAD_IPV4, PAYLOAD_IPV6):
            raise ProtocolError("unsupported payload type")
        if len(self.payload) > MAX_DATAGRAM_SIZE:
            raise ProtocolError("payload exceeds prototype datagram limit")
        header = _HEADER.pack(
            MAGIC,
            VERSION,
            len(encoded_ids[0]),
            len(encoded_ids[1]),
            len(encoded_ids[2]),
            self.payload_type,
            len(self.payload),
        )
        packet = header + b"".join(encoded_ids) + self.payload
        if len(packet) > MAX_DATAGRAM_SIZE:
            raise ProtocolError("encoded datagram exceeds prototype limit")
        return packet

    @classmethod
    def decode(cls, packet: bytes) -> "Envelope":
        if len(packet) < _HEADER.size or len(packet) > MAX_DATAGRAM_SIZE:
            raise ProtocolError("invalid datagram size")
        magic, version, vether_len, source_len, destination_len, payload_type, payload_len = (
            _HEADER.unpack_from(packet)
        )
        if magic != MAGIC or version != VERSION:
            raise ProtocolError("invalid magic or unsupported protocol version")
        if not all(1 <= size <= _MAX_ID_SIZE for size in (vether_len, source_len, destination_len)):
            raise ProtocolError("invalid identifier length")
        ids_end = _HEADER.size + vether_len + source_len + destination_len
        if ids_end + payload_len != len(packet):
            raise ProtocolError("declared lengths do not match datagram")
        if payload_type not in (PAYLOAD_TEXT, PAYLOAD_IPV4, PAYLOAD_IPV6):
            raise ProtocolError("unsupported payload type")
        parts: list[str] = []
        offset = _HEADER.size
        for size in (vether_len, source_len, destination_len):
            try:
                parts.append(packet[offset : offset + size].decode("utf-8"))
            except UnicodeDecodeError as exc:
                raise ProtocolError("identifier is not valid UTF-8") from exc
            offset += size
        return cls(
            parts[0],
            parts[1],
            parts[2],
            payload_type,
            packet[offset:],
        )
