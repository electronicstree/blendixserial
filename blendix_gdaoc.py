# blendixserial (subprocess + TCP edition)
# Data routing between the worker subprocess and Blender scene objects.

import bpy
import math
import struct
from bpy.app.handlers import persistent

from .blendix_connection import worker_manager
from .serial_log import serial_logger



#  Parsing helpers  
def parse_serial_data(serial_data: str):
    if not serial_data:
        return [], ""

    numerical_values = []
    text_data = ""

    if ";" in serial_data:
        parts = serial_data.split(";", 1)
        numerical_part = parts[0].strip()
        if numerical_part:
            try:
                numerical_values = list(map(float, numerical_part.split(",")))
            except ValueError:
                pass
        if len(parts) > 1:
            text_data = parts[1].strip()

    elif serial_data.startswith(";"):
        text_data = serial_data[1:].strip()

    return numerical_values, text_data


def parse_protocol_message(full_msg_hex: str):
    try:
        full_msg = bytes.fromhex(full_msg_hex)
    except ValueError:
        serial_logger.error("[PARSE] Invalid hex in PROTOCOL event")
        return [], ""

    try:
        if len(full_msg) < 7 or full_msg[0] != 0x02 or full_msg[-1] != 0x03:
            return [], ""

        msg_type  = full_msg[1]
        obj_count = full_msg[2]
        payload_len = struct.unpack(">H", full_msg[3:5])[0]

        payload = full_msg[5:5 + payload_len]
        received_checksum = full_msg[5 + payload_len]

        calc = 0
        for b in full_msg[1:5 + payload_len]:
            calc ^= b
        if calc != received_checksum:
            serial_logger.error("[PARSE] Checksum mismatch")
            return [], ""

        numerical = []
        text = ""
        pos = 0

        if msg_type in (1, 3):
            for _ in range(obj_count):
                if pos + 3 > len(payload):
                    break
                obj_id, bitmask = struct.unpack(">BH", payload[pos:pos + 3])
                pos += 3
                for bit in range(9):
                    if bitmask & (1 << bit):
                        if pos + 4 > len(payload):
                            break
                        val = struct.unpack(">f", payload[pos:pos + 4])[0]
                        numerical.append(val)
                        pos += 4
                    else:
                        numerical.append(None)

        if msg_type in (2, 3):
            if msg_type == 3 and pos < len(payload):
                text_len = payload[pos]
                pos += 1
                if pos + text_len <= len(payload):
                    text = payload[pos:pos + text_len].decode("utf-8", errors="replace")
            elif msg_type == 2:
                text = payload.decode("utf-8", errors="replace")

        serial_logger.data(
            f"[PARSED] msg_type={msg_type}, obj_count={obj_count}, "
            f"values={numerical}, text='{text}'"
        )
        return numerical, text

    except Exception as e:
        serial_logger.error(f"[PARSE] Protocol parse error → {e}")
        return [], ""




_last_numerical_data = None
_last_text_data = None


#  Receive timer 
@persistent
def timer_func():

    if not bpy.context or not bpy.context.scene:
        return 0.1

    global _last_numerical_data, _last_text_data

    scene = bpy.context.scene
    worker_manager.update_settings(bpy.context.window_manager)
    events = worker_manager.poll_events()
    latest_numerical = None
    latest_text = None

    for evt in events:
        tag = evt.get("tag", "")

        if tag == "STATUS":
            status = evt.get("status", "")
            msg    = evt.get("msg", "")
            serial_logger.event(f"[STATUS] {status}: {msg}")
            wm = bpy.context.window_manager          # runtime state on WindowManager
            if status == "connected":
                wm.serial_is_connected      = True
                wm.serial_connection_status = "Connected"
                serial_logger.event(f"[CONNECTION] {msg}")
            elif status == "disconnected":
                wm.serial_is_connected      = False
                wm.serial_connection_status = "Disconnected"
                serial_logger.event(f"[CONNECTION] Disconnected: {msg}")
            elif status == "error":
                wm.serial_is_connected      = False
                wm.serial_connection_status = "Error"
                serial_logger.error(f"[CONNECTION] Error: {msg}")

        elif tag in ("CSV", "PROTOCOL") and not worker_manager.pause_movement:
            # Only parse data events when movement is allowed
            if tag == "CSV":
                numerical_data, text_data = parse_serial_data(evt.get("data", ""))
            else:
                numerical_data, text_data = parse_protocol_message(evt.get("data", ""))
            latest_numerical = numerical_data
            latest_text      = text_data

    if latest_numerical is not None or latest_text is not None:
        numerical_data = latest_numerical or []
        text_data      = latest_text      or ""

        if (numerical_data != _last_numerical_data or
                text_data != _last_text_data):
            process_data(scene, numerical_data, text_data)
            _last_numerical_data = numerical_data
            _last_text_data      = text_data

    return scene.updateSceneDelay



#  Send helpers
def send_serial_data():
    if not bpy.context or not bpy.context.scene:
        return
    scene = bpy.context.scene

    if not (
        worker_manager.is_connected
        and not worker_manager.pause_movement
        and worker_manager.mode in ("send", "both")
    ):
        return

    wm = bpy.context.window_manager
    try:
        if wm.serial_thread_format == "CSV":          
            parts = []
            decimals = scene.send_decimal_places
            for item in scene.send_object_collection:
                obj = item.sel_object
                if obj:
                    parts.append(format_data_for_object(obj, item, decimals))
            if parts:
                data_to_send = ", ".join(parts) + ";"
                worker_manager.send(data_to_send)

        else:  # PROTOCOL
            obj_data = []
            text_to_send = ""

            for i, item in enumerate(scene.send_object_collection):
                obj = item.sel_object
                if obj:
                    bitmask, values = get_bitmask_and_values(item, obj)
                    if bitmask != 0:
                        obj_data.append((i, bitmask, values))

            if obj_data or text_to_send:
                if obj_data and not text_to_send:
                    msg_type = 1
                elif not obj_data and text_to_send:
                    msg_type = 2
                else:
                    msg_type = 3

                binary_msg = build_protocol_message(msg_type, obj_data, text_to_send)
                serial_logger.data(f"[TX] Protocol type {msg_type} → {len(binary_msg)} bytes")
                worker_manager.send(binary_msg)
            else:
                serial_logger.data("[TX] No protocol data to send")

    except Exception as e:
        fmt = "CSV" if wm.serial_thread_format == "CSV" else "Protocol"  
        serial_logger.error(f"[TX] {fmt} send error → {e}")
        worker_manager.disconnect()


@persistent
def send_timer_func():
    # guard bpy.context for the same reasons as timer_func.
    if not bpy.context or not bpy.context.scene:
        return 0.1
    if bpy.context.scene.send_data_method == "TIMER":
        send_serial_data()
    return bpy.context.scene.updateSceneDelay


@persistent
def on_frame_change_post(scene):
    if scene.send_data_method != "KEYFRAME":
        return
    interval = getattr(scene, "frame_skip_interval", 1)
    if interval == 0 or scene.frame_current % interval == 0:
        send_serial_data()



#  Scene update 
def process_data(scene, numerical_data, text_data):
    if numerical_data:
        update_objects(scene, numerical_data)
        update_axis_text_objects(scene, numerical_data)
    if text_data:
        update_received_text(scene, text_data)


def update_objects(scene, numerical_data):
    for i, item in enumerate(scene.custom_object_collection):
        if not item.sel_object:
            continue
        base = i * 9
        if item.use_location and base + 2 < len(numerical_data):
            update_location(item.sel_object, item.selected_axes_location, numerical_data, base)
        if item.use_rotation and base + 5 < len(numerical_data):
            update_rotation(item.sel_object, item.selected_axes_rotation, numerical_data, base + 3)
        if item.use_scale and base + 8 < len(numerical_data):
            update_scale(item.sel_object, item.selected_axes_scale, numerical_data, base + 6)


def update_location(obj, selected_axes, numerical_data, base_index):
    if base_index < len(numerical_data):
        val = numerical_data[base_index]
        if val is not None and "X" in selected_axes:
            obj.location.x = val
    if base_index + 1 < len(numerical_data):
        val = numerical_data[base_index + 1]
        if val is not None and "Y" in selected_axes:
            obj.location.y = val
    if base_index + 2 < len(numerical_data):
        val = numerical_data[base_index + 2]
        if val is not None and "Z" in selected_axes:
            obj.location.z = val


def update_rotation(obj, selected_axes, numerical_data, base_index):
    if base_index < len(numerical_data):
        val = numerical_data[base_index]
        if val is not None and "X" in selected_axes:
            obj.rotation_euler.x = val / 360 * 2 * math.pi
    if base_index + 1 < len(numerical_data):
        val = numerical_data[base_index + 1]
        if val is not None and "Y" in selected_axes:
            obj.rotation_euler.y = val / 360 * 2 * math.pi
    if base_index + 2 < len(numerical_data):
        val = numerical_data[base_index + 2]
        if val is not None and "Z" in selected_axes:
            obj.rotation_euler.z = val / 360 * 2 * math.pi


def update_scale(obj, selected_axes, numerical_data, base_index):
    if base_index < len(numerical_data):
        val = numerical_data[base_index]
        if val is not None and "X" in selected_axes:
            obj.scale.x = val
    if base_index + 1 < len(numerical_data):
        val = numerical_data[base_index + 1]
        if val is not None and "Y" in selected_axes:
            obj.scale.y = val
    if base_index + 2 < len(numerical_data):
        val = numerical_data[base_index + 2]
        if val is not None and "Z" in selected_axes:
            obj.scale.z = val


def update_axis_text_objects(scene, numerical_data):
    for i, item in enumerate(scene.custom_object_collection):
        if item.text_object_axis and item.text_object_axis.type == "FONT":
            axis_text = build_axis_text(scene, item, numerical_data, i)
            item.text_object_axis.data.body = axis_text


def update_received_text(scene, text_data):
    if text_data:
        received_text_obj = scene.received_text
        if received_text_obj and received_text_obj.type == "FONT":
            received_text_obj.data.body = text_data


def build_axis_text(scene, item, numerical_data, index):
    parts = []
    base = index * 9
    if base >= len(numerical_data):
        return "No data"

    use_newline = scene.axis_text_newline
    sep = "\n" if use_newline else " | "

    def add_prop(label, use_flag, show_text_flag, axes_enum, offset):
        if not use_flag or not show_text_flag:
            return
        mode = scene.axis_text_mode
        axis_map = [("X", 0), ("Y", 1), ("Z", 2)]

        if mode == "GROUP":
            vals = []
            for axis_name, axis_offset in axis_map:
                if axis_name in axes_enum and base + offset + axis_offset < len(numerical_data):
                    val = numerical_data[base + offset + axis_offset]
                    if val is not None:
                        vals.append(f"{val:.2f}")
            if vals:
                parts.append(" ".join(vals))

        elif mode == "AXIS":
            for axis_name, axis_offset in axis_map:
                if axis_name in axes_enum and base + offset + axis_offset < len(numerical_data):
                    val = numerical_data[base + offset + axis_offset]
                    if val is not None:
                        parts.append(f"{val:.2f}")

    add_prop("Loc", item.use_location, item.show_text_location, item.selected_axes_location, 0)
    add_prop("Rot", item.use_rotation, item.show_text_rotation, item.selected_axes_rotation, 3)
    add_prop("Sca", item.use_scale,    item.show_text_scale,    item.selected_axes_scale,    6)

    return sep.join(parts) if parts else "No text enabled"


#  CSV / Protocol build helpers 
def format_data_for_object(obj, item, decimals):
    #  decimals passed in by the caller (who already holds scene)
    if obj is None:
        return "0.00,0.00,0.00,0.00,0.00,0.00,0.00,0.00,0.00"
    values = [0.0] * 9
    if item.send_location:
        if "X" in item.send_axes_location: values[0] = obj.location.x
        if "Y" in item.send_axes_location: values[1] = obj.location.y
        if "Z" in item.send_axes_location: values[2] = obj.location.z
    if item.send_rotation:
        rot_deg = [math.degrees(a) for a in obj.rotation_euler]
        if "X" in item.send_axes_rotation: values[3] = rot_deg[0]
        if "Y" in item.send_axes_rotation: values[4] = rot_deg[1]
        if "Z" in item.send_axes_rotation: values[5] = rot_deg[2]
    if item.send_scale:
        if "X" in item.send_axes_scale: values[6] = obj.scale.x
        if "Y" in item.send_axes_scale: values[7] = obj.scale.y
        if "Z" in item.send_axes_scale: values[8] = obj.scale.z
    return ",".join(f"{v:.{decimals}f}" for v in values)


def get_bitmask_and_values(item, obj):
    bitmask = 0
    values  = []
    if item.send_location:
        if "X" in item.send_axes_location: bitmask |= 1 << 0; values.append(obj.location.x)
        if "Y" in item.send_axes_location: bitmask |= 1 << 1; values.append(obj.location.y)
        if "Z" in item.send_axes_location: bitmask |= 1 << 2; values.append(obj.location.z)
    if item.send_rotation:
        rot = [math.degrees(a) for a in obj.rotation_euler]
        if "X" in item.send_axes_rotation: bitmask |= 1 << 3; values.append(rot[0])
        if "Y" in item.send_axes_rotation: bitmask |= 1 << 4; values.append(rot[1])
        if "Z" in item.send_axes_rotation: bitmask |= 1 << 5; values.append(rot[2])
    if item.send_scale:
        if "X" in item.send_axes_scale: bitmask |= 1 << 6; values.append(obj.scale.x)
        if "Y" in item.send_axes_scale: bitmask |= 1 << 7; values.append(obj.scale.y)
        if "Z" in item.send_axes_scale: bitmask |= 1 << 8; values.append(obj.scale.z)
    return bitmask, values


def build_protocol_message(msg_type, obj_data_list, text=""):
    payload = b""
    if msg_type in (1, 3):
        for obj_id, bitmask, values in obj_data_list:
            if not (0 <= obj_id <= 255):
                continue
            bitmask = bitmask & 0xFFFF
            payload += struct.pack("B", obj_id)
            payload += struct.pack(">H", bitmask)
            for v in values:
                payload += struct.pack(">f", v)

    if msg_type in (2, 3):
        text_bytes = text.encode("utf-8")
        if msg_type == 3:
            payload += struct.pack("B", len(text_bytes)) + text_bytes
        else:
            payload += text_bytes

    header = struct.pack(
        ">BBBH",
        0x02,
        msg_type,
        len(obj_data_list) if msg_type in (1, 3) else 0,
        len(payload),
    )

    checksum = 0
    for b in header[1:] + payload:
        checksum ^= b

    return header + payload + bytes([checksum]) + b"\x03"



#  Register timers + handlers
def register():
    if on_frame_change_post not in bpy.app.handlers.frame_change_post:
        bpy.app.handlers.frame_change_post.append(on_frame_change_post)
    if not bpy.app.timers.is_registered(timer_func):
        bpy.app.timers.register(timer_func,persistent=True)
    if not bpy.app.timers.is_registered(send_timer_func):
        bpy.app.timers.register(send_timer_func, persistent=True)


def unregister():
    if on_frame_change_post in bpy.app.handlers.frame_change_post:
        bpy.app.handlers.frame_change_post.remove(on_frame_change_post)
    if bpy.app.timers.is_registered(timer_func):
        bpy.app.timers.unregister(timer_func)
    if bpy.app.timers.is_registered(send_timer_func):
        bpy.app.timers.unregister(send_timer_func)