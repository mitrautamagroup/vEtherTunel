"""Interactive userspace node for the vEtherTunel QUIC relay prototype."""

from __future__ import annotations

import argparse
import asyncio
from contextlib import suppress
import getpass
import ipaddress
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
    MAX_DATAGRAM_FRAME_SIZE,
    MAX_QUIC_DATAGRAM_SIZE,
    PAYLOAD_IPV4,
    PAYLOAD_IPV6,
    PAYLOAD_TEXT,
    ProtocolError,
    max_envelope_payload_size,
    validate_ip_packet,
)
from .tun_linux import LinuxTunDevice, LinuxTunError, TUN_MTU

LOG = logging.getLogger("vethertunel.node")


class NodeProtocol(QuicConnectionProtocol):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.auth_response: asyncio.Future[dict[str, Any]] = self._loop.create_future()
        self.control_buffer = bytearray()
        self.vether_id: str | None = None
        self.node_id: str | None = None
        self.local_overlay_addresses: set[ipaddress.IPv4Address | ipaddress.IPv6Address] = set()
        self.peer_node_addresses: dict[
            str, set[ipaddress.IPv4Address | ipaddress.IPv6Address]
        ] = {}
        self.tun_device: LinuxTunDevice | None = None

    def configure_tun(
        self,
        *,
        vether_id: str,
        node_id: str,
        local_addresses: set[ipaddress.IPv4Address | ipaddress.IPv6Address],
        peer_node_addresses: dict[
            str, set[ipaddress.IPv4Address | ipaddress.IPv6Address]
        ],
        device: LinuxTunDevice,
    ) -> None:
        self.vether_id = vether_id
        self.node_id = node_id
        self.local_overlay_addresses = local_addresses
        self.peer_node_addresses = peer_node_addresses
        self.tun_device = device

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
                try:
                    packet_source, packet_destination = validate_ip_packet(
                        envelope.payload, envelope.payload_type
                    )
                except ProtocolError as exc:
                    LOG.warning("dropped invalid IP packet from hub: %s", exc)
                    return
                if self.tun_device is not None:
                    if (
                        envelope.vether_id != self.vether_id
                        or envelope.destination_node_id != self.node_id
                        or packet_destination not in self.local_overlay_addresses
                        or packet_source
                        not in self.peer_node_addresses.get(envelope.source_node_id, set())
                    ):
                        LOG.warning("dropped IP packet that does not match TUN peer policy")
                        return
                    try:
                        self.tun_device.write_packet(envelope.payload)
                    except (OSError, LinuxTunError) as exc:
                        LOG.warning("could not inject IP packet into Linux TUN: %s", exc)
                    return
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
    if args.enable_tun and sys.platform != "linux":
        raise LinuxTunError("--enable-tun is supported on Linux only; this mode makes no Mac changes")
    local_addresses, peer_node_addresses = _parse_tun_addresses(args)
    if args.enable_tun:
        for peer_id in peer_node_addresses:
            capacity = max_envelope_payload_size(args.vether_id, args.node_id, peer_id)
            if capacity < TUN_MTU:
                raise LinuxTunError(
                    f"IDs leave room for {capacity} byte IP packets to {peer_id}; "
                    f"TUN requires at least {TUN_MTU} bytes"
                )
    token = os.environ.get(args.token_env)
    if not token:
        token = getpass.getpass(f"Enrollment token for {args.node_id}: ")
    configuration = QuicConfiguration(
        alpn_protocols=[ALPN],
        is_client=True,
        max_datagram_frame_size=MAX_DATAGRAM_FRAME_SIZE,
        max_datagram_size=MAX_QUIC_DATAGRAM_SIZE,
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
        if args.enable_tun:
            peer_addresses = set().union(*peer_node_addresses.values())
            device = LinuxTunDevice(args.tun_name, local_addresses, peer_addresses)
            protocol.configure_tun(
                vether_id=args.vether_id,
                node_id=args.node_id,
                local_addresses=local_addresses,
                peer_node_addresses=peer_node_addresses,
                device=device,
            )
            print(
                f"Connected with Linux TUN {device.name} (MTU {TUN_MTU}); "
                "only assigned peer /32 and /128 routes are installed. Ctrl-C to stop.",
                flush=True,
            )
            packet_task = asyncio.create_task(
                _tun_packet_loop(protocol, device, args.vether_id, args.node_id,
                                 local_addresses, peer_node_addresses)
            )
            try:
                await packet_task
            finally:
                packet_task.cancel()
                with suppress(asyncio.CancelledError):
                    await packet_task
                device.close()
        else:
            print(f"Connected as {args.node_id} in vEther {args.vether_id}. Type /quit to stop.")
            await _interactive_loop(protocol, args.vether_id, args.node_id)


def _parse_tun_addresses(
    args: argparse.Namespace,
) -> tuple[
    set[ipaddress.IPv4Address | ipaddress.IPv6Address],
    dict[str, set[ipaddress.IPv4Address | ipaddress.IPv6Address]],
]:
    if not args.enable_tun:
        if args.overlay_address or args.peer_address:
            raise ValueError("--overlay-address and --peer-address require --enable-tun")
        return set(), {}
    if not args.overlay_address or not args.peer_address:
        raise ValueError("TUN mode requires at least one --overlay-address and --peer-address NODE=IP")
    try:
        local = {ipaddress.ip_address(value) for value in args.overlay_address}
    except ValueError as exc:
        raise ValueError("overlay addresses must be IP addresses without CIDR prefixes") from exc
    if len(local) != len(args.overlay_address):
        raise ValueError("duplicate local overlay address")
    peers: dict[str, set[ipaddress.IPv4Address | ipaddress.IPv6Address]] = {}
    all_peer_addresses: set[ipaddress.IPv4Address | ipaddress.IPv6Address] = set()
    for assignment in args.peer_address:
        peer_id, separator, raw_address = assignment.partition("=")
        if not separator or not peer_id or peer_id == args.node_id:
            raise ValueError("peer address format must be NODE=IP for a different node")
        if peer_id in peers:
            raise ValueError(f"duplicate peer address mapping for {peer_id}")
        try:
            address = ipaddress.ip_address(raw_address)
        except ValueError as exc:
            raise ValueError(f"invalid peer IP address for {peer_id}") from exc
        if address in local or address in all_peer_addresses:
            raise ValueError(f"duplicate local or peer overlay address: {address}")
        peers[peer_id] = {address}
        all_peer_addresses.add(address)
    return local, peers


async def _tun_packet_loop(
    protocol: NodeProtocol,
    device: LinuxTunDevice,
    vether_id: str,
    node_id: str,
    local_addresses: set[ipaddress.IPv4Address | ipaddress.IPv6Address],
    peer_node_addresses: dict[str, set[ipaddress.IPv4Address | ipaddress.IPv6Address]],
) -> None:
    address_to_peer = {
        address: peer_id
        for peer_id, addresses in peer_node_addresses.items()
        for address in addresses
    }
    while True:
        packet = await device.read_packet()
        if not packet:
            continue
        version = packet[0] >> 4
        payload_type = {4: PAYLOAD_IPV4, 6: PAYLOAD_IPV6}.get(version)
        if payload_type is None:
            LOG.warning("dropped packet with unsupported IP version")
            continue
        try:
            source, destination = validate_ip_packet(packet, payload_type)
        except ProtocolError as exc:
            LOG.warning("dropped invalid packet read from TUN: %s", exc)
            continue
        if source not in local_addresses:
            LOG.warning("dropped TUN packet with unassigned source address")
            continue
        peer_id = address_to_peer.get(destination)
        if peer_id is None:
            LOG.warning("dropped TUN packet outside configured peer routes")
            continue
        try:
            raw = Envelope(vether_id, node_id, peer_id, payload_type, packet).encode()
        except ProtocolError as exc:
            LOG.warning("dropped TUN packet: %s", exc)
            continue
        protocol._quic.send_datagram_frame(raw)
        protocol.transmit()


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
    parser.add_argument("--enable-tun", action="store_true", help="opt in to Linux TUN and narrow peer routes")
    parser.add_argument("--tun-name", default="vtun0", help="Linux TUN interface name (default: vtun0)")
    parser.add_argument("--overlay-address", action="append", default=[], help="local overlay IP; repeatable")
    parser.add_argument("--peer-address", action="append", default=[], help="allowed peer mapping NODE=IP; repeatable")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)
    try:
        asyncio.run(run_node(args))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
