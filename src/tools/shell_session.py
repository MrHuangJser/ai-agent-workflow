import os
import pty
import select
import subprocess
import uuid
import fcntl
import termios
import tty
from typing import Any, Dict, Optional

from agentscope.tool import ToolResponse
from agentscope.message import TextBlock


_SESSIONS: Dict[str, Dict[str, Any]] = {}


def _safe_cwd(cwd: Optional[str]) -> str:
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    if not cwd:
        return root
    abs_cwd = os.path.abspath(os.path.join(root, cwd))
    if not abs_cwd.startswith(root):
        return root
    return abs_cwd


def _set_nonblocking(fd: int) -> None:
    flags = fcntl.fcntl(fd, fcntl.F_GETFL)
    fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)


def _spawn_pty(command: str, cwd: Optional[str], env: Optional[Dict[str, str]]):
    master_fd, slave_fd = pty.openpty()
    # Optional: set raw mode to avoid local echo complications
    try:
        tty.setraw(master_fd)
    except Exception:
        pass
    _set_nonblocking(master_fd)

    proc_env = os.environ.copy()
    proc_env.setdefault("CI", "1")
    if env:
        for k, v in env.items():
            if isinstance(k, str) and isinstance(v, str):
                proc_env[k] = v

    proc = subprocess.Popen(
        command,
        shell=True,
        cwd=_safe_cwd(cwd),
        stdin=slave_fd,
        stdout=slave_fd,
        stderr=slave_fd,
        env=proc_env,
        close_fds=True,
        start_new_session=True,
    )
    # Close slave in parent
    try:
        os.close(slave_fd)
    except Exception:
        pass
    return proc, master_fd


def _read_available(master_fd: int, timeout: float = 0.2, max_bytes: int = 8192) -> str:
    out_chunks: list[bytes] = []
    remaining = max_bytes
    # Wait until readable or timeout, then drain what's available quickly
    r, _, _ = select.select([master_fd], [], [], timeout)
    if not r:
        return ""
    while remaining > 0:
        try:
            chunk = os.read(master_fd, min(remaining, 1024))
            if not chunk:
                break
            out_chunks.append(chunk)
            remaining -= len(chunk)
            # Briefly check if more data is ready without blocking
            r, _, _ = select.select([master_fd], [], [], 0)
            if not r:
                break
        except BlockingIOError:
            break
        except OSError:
            break
    return b"".join(out_chunks).decode("utf-8", errors="replace")


async def shell_session_start(
    command: str,
    cwd: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
) -> ToolResponse:
    try:
        proc, master_fd = _spawn_pty(command, cwd, env)
        sid = f"sh_{uuid.uuid4().hex[:8]}"
        _SESSIONS[sid] = {
            "proc": proc,
            "fd": master_fd,
            "cwd": _safe_cwd(cwd),
        }
        initial = _read_available(master_fd, timeout=0.3)
        payload = {
            "ok": True,
            "session_id": sid,
            "pid": proc.pid,
            "started": True,
            "initial_output": initial,
            "closed": False,
        }
        return ToolResponse(content=[TextBlock(type="text", text=_to_json(payload))])
    except Exception as e:
        return ToolResponse(content=[TextBlock(type="text", text=_to_json({
            "ok": False,
            "error": str(e),
        }))])


async def shell_session_read(
    session_id: str,
    timeout: float = 0.5,
    max_bytes: int = 8192,
) -> ToolResponse:
    s = _SESSIONS.get(session_id)
    if not s:
        return ToolResponse(content=[TextBlock(type="text", text=_to_json({
            "ok": False,
            "error": "session_not_found",
        }))])
    proc = s["proc"]
    fd = s["fd"]
    text = _read_available(fd, timeout=timeout, max_bytes=max_bytes)
    closed = (proc.poll() is not None)
    exit_code = proc.returncode if closed else None
    payload = {
        "ok": True,
        "session_id": session_id,
        "closed": closed,
        "exit_code": exit_code,
        "output": text,
    }
    return ToolResponse(content=[TextBlock(type="text", text=_to_json(payload))])


async def shell_session_send(
    session_id: str,
    data: str,
    append_newline: bool = True,
) -> ToolResponse:
    s = _SESSIONS.get(session_id)
    if not s:
        return ToolResponse(content=[TextBlock(type="text", text=_to_json({
            "ok": False,
            "error": "session_not_found",
        }))])
    fd = s["fd"]
    if append_newline and not data.endswith("\n"):
        data = data + "\n"
    try:
        os.write(fd, data.encode("utf-8"))
        return ToolResponse(content=[TextBlock(type="text", text=_to_json({
            "ok": True,
            "session_id": session_id,
            "bytes": len(data),
        }))])
    except Exception as e:
        return ToolResponse(content=[TextBlock(type="text", text=_to_json({
            "ok": False,
            "error": str(e),
        }))])


async def shell_session_close(session_id: str) -> ToolResponse:
    s = _SESSIONS.pop(session_id, None)
    if not s:
        return ToolResponse(content=[TextBlock(type="text", text=_to_json({
            "ok": False,
            "error": "session_not_found",
        }))])
    proc = s["proc"]
    fd = s["fd"]
    try:
        if proc.poll() is None:
            proc.terminate()
        try:
            os.close(fd)
        except Exception:
            pass
        return ToolResponse(content=[TextBlock(type="text", text=_to_json({
            "ok": True,
            "closed": True,
            "exit_code": proc.returncode,
        }))])
    except Exception as e:
        return ToolResponse(content=[TextBlock(type="text", text=_to_json({
            "ok": False,
            "error": str(e),
        }))])


def _to_json(obj: Dict[str, Any]) -> str:
    import json
    return json.dumps(obj, ensure_ascii=False)

