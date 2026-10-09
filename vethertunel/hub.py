"""Opt-in userspace QUIC hub; it never creates or changes host interfaces."""

from __future__ import annotations

import argparse
import asyncio
import hmac
import ipaddress
import json
import logging
from pathlib import Path
from typing import Any

from aioquic.asyncio import QuicConnectionProtocol, serve
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.events import (
    ConnectionTerminated,
    DatagramFrameReceived,
    QuicEvent,
    StreamDataReceived,
)

from .protocol import (
    Envelope,
    MAX_DATAGRAM_SIZE,
    MAX_DATAGRAM_FRAME_SIZE,
    MAX_QUIC_DATAGRAM_SIZE,
    PAYLOAD_IPV4,
    PAYLOAD_IPV6,
    ProtocolError,
    validate_ip_packet,
)

ALPN = "vethertunel/1"
MAX_CONTROL_SIZE = 4096
LOG = logging.getLogger("vethertunel.hub")
_PRIVATE_BIND_NETWORKS = (
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("fc00::/7"),
)


def validate_bind_host(host: str, allow_private_network: bool) -> None:
    """Keep the hub on loopback unless a private LAN bind is explicitly enabled."""
    if host.lower() == "localhost":
        return
    try:
        address = ipaddress.ip_address(host)
    except ValueError as exc:
        raise ValueError("bind host must be localhost or a literal private IP address") from exc
    if address.is_unspecified or address.is_multicast:
        raise ValueError("wildcard and multicast bind addresses are not allowed")
    if address.is_loopback:
        return
    if not allow_private_network:
        raise ValueError("non-loopback bind requires --allow-private-network")
    if not any(
        address.version == network.version and address in network
        for network in _PRIVATE_BIND_NETWORKS
    ):
        raise ValueError("bind address must be RFC1918 IPv4 or IPv6 ULA")


class HubRegistry:
    def __init__(self, node_config: dict[tuple[str, str], dict[str, Any]]) -> None:
        self.node_config = node_config
        self.connections: dict[tuple[str, str], HubProtocol] = {}


class HubProtocol(QuicConnectionProtocol):
    def __init__(self, *args: Any, registry: HubRegistry, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.registry = registry
        self.node_key: tuple[str, str] | None = None
        self.control_streams: dict[int, bytearray] = {}

    def quic_event_received(self, event: QuicEvent) -> None:
        if isinstance(event, StreamDataReceived):
            buffer = self.control_streams.setdefault(event.stream_id, bytearray())
            if len(buffer) + len(event.data) > MAX_CONTROL_SIZE:
                self._reply(event.stream_id, {"type": "error", "error": "control message too large"})
                return
            buffer.extend(event.data)
            if event.end_stream:
                self._handle_hello(event.stream_id, bytes(buffer))
                self.control_streams.pop(event.stream_id, None)
        elif isinstance(event, DatagramFrameReceived):
            self._relay(event.data)
        elif isinstance(event, ConnectionTerminated):
            self._unregister()

    def _handle_hello(self, stream_id: int, raw: bytes) -> None:
        try:
            message = json.loads(raw)
            if message.get("type") != "hello":
                raise ValueError("expected hello")
            if message.get("version") != 1:
                raise ValueError("unsupported control protocol version")
            node_id = _identifier(message.get("node_id"))
            vether_id = _identifier(message.get("vEther_id"))
            token = message.get("token")
            if not isinstance(token, str) or not token:
                raise ValueError("missing token")
            key = (vether_id, node_id)
            allowed = self.registry.node_config.get(key)
            if allowed is None or not hmac.compare_digest(token, allowed["token"]):
                self._reply(stream_id, {"type": "error", "error": "not authorized"})
                self.close(reason_phrase="not authorized")
                return
            self._unregister()
            self.node_key = key
            self.registry.connections[key] = self
            self._reply(stream_id, {"type": "hello_ack", "version": 1})
            LOG.info("node registered: vEther=%s node=%s", vether_id, node_id)
        except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError, KeyError) as exc:
            self._reply(stream_id, {"type": "error", "error": str(exc)[:160]})

    def _relay(self, raw: bytes) -> None:
        if self.node_key is None:
            self.close(reason_phrase="enrollment required")
            return
        try:
            envelope = Envelope.decode(raw)
        except ProtocolError as exc:
            LOG.warning("dropped malformed datagram: %s", exc)
            return
        vether_id, authenticated_source = self.node_key
        if envelope.vether_id != vether_id or envelope.source_node_id != authenticated_source:
            LOG.warning("dropped datagram with mismatched source identity")
            return
        source_config = self.registry.node_config[self.node_key]
        if envelope.destination_node_id not in source_config["allowed_peers"]:
            LOG.warning("dropped datagram denied by peer policy")
            return
        destination_key = (vether_id, envelope.destination_node_id)
        destination_config = self.registry.node_config.get(destination_key)
        if destination_config is None:
            return
        if envelope.payload_type in (PAYLOAD_IPV4, PAYLOAD_IPV6):
            try:
                packet_source, packet_destination = validate_ip_packet(
                    envelope.payload, envelope.payload_type
                )
            except ProtocolError as exc:
                LOG.warning("dropped invalid IP packet: %s", exc)
                return
            if packet_source not in source_config["overlay_addresses"]:
                LOG.warning("dropped IP packet with unassigned source address")
                return
            if packet_destination not in destination_config["overlay_addresses"]:
                LOG.warning("dropped IP packet addressed to a different peer")
                return
        destination = self.registry.connections.get(destination_key)
        if destination is None:
            return
        destination._quic.send_datagram_frame(raw)
        destination.transmit()

    def _reply(self, stream_id: int, message: dict[str, Any]) -> None:
        payload = json.dumps(message, separators=(",", ":")).encode("utf-8")
        self._quic.send_stream_data(stream_id, payload, end_stream=True)
        self.transmit()

    def _unregister(self) -> None:
        if self.node_key is not None and self.registry.connections.get(self.node_key) is self:
            self.registry.connections.pop(self.node_key, None)
            LOG.info("node disconnected: vEther=%s node=%s", *self.node_key)
        self.node_key = None


def _identifier(value: object) -> str:
    if not isinstance(value, str) or not value or len(value.encode("utf-8")) > 64:
        raise ValueError("identifier must be 1..64 UTF-8 bytes")
    return value


def load_node_config(path: Path) -> dict[tuple[str, str], dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    nodes = data.get("nodes")
    if not isinstance(nodes, list):
        raise ValueError("config must contain a nodes array")
    result: dict[tuple[str, str], dict[str, Any]] = {}
    for node in nodes:
        if not isinstance(node, dict):
            raise ValueError("each node entry must be an object")
        vether_id = _identifier(node.get("vEther_id"))
        node_id = _identifier(node.get("node_id"))
        token = node.get("token")
        peers = node.get("allowed_peers", [])
        addresses = node.get("overlay_addresses", [])
        if not isinstance(token, str) or len(token) < 16:
            raise ValueError(f"token for {node_id} must contain at least 16 characters")
        if not isinstance(peers, list) or any(not isinstance(peer, str) for peer in peers):
            raise ValueError(f"allowed_peers for {node_id} must be a string array")
        if not isinstance(addresses, list) or not addresses:
            raise ValueError(f"overlay_addresses for {node_id} must be a non-empty string array")
        try:
            overlay_addresses = {ipaddress.ip_address(address) for address in addresses}
        except ValueError as exc:
            raise ValueError(f"invalid overlay address for {node_id}") from exc
        if len(overlay_addresses) != len(addresses):
            raise ValueError(f"duplicate overlay address for {node_id}")
        key = (vether_id, node_id)
        if key in result:
            raise ValueError(f"duplicate node registration: {node_id}")
        result[key] = {
            "token": token,
            "allowed_peers": set(peers),
            "overlay_addresses": overlay_addresses,
        }
    for (vether_id, node_id), entry in result.items():
        unknown_peers = entry["allowed_peers"] - {
            peer_id for peer_vether, peer_id in result if peer_vether == vether_id
        }
        if unknown_peers:
            raise ValueError(
                f"unknown peer(s) in vEther {vether_id} for {node_id}: "
                f"{', '.join(sorted(unknown_peers))}"
            )
    addresses_by_vether: dict[str, set[ipaddress.IPv4Address | ipaddress.IPv6Address]] = {}
    for (vether_id, node_id), entry in result.items():
        seen = addresses_by_vether.setdefault(vether_id, set())
        overlap = seen & entry["overlay_addresses"]
        if overlap:
            raise ValueError(f"duplicate overlay address in vEther {vether_id}: {min(overlap)}")
        seen.update(entry["overlay_addresses"])
    return result


async def run_hub(args: argparse.Namespace) -> None:
    validate_bind_host(args.host, getattr(args, "allow_private_network", False))
    registry = HubRegistry(load_node_config(args.config))
    configuration = QuicConfiguration(
        alpn_protocols=[ALPN],
        is_client=False,
        max_datagram_frame_size=MAX_DATAGRAM_FRAME_SIZE,
        max_datagram_size=MAX_QUIC_DATAGRAM_SIZE,
    )
    configuration.load_cert_chain(args.certificate, args.private_key)
    await serve(
        args.host,
        args.port,
        configuration=configuration,
        create_protocol=lambda *a, **kw: HubProtocol(*a, registry=registry, **kw),
        retry=True,
    )
    LOG.info("userspace QUIC hub listening on %s:%d", args.host, args.port)
    await asyncio.Future()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the vEtherTunel userspace QUIC relay")
    parser.add_argument("--config", type=Path, required=True, help="private JSON node registry")
    parser.add_argument("--certificate", type=Path, required=True, help="TLS certificate PEM")
    parser.add_argument("--private-key", type=Path, required=True, help="TLS private key PEM")
    parser.add_argument("--host", default="127.0.0.1", help="listen address (default: loopback only)")
    parser.add_argument("--port", type=int, default=4433)
    parser.add_argument(
        "--allow-private-network",
        action="store_true",
        help="allow binding to an RFC1918 IPv4 or IPv6 ULA address (never a wildcard/public address)",
    )
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)
    try:
        asyncio.run(run_hub(args))
    except ValueError as exc:
        parser.error(str(exc))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
