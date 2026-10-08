"""Opt-in userspace QUIC hub; it never creates or changes host interfaces."""

from __future__ import annotations

import argparse
import asyncio
import hmac
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

from .protocol import Envelope, MAX_DATAGRAM_SIZE, PAYLOAD_TEXT, ProtocolError

ALPN = "vethertunel/1"
MAX_CONTROL_SIZE = 4096
LOG = logging.getLogger("vethertunel.hub")


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
        if envelope.payload_type != PAYLOAD_TEXT:
            LOG.warning("dropped non-text payload; IP forwarding is not implemented")
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
        if not isinstance(token, str) or len(token) < 16:
            raise ValueError(f"token for {node_id} must contain at least 16 characters")
        if not isinstance(peers, list) or any(not isinstance(peer, str) for peer in peers):
            raise ValueError(f"allowed_peers for {node_id} must be a string array")
        key = (vether_id, node_id)
        if key in result:
            raise ValueError(f"duplicate node registration: {node_id}")
        result[key] = {"token": token, "allowed_peers": set(peers)}
    return result


async def run_hub(args: argparse.Namespace) -> None:
    registry = HubRegistry(load_node_config(args.config))
    configuration = QuicConfiguration(
        alpn_protocols=[ALPN],
        is_client=False,
        max_datagram_frame_size=MAX_DATAGRAM_SIZE,
        max_datagram_size=1200,
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
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)
    try:
        asyncio.run(run_hub(args))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
