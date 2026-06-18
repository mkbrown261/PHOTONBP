"""
remote_execution.py — UE Python Remote Execution client
Clean rewrite based on confirmed UE 5.4 protocol behavior.
"""

from __future__ import annotations

import json
import logging
import socket
import time
import uuid
from typing import Any

log = logging.getLogger("ueos.remote_exec")

# ── Protocol constants ────────────────────────────────────────────────────────
MULTICAST_GROUP_IP   = "239.0.0.1"
MULTICAST_GROUP_PORT = 6766
IP_MULTICAST_TTL     = 0              # 0 = local machine only
SOCKET_TIMEOUT       = 0.5
BUFFER_SIZE          = 2_097_152

PROTOCOL_VERSION = 1
UE_MAGIC         = "ue_py"

EXEC_MODE_EXEC_FILE      = "ExecuteFile"
EXEC_MODE_EXEC_STATEMENT = "ExecuteStatement"
EXEC_MODE_EVAL_STATEMENT = "EvaluateStatement"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_msg(msg_type: str, source: str, dest: str = "", data: dict | None = None) -> bytes:
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


def _make_multicast_socket() -> socket.socket:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, IP_MULTICAST_TTL)
    s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, 1)
    s.bind(("0.0.0.0", MULTICAST_GROUP_PORT))
    mreq = socket.inet_aton(MULTICAST_GROUP_IP) + socket.inet_aton("0.0.0.0")
    s.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
    s.settimeout(SOCKET_TIMEOUT)
    return s


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("", 0))
        return s.getsockname()[1]


def _recv_pong(sock: socket.socket, our_source: str, deadline: float) -> str | None:
    """
    Read UDP datagrams until we get a pong from UE (not our own echo).
    Returns the UE node_id (source field of pong) or None on timeout.
    """
    buf = b""
    while time.monotonic() < deadline:
        try:
            data, _ = sock.recvfrom(BUFFER_SIZE)
        except socket.timeout:
            return None
        buf += data
        try:
            msg = json.loads(buf)
            buf = b""
        except json.JSONDecodeError:
            continue

        # Skip our own messages
        if msg.get("source") == our_source:
            continue
        if msg.get("magic") != UE_MAGIC:
            continue
        if msg.get("type") == "pong":
            return msg.get("source", "")
    return None


def _recv_tcp(conn: socket.socket, skip_type: str, timeout: float) -> dict | None:
    conn.settimeout(timeout)
    buf = b""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            chunk = conn.recv(BUFFER_SIZE)
        except socket.timeout:
            break
        if not chunk:
            break
        buf += chunk
        try:
            msg = json.loads(buf)
            buf = b""
        except json.JSONDecodeError:
            continue
        if msg.get("type") == skip_type:
            continue
        return msg
    return None


# ── Main client ───────────────────────────────────────────────────────────────

class UnrealRemoteExecution:
    """
    Synchronous UE Python Remote Execution client for UE 5.4.
    """

    def __init__(self, command_timeout: int = 30, discovery_timeout: float = 5.0):
        self.command_timeout  = command_timeout
        self.disc_timeout     = discovery_timeout
        self.source_id        = str(uuid.uuid4())

    def ping(self) -> bool:
        try:
            return self._discover() is not None
        except Exception as e:
            log.debug(f"ping failed: {e}")
            return False

    def run(self, script: str, exec_mode: str = EXEC_MODE_EXEC_STATEMENT,
            timeout: int | None = None) -> dict:
        t = timeout if timeout is not None else self.command_timeout
        return self._execute(script, exec_mode=exec_mode, timeout=t)

    def run_ex(self, script: str, timeout: int | None = None) -> dict:
        wrapped = (
            "import traceback as _tb\n"
            "try:\n" +
            "\n".join("    " + line for line in script.splitlines()) + "\n"
            "except Exception as _e:\n"
            "    print('UEOS_ERROR:' + _tb.format_exc().replace('\\n', ' | '))\n"
        )
        raw = self.run(wrapped, timeout=timeout)
        return _parse_exec_result(raw)

    # ── Internal ──────────────────────────────────────────────────────────────

    def _discover(self) -> str | None:
        sock = _make_multicast_socket()
        try:
            ping_msg = _make_msg("ping", self.source_id)
            deadline = time.monotonic() + self.disc_timeout
            while time.monotonic() < deadline:
                sock.sendto(ping_msg, (MULTICAST_GROUP_IP, MULTICAST_GROUP_PORT))
                node_id = _recv_pong(sock, self.source_id, min(deadline, time.monotonic() + 1.0))
                if node_id:
                    return node_id
            return None
        finally:
            sock.close()

    def _execute(self, command: str, exec_mode: str, timeout: int) -> dict:
        sock = _make_multicast_socket()
        try:
            # ── 1. Discover UE node ───────────────────────────────────────────
            ping_msg = _make_msg("ping", self.source_id)
            deadline = time.monotonic() + self.disc_timeout
            node_id = None
            while time.monotonic() < deadline:
                sock.sendto(ping_msg, (MULTICAST_GROUP_IP, MULTICAST_GROUP_PORT))
                node_id = _recv_pong(sock, self.source_id, min(deadline, time.monotonic() + 1.0))
                if node_id:
                    break

            if not node_id:
                raise RuntimeError(
                    "No Unreal Engine instance found.\n"
                    "Check: Edit > Project Settings > Plugins > Python > Enable Remote Execution = ON"
                )

            # ── 2. Open TCP server (we listen, UE connects back) ──────────────
            port = _free_port()
            tcp_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            tcp_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            tcp_server.bind(("127.0.0.1", port))
            tcp_server.settimeout(5.0)
            tcp_server.listen(1)

            # ── 3. Tell UE our TCP port ───────────────────────────────────────
            open_msg = _make_msg(
                "open_connection", self.source_id, dest=node_id,
                data={"command_ip": "127.0.0.1", "command_port": port},
            )
            sock.sendto(open_msg, (MULTICAST_GROUP_IP, MULTICAST_GROUP_PORT))

            # ── 4. Accept UE's connection ─────────────────────────────────────
            try:
                conn, _ = tcp_server.accept()
            except socket.timeout:
                tcp_server.close()
                raise RuntimeError(
                    f"UE did not connect back on TCP port {port} within 5s.\n"
                    "Remote Execution may not be enabled in Project Settings."
                )
            finally:
                tcp_server.close()

            try:
                # ── 5. Send command ───────────────────────────────────────────
                cmd_msg = _make_msg(
                    "command", self.source_id, dest=node_id,
                    data={
                        "command":    command,
                        "unattended": True,
                        "exec_mode":  exec_mode,
                    },
                )
                conn.sendall(cmd_msg)

                # ── 6. Receive result ─────────────────────────────────────────
                result = _recv_tcp(conn, "command", float(timeout))
                if result is None:
                    raise TimeoutError(f"No response from UE within {timeout}s")
                return result.get("data", {})

            finally:
                # ── 7. Close connection ───────────────────────────────────────
                try:
                    close_msg = _make_msg("close_connection", self.source_id, dest=node_id)
                    sock.sendto(close_msg, (MULTICAST_GROUP_IP, MULTICAST_GROUP_PORT))
                except Exception:
                    pass
                try:
                    conn.close()
                except Exception:
                    pass

        finally:
            sock.close()


# ── Result parser ─────────────────────────────────────────────────────────────

def _parse_exec_result(raw: dict) -> dict:
    output_entries = raw.get("output", [])
    if isinstance(output_entries, list):
        all_output = "\n".join(
            e.get("output", "") if isinstance(e, dict) else str(e)
            for e in output_entries
        )
    else:
        all_output = str(output_entries)

    result = {"ok": True, "result": None, "error": None, "output": all_output}

    for line in all_output.replace("\r", "").split("\n"):
        line = line.strip()
        if line.startswith("UEOS_RESULT:"):
            try:
                result["result"] = json.loads(line[len("UEOS_RESULT:"):])
            except Exception:
                result["result"] = line[len("UEOS_RESULT:"):]
        elif line.startswith("UEOS_ERROR:"):
            result["ok"] = False
            result["error"] = line[len("UEOS_ERROR:"):]

    return result
