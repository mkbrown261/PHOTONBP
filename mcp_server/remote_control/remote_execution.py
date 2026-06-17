"""
remote_execution.py — UEOS Remote Execution Client

Implements Unreal Engine's Python Remote Execution protocol (multicast UDP
discovery + TCP command socket). This is the CORRECT way to run arbitrary
Python inside the UE editor — not the HTTP CDO approach which is blocked
by UE's security model regardless of INI settings.

Requirements (UE side):
  - Python Editor Script Plugin enabled
  - Project Settings → Plugins → Python → Enable Remote Execution ✅
  - Multicast Bind Address: 0.0.0.0
  - Multicast Group Endpoint: 239.0.0.1:6766 (default)

Protocol reference: Engine/Plugins/Experimental/PythonScriptPlugin/Content/Python/remote_execution.py
"""

from __future__ import annotations

import asyncio
import json
import logging
import socket
import struct
import time
import uuid
from typing import Any

log = logging.getLogger("ueos.remote_exec")

# ── Protocol constants (must match UE's Python plugin) ────────────────────────
DEFAULT_MULTICAST_TTL         = 0          # 0 = local machine only
DEFAULT_MULTICAST_GROUP_IP    = "239.0.0.1"
DEFAULT_MULTICAST_GROUP_PORT  = 6766
DEFAULT_MULTICAST_BIND_IP     = "0.0.0.0"
DEFAULT_COMMAND_PORT          = 6776       # TCP port UE listens on for commands

# Message types
_TYPE_PING       = "ping"
_TYPE_PONG       = "pong"
_TYPE_OPEN_CMD   = "open_connection"
_TYPE_CLOSE_CMD  = "close_connection"
_TYPE_CMD        = "command"
_TYPE_CMD_RESULT = "command_result"

# Exec modes
EXEC_MODE_EXEC_FILE        = "ExecuteFile"
EXEC_MODE_EXEC_STATEMENT   = "ExecuteStatement"
EXEC_MODE_EVALUATE_EXPR    = "EvaluateExpression"


# ── Message helpers ────────────────────────────────────────────────────────────

def _make_message(msg_type: str, source_id: str, dest_id: str | None = None, data: dict | None = None) -> bytes:
    msg = {
        "version":   1,
        "magic":     "ue_py",
        "type":      msg_type,
        "source":    source_id,
        "dest":      dest_id or "",
        "data":      data or {},
    }
    payload = json.dumps(msg).encode("utf-8")
    # 4-byte little-endian length prefix
    return struct.pack("<I", len(payload)) + payload


def _parse_message(data: bytes) -> dict | None:
    try:
        if len(data) < 4:
            return None
        length = struct.unpack("<I", data[:4])[0]
        payload = data[4:4 + length]
        return json.loads(payload.decode("utf-8"))
    except Exception:
        return None


# ── UDP discovery ──────────────────────────────────────────────────────────────

class _UDPDiscovery:
    """
    Sends UDP multicast pings and collects pong replies from UE instances.
    """

    def __init__(
        self,
        multicast_group:  str = DEFAULT_MULTICAST_GROUP_IP,
        multicast_port:   int = DEFAULT_MULTICAST_GROUP_PORT,
        bind_ip:          str = DEFAULT_MULTICAST_BIND_IP,
        ttl:              int = DEFAULT_MULTICAST_TTL,
    ):
        self.multicast_group = multicast_group
        self.multicast_port  = multicast_port
        self.bind_ip         = bind_ip
        self.ttl             = ttl
        self.source_id       = str(uuid.uuid4())
        self._sock: socket.socket | None = None

    def open(self):
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        except AttributeError:
            pass  # Windows doesn't have SO_REUSEPORT
        self._sock.bind((self.bind_ip, self.multicast_port))
        # Join multicast group
        mreq = struct.pack("4sL",
            socket.inet_aton(self.multicast_group),
            socket.INADDR_ANY
        )
        self._sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        # Set TTL
        self._sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, self.ttl)
        self._sock.settimeout(0.5)

    def close(self):
        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass
            self._sock = None

    def ping(self):
        """Broadcast a ping to discover UE nodes."""
        msg = _make_message(_TYPE_PING, self.source_id)
        self._sock.sendto(msg, (self.multicast_group, self.multicast_port))

    def collect_pongs(self, timeout: float = 1.0) -> list[dict]:
        """Collect pong replies for up to `timeout` seconds."""
        nodes = []
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                data, addr = self._sock.recvfrom(4096)
                msg = _parse_message(data)
                if msg and msg.get("type") == _TYPE_PONG:
                    node = msg.get("data", {})
                    node["_addr"] = addr[0]
                    nodes.append(node)
            except socket.timeout:
                break
            except Exception:
                continue
        return nodes


# ── TCP command connection ────────────────────────────────────────────────────

class _TCPCommandConnection:
    """
    Opens a TCP connection to a discovered UE node and sends Python commands.
    """

    def __init__(self, node: dict, source_id: str, timeout: int = 30):
        self._node      = node
        self._source_id = source_id
        self._timeout   = timeout
        self._reader: asyncio.StreamReader | None  = None
        self._writer: asyncio.StreamWriter | None = None
        self._node_id   = node.get("node_id", "")
        self._command_ip   = node.get("_addr", "127.0.0.1")
        self._command_port = node.get("command_port", DEFAULT_COMMAND_PORT)

    async def open(self):
        self._reader, self._writer = await asyncio.wait_for(
            asyncio.open_connection(self._command_ip, self._command_port),
            timeout=5
        )
        # Send open_connection handshake
        msg = _make_message(_TYPE_OPEN_CMD, self._source_id, self._node_id)
        self._writer.write(msg)
        await self._writer.drain()

    async def close(self):
        if self._writer:
            try:
                msg = _make_message(_TYPE_CLOSE_CMD, self._source_id, self._node_id)
                self._writer.write(msg)
                await self._writer.drain()
                self._writer.close()
            except Exception:
                pass

    async def run_command(
        self,
        command:    str,
        exec_mode:  str = EXEC_MODE_EXEC_STATEMENT,
        unattended: bool = True,
    ) -> dict:
        """
        Send a Python command and wait for the result.
        Returns dict with keys: success, result, output (list of {type, output}).
        """
        cmd_id = str(uuid.uuid4())
        msg = _make_message(
            _TYPE_CMD,
            self._source_id,
            self._node_id,
            data={
                "command":    command,
                "exec_mode":  exec_mode,
                "unattended": unattended,
                "command_id": cmd_id,
            }
        )
        self._writer.write(msg)
        await self._writer.drain()

        # Read response
        deadline = time.monotonic() + self._timeout
        while time.monotonic() < deadline:
            try:
                header = await asyncio.wait_for(
                    self._reader.readexactly(4),
                    timeout=min(2.0, deadline - time.monotonic())
                )
                length = struct.unpack("<I", header)[0]
                payload = await asyncio.wait_for(
                    self._reader.readexactly(length),
                    timeout=min(self._timeout, deadline - time.monotonic())
                )
                msg = json.loads(payload.decode("utf-8"))
                if msg.get("type") == _TYPE_CMD_RESULT:
                    data = msg.get("data", {})
                    if data.get("command_id") == cmd_id:
                        return data
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                raise RuntimeError(f"TCP read error: {e}")

        raise TimeoutError(f"No response from UE within {self._timeout}s")


# ── High-level client ─────────────────────────────────────────────────────────

class UnrealRemoteExecution:
    """
    High-level async client for UE Python Remote Execution.

    Usage:
        exec = UnrealRemoteExecution()
        result = await exec.run("print('hello')")
        # result = {"success": True, "output": [...], "result": ""}
    """

    def __init__(
        self,
        multicast_group: str = DEFAULT_MULTICAST_GROUP_IP,
        multicast_port:  int = DEFAULT_MULTICAST_GROUP_PORT,
        bind_ip:         str = DEFAULT_MULTICAST_BIND_IP,
        command_timeout: int = 30,
        discovery_timeout: float = 3.0,
    ):
        self.multicast_group    = multicast_group
        self.multicast_port     = multicast_port
        self.bind_ip            = bind_ip
        self.command_timeout    = command_timeout
        self.discovery_timeout  = discovery_timeout
        self._source_id         = str(uuid.uuid4())

    async def _discover_node(self) -> dict:
        """Find a UE instance via multicast. Returns node dict or raises."""
        loop = asyncio.get_event_loop()
        discovery = _UDPDiscovery(
            multicast_group=self.multicast_group,
            multicast_port=self.multicast_port,
            bind_ip=self.bind_ip,
        )

        def _sync_discover():
            discovery.open()
            try:
                deadline = time.monotonic() + self.discovery_timeout
                while time.monotonic() < deadline:
                    discovery.ping()
                    nodes = discovery.collect_pongs(timeout=0.5)
                    if nodes:
                        return nodes[0]
                return None
            finally:
                discovery.close()

        node = await loop.run_in_executor(None, _sync_discover)
        if not node:
            raise RuntimeError(
                "No Unreal Engine instance found via Remote Execution multicast. "
                "Ensure: Python Editor Script Plugin enabled, "
                "Project Settings → Plugins → Python → Enable Remote Execution ✅, "
                "Multicast Bind Address = 0.0.0.0"
            )
        return node

    async def run(
        self,
        script: str,
        exec_mode: str = EXEC_MODE_EXEC_STATEMENT,
        timeout: int | None = None,
    ) -> dict:
        """
        Discover a UE node, connect, run script, disconnect.
        Returns: { "success": bool, "output": [...], "result": str }
        """
        node = await self._discover_node()
        conn = _TCPCommandConnection(
            node,
            self._source_id,
            timeout=timeout or self.command_timeout
        )
        await conn.open()
        try:
            result = await conn.run_command(script, exec_mode=exec_mode)
            return result
        finally:
            await conn.close()

    async def ping(self) -> bool:
        """Return True if a UE instance is reachable via Remote Execution."""
        try:
            await self._discover_node()
            return True
        except Exception:
            return False

    async def run_ex(self, script: str, timeout: int | None = None) -> dict:
        """
        Like run() but wraps script in try/except and parses UEOS_RESULT / UEOS_ERROR markers.
        Returns: { "ok": bool, "result": Any, "error": str | None, "raw_output": str }
        """
        wrapped = (
            "import json as _j, traceback as _tb\n"
            "try:\n"
            + "\n".join("    " + line for line in script.splitlines())
            + "\nexcept Exception as _e:\n"
            "    print('UEOS_ERROR:' + _tb.format_exc().replace('\\n', ' | '))\n"
        )
        raw = await self.run(wrapped, timeout=timeout)
        return _parse_exec_result(raw)


def _parse_exec_result(raw: dict) -> dict:
    """Parse UEOS_RESULT / UEOS_ERROR markers from Remote Execution output."""
    output_entries = raw.get("output", [])
    all_output = "\n".join(
        entry.get("output", "") for entry in output_entries
        if isinstance(entry, dict)
    )

    result_val = None
    error_val  = None

    for line in all_output.splitlines():
        if line.startswith("UEOS_RESULT:"):
            try:
                result_val = json.loads(line[len("UEOS_RESULT:"):])
            except Exception:
                result_val = line[len("UEOS_RESULT:"):]
        elif line.startswith("UEOS_ERROR:"):
            error_val = line[len("UEOS_ERROR:"):]

    return {
        "ok":         raw.get("success", False) and error_val is None,
        "result":     result_val,
        "error":      error_val,
        "raw_output": all_output,
    }
