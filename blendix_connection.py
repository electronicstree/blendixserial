# blendixserial (subprocess + TCP edition)

import socket
import json
import subprocess
import sys
import os
import bpy
import select

from .debug_manager import debug_manager


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def list_ports():
    try:
        import serial.tools.list_ports
        return [p.device for p in serial.tools.list_ports.comports()]
    except Exception:
        return []


#  Port-list watcher
_PORT_POLL_INTERVAL = 2.0
_last_known_ports: set = set()


def _port_watcher() -> float | None:
    global _last_known_ports

    current_ports = set(list_ports())
    if current_ports != _last_known_ports:
        _last_known_ports = current_ports

        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == "VIEW_3D":
                    area.tag_redraw()

    return _PORT_POLL_INTERVAL


class WorkerManager:
    def __init__(self):
        self._process: subprocess.Popen | None = None
        self._sock: socket.socket | None = None
        self._tcp_port: int = 0
        self._recv_buf: str = ""

        self.pause_movement: bool = True
        self.mode: str = "receive"
        self.protocol_format: str = "CSV"
        self._connected: bool = False

        self._wants_connect: bool = False
        self._connect_port: str = ""
        self._connect_baud: int = 9600
        self._connect_fmt: str = "CSV"

    @property
    def is_connected(self) -> bool:
        return self._connected and self._sock is not None

    def _worker_script_path(self) -> str:
        return os.path.join(os.path.dirname(__file__), "serial_worker.py")

    def _start_worker(self):
        if self._process is not None:
            return
        self._tcp_port = _find_free_port()
        script = self._worker_script_path()
        env = os.environ.copy()
        try:
            import serial
            env["PYTHONPATH"] = os.path.dirname(os.path.dirname(serial.__file__))
        except ImportError:
            print("[blendixserial] ERROR: PySerial not found.\n")
            return

        self._process = subprocess.Popen(
            [sys.executable, script, str(self._tcp_port)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=env,
        )
        debug_manager.event(f"[WORKER] Subprocess started (PID {self._process.pid}), port {self._tcp_port}")

    def _ensure_socket(self) -> bool:
        if self._sock is not None:
            return True
        if self._process is None:
            self._start_worker()
            return False

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setblocking(False)
            err = sock.connect_ex(("127.0.0.1", self._tcp_port))

            if err not in (0, 10035, 115):
                sock.close()
                return False

            _, writable, _ = select.select([], [sock], [], 0.08)
            if writable:
                self._sock = sock
                debug_manager.event(f"[WORKER] Socket connected → 127.0.0.1:{self._tcp_port}")
                return True
            else:
                sock.close()
                return False

        except Exception as e:
            debug_manager.error(f"[WORKER] Socket creation failed: {e}")
            return False

    def _send_cmd(self, obj: dict):
        if self._sock is None:
            return
        try:
            line = json.dumps(obj) + "\n"
            self._sock.sendall(line.encode("utf-8"))
        except Exception as e:
            debug_manager.error(f"[WORKER] Send failed: {e}")
            self._sock = None

    def poll_events(self) -> list:
        events = []

        self._ensure_socket()

        if self._wants_connect and self._sock is not None:
            cmd = {
                "cmd": "CONNECT",
                "port": self._connect_port,
                "baud": self._connect_baud,
                "format": self._connect_fmt
            }
            self._send_cmd(cmd)
            debug_manager.event(f"[MANAGER] CONNECT sent → {self._connect_port} @ {self._connect_baud} [{self._connect_fmt}]")

        if self._sock is not None:
            try:
                while True:
                    chunk = self._sock.recv(4096)
                    if not chunk:
                        self._sock = None
                        self._connected = False
                        break
                    self._recv_buf += chunk.decode("utf-8", errors="replace")
            except BlockingIOError:
                pass
            except Exception:
                self._sock = None
                self._connected = False

        while "\n" in self._recv_buf:
            line, self._recv_buf = self._recv_buf.split("\n", 1)
            line = line.strip()
            if not line:
                continue
            try:
                evt = json.loads(line)

                if evt.get("tag") == "STATUS":
                    status = evt.get("status", "")
                    msg = evt.get("msg", "")
                    debug_manager.event(f"[STATUS] {status}: {msg}")

                    if status == "connected":
                        self._connected = True
                        self._wants_connect = False
                    elif status in ("disconnected", "error"):
                        self._connected = False

                elif evt.get("tag") == "LOG":
                    msg = evt.get("msg", "")
                    level = evt.get("level", "info")
                    if level == "error":
                        debug_manager.error(msg)
                    else:
                        debug_manager.event(msg)
                    continue

                events.append(evt)

            except json.JSONDecodeError:
                debug_manager.error(f"[WORKER] Bad JSON: {line}")

        return events

    # PUBLIC API
    def connect(self, port: str, baud: int, fmt: str = "CSV"):
        self._start_worker()
        self.protocol_format = fmt

        self._connect_port = port
        self._connect_baud = baud
        self._connect_fmt = fmt
        self._wants_connect = True

        debug_manager.event(f"[MANAGER] Connect REQUESTED → {port} @ {baud} [{fmt}]")
        self._ensure_socket()

    def disconnect(self):
        self._send_cmd({"cmd": "DISCONNECT"})
        self._connected = False
        self._wants_connect = False

    def shutdown(self):
        self._send_cmd({"cmd": "SHUTDOWN"})
        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass
            self._sock = None
        if self._process:
            try:
                self._process.terminate()
                self._process.wait(timeout=1)
            except Exception:
                pass
            self._process = None
        self._connected = False
        self._wants_connect = False

    def set_mode(self, mode: str):
        if mode in ("send", "receive", "both") and self.mode != mode:
            self.mode = mode
            self._send_cmd({"cmd": "SET_MODE", "mode": mode})
            debug_manager.event(f"[MANAGER] Mode → {mode}")

    def update_settings(self, wm):
        """Accept a WindowManager instead of a Scene."""
        fmt = wm.serial_thread_format
        if fmt != self.protocol_format:
            self.protocol_format = fmt
            self._send_cmd({"cmd": "SET_FORMAT", "format": fmt})

    def send(self, data):
        if self._sock is None:
            return
        if isinstance(data, str):
            self._send_cmd({"cmd": "SEND", "data": data})
        elif isinstance(data, bytes):
            self._send_cmd({"cmd": "SEND_BYTES", "data": data.hex()})


# Singleton
worker_manager = WorkerManager()


def ensure_worker():
    if worker_manager._process is None:
        worker_manager._start_worker()


def _update_serial_thread_mode(self, context):
    worker_manager.set_mode(self.serial_thread_modes)


def register():
    bpy.types.WindowManager.serial_thread_modes = bpy.props.EnumProperty(
        name="Serial Thread Mode",
        items=[
            ('send',    "Send",          ""),
            ('receive', "Receive",       ""),
            ('both',    "Bidirectional", ""),
        ],
        default='receive',
        update=_update_serial_thread_mode,
    )
    bpy.types.WindowManager.serial_thread_format = bpy.props.EnumProperty(
        name="Data Format",
        items=[('CSV', "CSV", ""), ('PROTOCOL', "Protocol", "")],
        default='CSV',
    )

    if not bpy.app.timers.is_registered(_port_watcher):
        bpy.app.timers.register(_port_watcher, first_interval=_PORT_POLL_INTERVAL, persistent=True)


def unregister():
    if bpy.app.timers.is_registered(_port_watcher):
        bpy.app.timers.unregister(_port_watcher)

    del bpy.types.WindowManager.serial_thread_modes
    del bpy.types.WindowManager.serial_thread_format
    worker_manager.shutdown()
