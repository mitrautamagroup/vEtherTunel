"""Opt-in Linux TUN device with narrow overlay routes and fd-owned lifetime."""

from __future__ import annotations

import asyncio
import fcntl
import ipaddress
import os
import re
import struct
import subprocess
import sys
from typing import Iterable

TUNSETIFF = 0x400454CA
IFF_TUN = 0x0001
IFF_NO_PI = 0x1000
IFF_TUN_EXCL = 0x8000
TUN_MTU = 1280
_IFREQ = struct.Struct("16sH")
_IP_COMMANDS = ("/usr/sbin/ip", "/sbin/ip", "/usr/bin/ip", "/bin/ip")


class LinuxTunError(RuntimeError):
    """Raised when a Linux TUN device cannot be safely configured."""


class LinuxTunDevice:
    """Create a non-persistent Linux TUN device for explicitly opted-in nodes."""

    def __init__(
        self,
        name: str,
        local_addresses: Iterable[ipaddress.IPv4Address | ipaddress.IPv6Address],
        peer_addresses: Iterable[ipaddress.IPv4Address | ipaddress.IPv6Address],
        *,
        mtu: int = TUN_MTU,
    ) -> None:
        if sys.platform != "linux":
            raise LinuxTunError("the TUN adapter is available on Linux only")
        if not re.fullmatch(r"[A-Za-z0-9_.-]{1,15}", name):
            raise LinuxTunError("TUN name must be 1..15 safe interface-name characters")
        if not TUN_MTU <= mtu <= 9000:
            raise LinuxTunError(f"TUN MTU must be between {TUN_MTU} and 9000 bytes")

        self.name = name
        self.fd: int | None = None
        self._ip = next(
            (
                path
                for path in _IP_COMMANDS
                if os.path.isfile(path) and os.access(path, os.X_OK)
            ),
            None,
        )
        if self._ip is None:
            raise LinuxTunError("the iproute2 `ip` command is required on Linux")
        locals_ = tuple(dict.fromkeys(local_addresses))
        peers = tuple(dict.fromkeys(peer_addresses))
        if not locals_ or not peers:
            raise LinuxTunError("TUN mode requires local overlay addresses and peer addresses")
        if set(locals_) & set(peers):
            raise LinuxTunError("local and peer overlay addresses must be distinct")

        try:
            fd = os.open("/dev/net/tun", os.O_RDWR | os.O_NONBLOCK | os.O_CLOEXEC)
        except OSError as exc:
            raise LinuxTunError("cannot open /dev/net/tun; Linux TUN and CAP_NET_ADMIN are required") from exc

        try:
            request = _IFREQ.pack(name.encode("ascii"), IFF_TUN | IFF_NO_PI | IFF_TUN_EXCL)
            result = fcntl.ioctl(fd, TUNSETIFF, request)
            self.name = _IFREQ.unpack(result[: _IFREQ.size])[0].split(b"\0", 1)[0].decode("ascii")
            self.fd = fd
            for address in locals_:
                self._add_address(address)
            self._run_ip("link", "set", "dev", self.name, "mtu", str(mtu), "up")
            for address in peers:
                family = "-4" if address.version == 4 else "-6"
                prefix = 32 if address.version == 4 else 128
                self._run_ip(family, "route", "add", f"{address}/{prefix}", "dev", self.name)
        except Exception as exc:
            os.close(fd)
            self.fd = None
            if isinstance(exc, LinuxTunError):
                raise
            raise LinuxTunError(f"could not configure Linux TUN interface {name}") from exc

    def _add_address(self, address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> None:
        family = "-4" if address.version == 4 else "-6"
        prefix = 32 if address.version == 4 else 128
        args = [family, "address", "add", f"{address}/{prefix}", "dev", self.name]
        if address.version == 6:
            args.append("nodad")
        self._run_ip(*args)

    def _run_ip(self, *args: str) -> None:
        assert self._ip is not None
        try:
            result = subprocess.run(
                [self._ip, *args],
                capture_output=True,
                check=False,
                text=True,
                timeout=10,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise LinuxTunError("failed to configure Linux TUN interface") from exc
        if result.returncode:
            detail = result.stderr.strip()[:200]
            raise LinuxTunError(detail or "failed to configure Linux TUN interface")

    async def read_packet(self) -> bytes:
        if self.fd is None:
            raise LinuxTunError("TUN interface is closed")
        loop = asyncio.get_running_loop()
        future: asyncio.Future[bytes] = loop.create_future()

        def readable() -> None:
            if future.done() or self.fd is None:
                return
            try:
                packet = os.read(self.fd, 65535)
            except BlockingIOError:
                return
            except OSError as exc:
                future.set_exception(exc)
            else:
                future.set_result(packet)

        loop.add_reader(self.fd, readable)
        try:
            return await future
        finally:
            if self.fd is not None:
                loop.remove_reader(self.fd)

    def write_packet(self, packet: bytes) -> None:
        if self.fd is None:
            raise LinuxTunError("TUN interface is closed")
        written = os.write(self.fd, packet)
        if written != len(packet):
            raise LinuxTunError("Linux TUN accepted only part of an IP packet")

    def close(self) -> None:
        """Closing the non-persistent TUN fd removes its interface and routes."""
        if self.fd is not None:
            fd, self.fd = self.fd, None
            os.close(fd)

    def __enter__(self) -> "LinuxTunDevice":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
