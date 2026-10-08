"""Interactive userspace node for the vEtherTunel QUIC relay prototype."""

from __future__ import annotations

import argparse
import asyncio
import getpass
import json
import logging
import os
import ssl
import sys
from typing import Any

from aioquic.asyncio import QuicConnectionProtocol
from aioquic.asyncio.client import connect
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.events import DatagramFrameReceived, QuicEvent, StreamDataReceived

from .hub import ALPN, MAX_CONTROL_SIZE
from .protocol import (
    Envelope,
    MAX_DATAGRAM_SIZE,
    PAYLOAD_IPV4,
    PAYLOAD_IPV6,
    PAYLOAD_TEXT,
    ProtocolError,
    validate_ip_packet,
)

LOG = logging.getLogger("vethertunel.node")


class NodeProtocol(QuicConnectionProtocol):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.auth_response: asyncio.Future[dict[str, Any]] = self._loop.create_future()
        self.control_buffer = bytearray()

    def quic_event_received(self, event: QuicEvent) -> None:
        if isinstance(event, StreamDataReceived):
            if len(self.control_buffer) + len(event.data) > MAX_CONTROL_SIZE:
                if not self.auth_response.done():
                    self.auth_response.set_exception(ProtocolError("control response too large"))
                return
            self.control_buffer.extend(event.data)
            if event.end_stream and not self.auth_response.done():
                try:
                    response = json.loads(self.control_buffer)
                    if not isinstance(response, dict):
                        raise ValueError("invalid control response")
                    self.auth_response.set_result(response)
                except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as exc:
                    self.auth_response.set_exception(ProtocolError("invalid control response"))
        elif isinstance(event, DatagramFrameReceived):
            try:
                envelope = Envelope.decode(event.data)
            except ProtocolError as exc:
                LOG.warning("dropped malformed datagram: %s", exc)
                return
            if envelope.payload_type == PAYLOAD_TEXT:
                message = envelope.payload.decode("utf-8", errors="replace")
                print(f"[{envelope.source_node_id} -> {envelope.destination_node_id}] {message}", flush=True)
            elif envelope.payload_type in (PAYLOAD_IPV4, PAYLOAD_IPV6):
                packet_source, packet_destination = validate_ip_packet(
                    envelope.payload, envelope.payload_type
                )
                print(
                    f"IP {packet_source} -> {packet_destination}; "
                    f"{len(envelope.payload)} bytes from {envelope.source_node_id}",
                    flush=True,
                )
            else:
                print(
                    f"received payload type={envelope.payload_type} bytes={len(envelope.payload)} "
                    f"from={envelope.source_node_id}",
                    flush=True,
                )


async def run_node(args: argparse.Namespace) -> None:
    token = os.environ.get(args.token_env)
    if not token:
        token = getpass.getpass(f"Enrollment token for {args.node_id}: ")
    configuration = QuicConfiguration(
        alpn_protocols=[ALPN],
        is_client=True,
        max_datagram_frame_size=MAX_DATAGRAM_SIZE,
        max_datagram_size=1200,
        server_name=args.server_name or args.host,
        verify_mode=ssl.CERT_REQUIRED,
    )
    configuration.load_verify_locations(cafile=str(args.ca_cert))

    async with connect(
        args.host,
        args.port,
        configuration=configuration,
        create_protocol=NodeProtocol,
    ) as protocol:
        assert isinstance(protocol, NodeProtocol)
        stream_id = protocol._quic.get_next_available_stream_id()
        hello = {
            "type": "hello",
            "version": 1,
            "vEther_id": args.vether_id,
            "node_id": args.node_id,
            "token": token,
        }
        protocol._quic.send_stream_data(
            stream_id,
            json.dumps(hello, separators=(",", ":")).encode("utf-8"),
            end_stream=True,
        )
        protocol.transmit()
        response = await asyncio.wait_for(protocol.auth_response, timeout=10)
        if response.get("type") != "hello_ack":
            raise PermissionError(response.get("error", "hub rejected enrollment"))
        print(f"Connected as {args.node_id} in vEther {args.vether_id}. Type /quit to stop.")
        await _interactive_loop(protocol, args.vether_id, args.node_id)


async def _interactive_loop(protocol: NodeProtocol, vether_id: str, node_id: str) -> None:
    while True:
        line = await asyncio.to_thread(sys.stdin.readline)
        if not line:
            return
        command = line.rstrip("\r\n")
        if command == "/quit":
            return
        words = command.split(maxsplit=2)
        payload_type = PAYLOAD_TEXT
        if words and words[0] in ("ip4", "ip6"):
            if len(words) != 3 or len(words[2]) > MAX_DATAGRAM_SIZE * 2:
                print("Format: ip4|ip6 <node-id> <packet-hex>", flush=True)
                continue
            destination = words[1]
            try:
                message_bytes = bytes.fromhex(words[2])
            except ValueError:
                print("Not sent: packet must be hexadecimal", flush=True)
                continue
            payload_type = PAYLOAD_IPV4 if words[0] == "ip4" else PAYLOAD_IPV6
        else:
            destination, separator, message = command.partition(" ")
            if not separator or not destination or not message:
                print("Format: <node-id> <message>; ip4|ip6 <node-id> <packet-hex>; /quit to stop", flush=True)
                continue
            message_bytes = message.encode("utf-8")
        try:
            raw = Envelope(
                vether_id=vether_id,
                source_node_id=node_id,
                destination_node_id=destination,
                payload_type=payload_type,
                payload=message_bytes,
            ).encode()
        except ProtocolError as exc:
            print(f"Not sent: {exc}", flush=True)
            continue
        protocol._quic.send_datagram_frame(raw)
        protocol.transmit()


def main() -> None:
    parser = argparse.ArgumentParser(description="Connect a userspace node to a vEtherTunel hub")
    parser.add_argument("--host", required=True, help="hub DNS name or IP")
    parser.add_argument("--port", type=int, default=4433)
    parser.add_argument("--server-name", help="TLS certificate DNS name (defaults to --host)")
    parser.add_argument("--ca-cert", required=True, help="CA certificate PEM used to verify the hub")
    parser.add_argument("--vether-id", required=True)
    parser.add_argument("--node-id", required=True)
    parser.add_argument("--token-env", default="VETHERTUNEL_TOKEN", help="environment variable for enrollment token")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)
    try:
        asyncio.run(run_node(args))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
