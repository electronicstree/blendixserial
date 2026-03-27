import bpy
from .blendix_connection import serial_thread, serial_connection
import math
import serial
import struct
from bpy.app.handlers import persistent
from .debug_manager import debug_manager


def timer_func():
    if not hasattr(timer_func, "last_numerical_data"):
        timer_func.last_numerical_data = None
    if not hasattr(timer_func, "last_text_data"):
        timer_func.last_text_data = None

    if serial_connection._serial_connection is not None and not serial_thread.pause_movement:
        latest_data = None
        while not serial_thread.data_queue.empty():
            latest_data = serial_thread.get_data_from_queue()  
            
            if latest_data:
                # Route based on tag
                if isinstance(latest_data, tuple) and len(latest_data) == 2:
                    tag, raw = latest_data
                    
                    if tag == 'PROTOCOL':
                        numerical_data, text_data = serial_thread.parse_protocol_message(raw)
                    elif tag == 'CSV':
                        numerical_data, text_data = serial_thread.parse_serial_data(raw)
                    else:
                        numerical_data, text_data = [], ""
                        debug_manager.error(f"[RX] Unknown queue tag: {tag}")
                else:
                    # Old-style direct data
                    if isinstance(latest_data, tuple) and len(latest_data) == 2:
                        numerical_data, text_data = latest_data
                    elif isinstance(latest_data, str):
                        numerical_data, text_data = serial_thread.parse_serial_data(latest_data)
                    else:
                        numerical_data, text_data = [], ""
                
                # duplicate check + process
                if numerical_data != timer_func.last_numerical_data or text_data != timer_func.last_text_data:
                    process_data(bpy.context, numerical_data, text_data)

                    timer_func.last_numerical_data = numerical_data
                    timer_func.last_text_data = text_data

    return bpy.context.scene.updateSceneDelay


# Timer + Keyframe Shared 
def send_serial_data():
    scene = bpy.context.scene
    
    if (
        serial_connection._serial_connection is not None
        and serial_connection._serial_connection.is_open
        and not serial_thread.pause_movement
        and serial_thread.mode in ['send', 'both']
    ):
        
        try:
            if scene.protocol_format == 'CSV':
                parts = []
                for item in scene.send_object_collection:
                    obj = item.sel_object
                    if obj:
                        part = format_data_for_object(obj, item)
                        parts.append(part)

                if parts:
                    data_to_send = ", ".join(parts) + ";"
                    serial_thread.queue_send_data(data_to_send)
                    
            else:
                obj_data = []
                text_to_send = ""  # future updates 
                
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
                    debug_manager.data(f"[TX] Protocol type {msg_type} → {len(binary_msg)} bytes")
                    serial_thread.queue_send_data(binary_msg)
                    
                else:
                    debug_manager.data("[TX] No protocol data to send")

        except Exception as e:
            debug_manager.error(f"[TX] {'CSV' if scene.protocol_format == 'CSV' else 'Protocol'} send error → {e}")
            serial_connection.disconnect(serial_thread)



def send_timer_func():
    if bpy.context.scene.send_data_method == 'TIMER':
        send_serial_data()
    return bpy.context.scene.updateSceneDelay


@persistent
def on_frame_change_post(scene):
    if scene.send_data_method != 'KEYFRAME':
        return  

    frame_skip_interval = getattr(scene, "frame_skip_interval", 1)
    if frame_skip_interval == 0 or scene.frame_current % frame_skip_interval == 0:
        send_serial_data()



def process_data(context, numerical_data, text_data):
    scene = context.scene
    if numerical_data:
        update_objects(scene, numerical_data)
        update_axis_text_objects(scene, numerical_data)
    if text_data:
        update_received_text(text_data) 


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
        if item.text_object_axis and item.text_object_axis.type == 'FONT':
            axis_text = build_axis_text(item, numerical_data, i)
            item.text_object_axis.data.body = axis_text



def update_received_text(text_data):
    if text_data:
        received_text_obj = bpy.context.scene.received_text
        if received_text_obj and received_text_obj.type == 'FONT':
            received_text_obj.data.body = text_data



def build_axis_text(item, numerical_data, index):
    parts = []
    base = index * 9
    if base >= len(numerical_data):
        return "No data"

    use_newline = bpy.context.scene.axis_text_newline
    sep = "\n" if use_newline else " | "

    def add_prop(label, use_flag, show_text_flag, axes_enum, offset):
        if not use_flag or not show_text_flag:
            return

        mode = bpy.context.scene.axis_text_mode

        axis_map = [
            ("X", 0),
            ("Y", 1),
            ("Z", 2),
        ]

        if mode == 'GROUP':
            vals = []
            for axis_name, axis_offset in axis_map:
                if axis_name in axes_enum and base + offset + axis_offset < len(numerical_data):
                    val = numerical_data[base + offset + axis_offset]
                    if val is not None:
                        vals.append(f"{val:.2f}")
            if vals:
                parts.append(" ".join(vals))

        elif mode == 'AXIS':
            for axis_name, axis_offset in axis_map:
                if axis_name in axes_enum and base + offset + axis_offset < len(numerical_data):
                    val = numerical_data[base + offset + axis_offset]
                    if val is not None:
                        parts.append(f"{val:.2f}")

    add_prop("Loc", item.use_location, item.show_text_location, item.selected_axes_location, 0)
    add_prop("Rot", item.use_rotation, item.show_text_rotation, item.selected_axes_rotation, 3)
    add_prop("Sca", item.use_scale, item.show_text_scale, item.selected_axes_scale, 6)

    return sep.join(parts) if parts else "No text enabled"



def format_data_for_object(obj, item):
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

    decimals = bpy.context.scene.send_decimal_places
    return ",".join(f"{v:.{decimals}f}" for v in values)




def get_bitmask_and_values(item, obj):
    bitmask = 0
    values = []

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
            if not (0 <= bitmask <= 65535):
                bitmask = bitmask & 0xFFFF

            payload += struct.pack("B", obj_id)
            bitmask_bytes = struct.pack(">H", bitmask)
            payload += bitmask_bytes
            for v in values:
                payload += struct.pack(">f", v)

    text_bytes = b""
    if msg_type in (2, 3):
        text_bytes = text.encode('utf-8')
        if msg_type == 3:
            payload += struct.pack("B", len(text_bytes)) + text_bytes
        else:  
            payload += text_bytes

    header = struct.pack(
        ">BBBH",
        0x02,
        msg_type,
        len(obj_data_list) if msg_type in (1,3) else 0,
        len(payload)
    )

    checksum = 0
    for b in header[1:] + payload:
        checksum ^= b

    full_message = header + payload + bytes([checksum]) + b"\x03"
    return full_message



bpy.app.handlers.frame_change_post.append(on_frame_change_post)
bpy.app.timers.register(timer_func, persistent=True)
bpy.app.timers.register(send_timer_func, persistent=True)

