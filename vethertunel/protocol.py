"""Versioned vEtherTunel datagram envelope for the userspace prototype."""

from __future__ import annotations

from dataclasses import dataclass
import ipaddress
import struct
from typing import TypeAlias

MAGIC = b"VETH"
VERSION = 1
PAYLOAD_TEXT = 1
PAYLOAD_IPV4 = 2
PAYLOAD_IPV6 = 3
MAX_DATAGRAM_SIZE = 1100
_HEADER = struct.Struct("!4sBBBBBH")
_MAX_ID_SIZE = 64
IPAddress: TypeAlias = ipaddress.IPv4Address | ipaddress.IPv6Address


class ProtocolError(ValueError):
    """Raised when an envelope is malformed or unsupported."""


def validate_ip_packet(payload: bytes, payload_type: int) -> tuple[IPAddress, IPAddress]:
    """Validate packet framing and return its source and destination addresses."""
    if payload_type == PAYLOAD_IPV4:
        if len(payload) < 20 or payload[0] >> 4 != 4:
            raise ProtocolError("invalid IPv4 packet header")
        header_length = (payload[0] & 0x0F) * 4
        total_length = int.from_bytes(payload[2:4], "big")
        if header_length < 20 or header_length > len(payload):
            raise ProtocolError("invalid IPv4 header length")
        if total_length != len(payload) or total_length < header_length:
            raise ProtocolError("invalid IPv4 total length")
        return ipaddress.ip_address(payload[12:16]), ipaddress.ip_address(payload[16:20])
    if payload_type == PAYLOAD_IPV6:
        if len(payload) < 40 or payload[0] >> 4 != 6:
            raise ProtocolError("invalid IPv6 packet header")
        payload_length = int.from_bytes(payload[4:6], "big")
        if payload_length == 0 and len(payload) != 40:
            raise ProtocolError("IPv6 jumbograms are not supported by this prototype")
        if 40 + payload_length != len(payload):
            raise ProtocolError("invalid IPv6 payload length")
        return ipaddress.ip_address(payload[8:24]), ipaddress.ip_address(payload[24:40])
    raise ProtocolError("payload is not an IP packet")


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
        if self.payload_type in (PAYLOAD_IPV4, PAYLOAD_IPV6):
            validate_ip_packet(self.payload, self.payload_type)
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
        payload = packet[offset:]
        if payload_type in (PAYLOAD_IPV4, PAYLOAD_IPV6):
            validate_ip_packet(payload, payload_type)
        return cls(
            parts[0],
            parts[1],
            parts[2],
            payload_type,
            payload,
        )
