
# serial_worker.py |  blendixserial Worker Process
# ------------------------------------------------
# Runs as a subprocess launched by Blender.
# Owns the serial port entirely.
# Exposes a TCP server on localhost so Blender can send/receive JSON messages.

# Message format (both directions): one JSON object per line, UTF-8, newline-terminated.

# Blender | Worker commands:
#     {"cmd": "CONNECT",    "port": "COM3", "baud": 9600, "format": "CSV"}
#     {"cmd": "DISCONNECT"}
#     {"cmd": "SEND",       "data": "1.0,2.0,3.0;"}          # CSV string
#     {"cmd": "SEND_BYTES", "data": "<hex string>"}           # Protocol binary
#     {"cmd": "SET_MODE",   "mode": "receive"|"send"|"both"}
#     {"cmd": "SET_FORMAT", "format": "CSV"|"PROTOCOL"}
#     {"cmd": "PING"}

# Worker | Blender events:
#     {"tag": "CSV",      "data": "12.5,0.0,3.2"}
#     {"tag": "PROTOCOL", "data": "<hex string>"}
#     {"tag": "STATUS",   "status": "connected"|"disconnected"|"error", "msg": "..."}
#     {"tag": "PONG"}
#     {"tag": "LOG",      "level": "info"|"error", "msg": "..."}


import sys
import json
import socket
import serial
import serial.tools.list_ports
import struct
import time
import select



#  Helpers
def send_event(conn, obj: dict):
    """Send a JSON line to Blender over the socket."""
    try:
        line = json.dumps(obj) + "\n"
        conn.sendall(line.encode("utf-8"))
    except Exception:
        pass


def log(conn, level: str, msg: str):
    send_event(conn, {"tag": "LOG", "level": level, "msg": msg})



#  Serial port helpers
def list_ports():
    return [p.device for p in serial.tools.list_ports.comports()]


def is_valid_csv(data: str) -> bool:
    if not data:
        return False
    parts = data.split(";")
    numerical_part = parts[0].strip()
    if numerical_part:
        try:
            list(map(float, numerical_part.split(",")))
        except ValueError:
            return False
    return True



#  Worker state
class WorkerState:
    def __init__(self):
        self.ser: serial.Serial | None = None
        self.mode: str = "receive"          # send | receive | both
        self.protocol_format: str = "CSV"   # CSV | PROTOCOL
        self.rx_buffer = bytearray()
        self.send_queue: list = []          # pending outbound items



#  Serial I/O
def do_receive(state: WorkerState, conn):
    ser = state.ser
    if ser is None or not ser.is_open:
        return

    if state.protocol_format == "PROTOCOL":
        if ser.in_waiting:
            state.rx_buffer.extend(ser.read(ser.in_waiting))

        while True:
            if len(state.rx_buffer) < 5:
                break

            if state.rx_buffer[0] != 0x02:
                state.rx_buffer.pop(0)
                continue

            payload_len = struct.unpack(">H", state.rx_buffer[3:5])[0]
            full_len = 5 + payload_len + 2

            if len(state.rx_buffer) < full_len:
                break

            full_msg = state.rx_buffer[:full_len]

            if full_msg[-1] != 0x03:
                state.rx_buffer.pop(0)
                continue

            # Checksum
            calc = 0
            for b in full_msg[1:-2]:
                calc ^= b

            if calc != full_msg[-2]:
                log(conn, "error", "[RX-PROTOCOL] Checksum mismatch")
                state.rx_buffer.pop(0)
                continue

            send_event(conn, {"tag": "PROTOCOL", "data": full_msg.hex()})
            state.rx_buffer = state.rx_buffer[full_len:]

    else:  # CSV
        if ser.in_waiting:
            try:
                line = ser.readline().decode(errors="replace").rstrip()
                if line and is_valid_csv(line):
                    send_event(conn, {"tag": "CSV", "data": line})
                elif line:
                    log(conn, "error", f"[RX-CSV] Invalid: {line}")
            except Exception as e:
                log(conn, "error", f"[RX-CSV] Read error: {e}")


def do_send(state: WorkerState, conn):
    if not state.send_queue:
        return
    ser = state.ser
    if ser is None or not ser.is_open:
        state.send_queue.clear()
        return

    for item in state.send_queue:
        try:
            if isinstance(item, bytes):
                ser.write(item)
            else:
                to_write = item if item.endswith("\n") else item + "\n"
                ser.write(to_write.encode("utf-8"))
            ser.flush()
        except serial.SerialException as e:
            log(conn, "error", f"[TX] Send failed: {e}")
    state.send_queue.clear()



#  Command handler
def handle_command(cmd_obj: dict, state: WorkerState, conn) -> bool:
    cmd = cmd_obj.get("cmd", "")

    if cmd == "PING":
        send_event(conn, {"tag": "PONG"})

    elif cmd == "CONNECT":
        port   = cmd_obj.get("port", "")
        baud   = int(cmd_obj.get("baud", 9600))
        fmt    = cmd_obj.get("format", "CSV")
        state.protocol_format = fmt

        # Close previous connection if any
        if state.ser and state.ser.is_open:
            try:
                state.ser.close()
            except Exception:
                pass

        try:
            state.ser = serial.Serial(port, baud, timeout=0)   # non-blocking
            send_event(conn, {"tag": "STATUS", "status": "connected",
                              "msg": f"Connected to {port} @ {baud}"})
            log(conn, "info", f"[SERIAL] Connected → {port} @ {baud}")
        except serial.SerialException as e:
            state.ser = None
            send_event(conn, {"tag": "STATUS", "status": "error",
                              "msg": str(e)})
            log(conn, "error", f"[SERIAL] Connect failed: {e}")

    elif cmd == "DISCONNECT":
        if state.ser and state.ser.is_open:
            try:
                state.ser.flush()
                state.ser.close()
            except Exception:
                pass
        state.ser = None
        state.rx_buffer.clear()
        state.send_queue.clear()
        send_event(conn, {"tag": "STATUS", "status": "disconnected",
                          "msg": "Disconnected"})
        log(conn, "info", "[SERIAL] Disconnected")

    elif cmd == "SET_MODE":
        mode = cmd_obj.get("mode", "receive")
        if mode in ("send", "receive", "both"):
            state.mode = mode
            log(conn, "info", f"[WORKER] Mode → {mode}")

    elif cmd == "SET_FORMAT":
        fmt = cmd_obj.get("format", "CSV")
        if fmt in ("CSV", "PROTOCOL"):
            state.protocol_format = fmt
            log(conn, "info", f"[WORKER] Format → {fmt}")

    elif cmd == "SEND":
        # CSV string
        data = cmd_obj.get("data", "")
        if data:
            state.send_queue.append(data)

    elif cmd == "SEND_BYTES":
        # Binary protocol as hex string
        hex_data = cmd_obj.get("data", "")
        if hex_data:
            try:
                state.send_queue.append(bytes.fromhex(hex_data))
            except ValueError:
                log(conn, "error", "[TX] Invalid hex data")

    elif cmd == "SHUTDOWN":
        return False

    return True



#  Main loop
def run_server(port: int):
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("127.0.0.1", port))
    server.listen(1)
    server.setblocking(False)

    print(f"[WORKER] Listening on 127.0.0.1:{port}", flush=True)

    state = WorkerState()
    conn = None
    recv_buf = ""   # incomplete line buffer from socket

    while True:
        # Accept new connection from Blender
        if conn is None:
            readable, _, _ = select.select([server], [], [], 0.05)
            if readable:
                conn, addr = server.accept()
                conn.setblocking(False)
                print(f"[WORKER] Blender connected from {addr}", flush=True)
            continue  # nothing else to do without a connection

        #Read commands from Blender (non-blocking)
        try:
            readable, _, _ = select.select([conn], [], [], 0)
            if readable:
                chunk = conn.recv(4096).decode("utf-8", errors="replace")
                if not chunk:
                    # Blender closed the connection
                    print("[WORKER] Blender disconnected", flush=True)
                    conn.close()
                    conn = None
                    # Also close serial port cleanly
                    if state.ser and state.ser.is_open:
                        state.ser.close()
                    state.ser = None
                    continue

                recv_buf += chunk
                while "\n" in recv_buf:
                    line, recv_buf = recv_buf.split("\n", 1)
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        cmd_obj = json.loads(line)
                        if not handle_command(cmd_obj, state, conn):
                            # SHUTDOWN received
                            conn.close()
                            server.close()
                            return
                    except json.JSONDecodeError:
                        log(conn, "error", f"[WORKER] Bad JSON: {line}")

        except (ConnectionResetError, OSError):
            conn = None
            continue

        #Serial I/O
        if state.ser and state.ser.is_open:
            if state.mode in ("receive", "both"):
                do_receive(state, conn)
            if state.mode in ("send", "both"):
                do_send(state, conn)
        else:
            time.sleep(0.005)


if __name__ == "__main__":
    tcp_port = int(sys.argv[1]) if len(sys.argv) > 1 else 50007
    run_server(tcp_port)