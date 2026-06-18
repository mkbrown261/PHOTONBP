"""
remote_execution.py — UE Python Remote Execution client

Protocol facts (from upyrc source — the authoritative reference):

UDP multicast socket:
  - Plain JSON, NO length prefix
  - IP_MULTICAST_LOOP = 1 (required)
  - membership_request = inet_aton(GROUP_IP) + inet_aton(BIND_ADDRESS)  ← NOT INADDR_ANY
  - bind to (BIND_ADDRESS, GROUP_PORT)

TCP command socket:
  - CLIENT binds + listens, UE connects BACK to the client
  - open_connection message tells UE which (ip, port) to connect to
  - Plain JSON, NO length prefix
  - recvfrom in a loop, accumulate bytes, try json.loads each time

Sequence:
  1. Create multicast UDP socket
  2. Send ping  →  receive pong (contains unreal_node_id)
  3. Bind TCP socket on a random free port, call listen()
  4. Send open_connection via UDP (telling UE the TCP port)
  5. Call accept() — UE connects to us
  6. Send command JSON over the TCP connection
  7. Receive command_result JSON from the TCP connection
  8. Send close_connection via UDP
  9. Close everything
"""

from __future__ import annotations

import json
import logging
import socket
import time
import uuid
from typing import Any

log = logging.getLogger("ueos.remote_exec")

# ── Protocol constants ─────────────────────────────────────────────────────────
MULTICAST_GROUP_IP   = "239.0.0.1"
MULTICAST_GROUP_PORT = 6766
MULTICAST_BIND_ADDR  = "0.0.0.0"     # must match UE default
IP_MULTICAST_TTL     = 0             # 0 = local machine only
SOCKET_TIMEOUT       = 0.5           # seconds (matches upyrc)
BUFFER_SIZE          = 2_097_152     # 2 MB (matches upyrc)

PROTOCOL_VERSION = 1
UE_MAGIC         = "ue_py"

# Exec modes (string values UE expects)
EXEC_MODE_EXEC_FILE      = "ExecuteFile"
EXEC_MODE_EXEC_STATEMENT = "ExecuteStatement"
EXEC_MODE_EVAL_STATEMENT = "EvaluateStatement"


# ── Low-level helpers ─────────────────────────────────────────────────────────

def _get_free_port() -> tuple[str, int]:
    """Bind to port 0 to get a free ephemeral port, then release it."""
    with socket.socket() as s:
        s.bind(("", 0))
        _, port = s.getsockname()
    return ("127.0.0.1", port)


def _make_udp_msg(msg_type: str, source: str, dest: str = "", data: dict | None = None) -> bytes:
    """Encode a protocol message as plain JSON bytes (no length prefix)."""
    msg: dict[str, Any] = {
        "version": PROTOCOL_VERSION,
        "magic":   UE_MAGIC,
        "type":    msg_type,
        "source":  source,
    }
    if dest:
        msg["dest"] = dest
    if data is not None:
        msg["data"] = data
    return json.dumps(msg).encode("utf-8")


def _open_multicast_socket(bind_addr: str, group_ip: str, group_port: int, ttl: int) -> socket.socket:
    """
    Create and configure the UDP multicast socket exactly as upyrc does.
    Critical differences from the wrong implementation:
      - IP_MULTICAST_LOOP = 1
      - membership_request uses bind_addr, NOT INADDR_ANY
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, ttl)
    s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, 1)   # ← REQUIRED
    s.bind((bind_addr, group_port))
    membership_request = (
        socket.inet_aton(group_ip) +
        socket.inet_aton("0.0.0.0")   # INADDR_ANY for multicast join
    )
    s.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, membership_request)
    s.settimeout(SOCKET_TIMEOUT)
    return s


def _recv_json(s: socket.socket, our_msg_type: str) -> dict | None:
    """
    Receive UDP datagrams until we get a valid JSON response that isn't
    an echo of our own message type.  Returns None on timeout.
    """
    data_acc = b""
    while True:
        try:
            data, _ = s.recvfrom(BUFFER_SIZE)
            data_acc += data
            try:
                msg = json.loads(data_acc)
                data_acc = b""
            except json.JSONDecodeError:
                continue
            if msg.get("type") == our_msg_type:
                continue          # skip echo of our own message
            return msg
        except socket.timeout:
            return None


def _recv_tcp_json(conn: socket.socket, our_msg_type: str, timeout: float) -> dict | None:
    """
    Read from a TCP connection accumulating bytes until valid JSON arrives.
    Ignores echoes of our own message type.  Returns None on timeout.
    """
    conn.settimeout(timeout)
    data_acc = b""
    while True:
        try:
            chunk, _ = conn.recvfrom(BUFFER_SIZE)
            if not chunk:
                return None
            data_acc += chunk
            try:
                msg = json.loads(data_acc)
                data_acc = b""
            except json.JSONDecodeError:
                continue
            if msg.get("type") == our_msg_type:
                continue          # skip echo
            return msg
        except socket.timeout:
            return None


# ── High-level client ─────────────────────────────────────────────────────────

class UnrealRemoteExecution:
    """
    Synchronous UE Python Remote Execution client.

    Correct protocol flow (matching upyrc exactly):
      ping → pong → bind TCP → listen → open_connection (UDP) →
      accept() → command (TCP) → command_result (TCP) → close_connection (UDP)
    """

    def __init__(
        self,
        multicast_group_ip:   str   = MULTICAST_GROUP_IP,
        multicast_group_port: int   = MULTICAST_GROUP_PORT,
        multicast_bind_addr:  str   = MULTICAST_BIND_ADDR,
        ip_multicast_ttl:     int   = IP_MULTICAST_TTL,
        command_timeout:      int   = 30,
        discovery_timeout:    float = 3.0,
    ):
        self.group_ip        = multicast_group_ip
        self.group_port      = multicast_group_port
        self.bind_addr       = multicast_bind_addr
        self.ttl             = ip_multicast_ttl
        self.command_timeout = command_timeout
        self.disc_timeout    = discovery_timeout
        self.source_id       = str(uuid.uuid4())

    # ── Public API ─────────────────────────────────────────────────────────

    def ping(self) -> bool:
        """Return True if a UE instance responds to multicast ping."""
        try:
            node_id = self._discover()
            return node_id is not None
        except Exception:
            return False

    def run(
        self,
        script:    str,
        exec_mode: str = EXEC_MODE_EXEC_STATEMENT,
        timeout:   int | None = None,
    ) -> dict:
        """
        Execute a Python script inside UE.
        Returns the raw command_result data dict from UE.
        Raises RuntimeError / TimeoutError on failure.
        """
        t = timeout if timeout is not None else self.command_timeout
        return self._execute(script, exec_mode=exec_mode, timeout=t)

    def run_ex(self, script: str, timeout: int | None = None) -> dict:
        """
        Like run() but wraps script in try/except and parses UEOS markers.
        Returns: { "ok": bool, "result": Any, "error": str|None, "raw_output": str }
        """
        wrapped = (
            "import traceback as _tb\n"
            "try:\n" +
            "\n".join("    " + line for line in script.splitlines()) + "\n"
            "except Exception as _e:\n"
            "    print('UEOS_ERROR:' + _tb.format_exc().replace('\\n', ' | '))\n"
        )
        raw = self.run(wrapped, timeout=timeout)
        return _parse_exec_result(raw)

    # ── Internal ────────────────────────────────────────────────────────────

    def _discover(self) -> str | None:
        """
        Send multicast ping, return the unreal node_id from the first pong.
        Returns None if no UE instance responds within disc_timeout.
        """
        mcast = _open_multicast_socket(
            self.bind_addr, self.group_ip, self.group_port, self.ttl
        )
        try:
            ping_msg = _make_udp_msg("ping", self.source_id)
            deadline = time.monotonic() + self.disc_timeout
            while time.monotonic() < deadline:
                mcast.sendto(ping_msg, (self.group_ip, self.group_port))
                pong = _recv_json(mcast, "ping")
                if pong and pong.get("type") == "pong":
                    node_id = pong.get("source", "")
                    log.debug(f"UE node found: {node_id}")
                    return node_id
            return None
        finally:
            mcast.close()

    def _execute(self, command: str, exec_mode: str, timeout: int) -> dict:
        """
        Full round-trip: ping → open_connection → accept → command → result → close.
        """
        # ── Step 1: open multicast socket ──────────────────────────────────
        mcast = _open_multicast_socket(
            self.bind_addr, self.group_ip, self.group_port, self.ttl
        )
        try:
            # ── Step 2: ping to get the node ID ────────────────────────────
            node_id = None
            ping_msg = _make_udp_msg("ping", self.source_id)
            deadline = time.monotonic() + self.disc_timeout
            while time.monotonic() < deadline:
                mcast.sendto(ping_msg, (self.group_ip, self.group_port))
                pong = _recv_json(mcast, "ping")
                if pong and pong.get("type") == "pong":
                    node_id = pong.get("source", "")
                    break

            if not node_id:
                raise RuntimeError(
                    "No Unreal Engine instance found via Remote Execution multicast. "
                    "Check: Python Editor Script Plugin enabled, "
                    "Project Settings → Plugins → Python → Enable Remote Execution ✅, "
                    "Multicast Bind Address = 0.0.0.0 (or 127.0.0.1)"
                )

            # ── Step 3: create TCP server socket (WE listen, UE connects) ──
            cmd_addr = _get_free_port()
            cmd_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            cmd_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            cmd_sock.bind(cmd_addr)
            cmd_sock.settimeout(2.0)
            cmd_sock.listen()

            # ── Step 4: send open_connection (tells UE our TCP port) ────────
            open_msg = _make_udp_msg(
                "open_connection",
                self.source_id,
                dest=node_id,
                data={"command_ip": cmd_addr[0], "command_port": cmd_addr[1]},
            )
            mcast.sendto(open_msg, (self.group_ip, self.group_port))

            # ── Step 5: accept UE's incoming TCP connection ─────────────────
            try:
                cmd_conn, _ = cmd_sock.accept()
            except socket.timeout:
                cmd_sock.close()
                raise RuntimeError(
                    "UE did not connect back on TCP port "
                    f"{cmd_addr[1]} within 2s. "
                    "Verify Remote Execution is enabled and multicast is working."
                )
            finally:
                cmd_sock.close()   # stop listening; we have the connection

            cmd_conn.settimeout(SOCKET_TIMEOUT)

            try:
                # ── Step 6: send command ────────────────────────────────────
                cmd_id = str(uuid.uuid4())
                cmd_msg = _make_udp_msg(
                    "command",
                    self.source_id,
                    dest=node_id,
                    data={
                        "command":    command,
                        "unattended": True,
                        "exec_mode":  exec_mode,
                    },
                )
                cmd_conn.sendto(cmd_msg, cmd_addr)

                # ── Step 7: receive command_result ──────────────────────────
                result = _recv_tcp_json(cmd_conn, "command", float(timeout))
                if result is None:
                    raise TimeoutError(
                        f"No command_result from UE within {timeout}s"
                    )
                return result.get("data", {})

            finally:
                # ── Step 8: close_connection ────────────────────────────────
                try:
                    close_msg = _make_udp_msg(
                        "close_connection", self.source_id, dest=node_id
                    )
                    mcast.sendto(close_msg, (self.group_ip, self.group_port))
                except Exception:
                    pass
                try:
                    cmd_conn.close()
                except Exception:
                    pass

        finally:
            mcast.close()


# ── Result parser ─────────────────────────────────────────────────────────────

def _parse_exec_result(raw: dict) -> dict:
    """Parse UEOS_RESULT / UEOS_ERROR markers from a command_result data dict."""
    output_entries = raw.get("output", [])
    if isinstance(output_entries, list):
        all_output = "\n".join(
            e.get("output", "") for e in output_entries if isinstance(e, dict)
        )
    else:
        all_output = str(output_entries)

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
