import bpy
from bpy.types import PropertyGroup
from bpy.props import (
    EnumProperty,
    BoolProperty,
    StringProperty,
    PointerProperty,
    CollectionProperty,
    FloatProperty,
)
from .blendix_connection import worker_manager, list_ports


def _status_update(self, context):
    for window in context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == "VIEW_3D":
                area.tag_redraw()


def _poll_font_object(self, obj):
    return obj.type == 'FONT'


class SerialConnectionProperties(PropertyGroup):
    port_name: EnumProperty(
        name="Port Name",
        description="Select a serial port",
        items=lambda self, context: (
            [(port, port, "") for port in list_ports()]
            or [("NONE", "No port available", "")]
        ),
    )  # type: ignore

    baud_rate: EnumProperty(
        name="Baud Rate",
        description="Select baud rate for serial communication",
        items=[
            ("4800",   "4800",   ""),
            ("9600",   "9600",   ""),
            ("19200",  "19200",  ""),
            ("31250",  "31250",  ""),
            ("38400",  "38400",  ""),
            ("57600",  "57600",  ""),
            ("74880",  "74880",  ""),
            ("115200", "115200", ""),
            ("230400", "230400", ""),
            ("250000", "250000", ""),
            ("460800", "460800", ""),
        ],
    )  # type: ignore


class DynamicObjectProperties(PropertyGroup):
    sel_object: PointerProperty(
        name="Object",
        type=bpy.types.Object,
    )  # type: ignore

    use_location: BoolProperty(
        name="Location",
        default=True,
        description="Receive Location data",
    )  # type: ignore

    selected_axes_location: EnumProperty(
        name="Location Axes",
        items=[
            ("X",   "X",   ""),
            ("Y",   "Y",   ""),
            ("Z",   "Z",   ""),
            ("XY",  "XY",  ""),
            ("XZ",  "XZ",  ""),
            ("YZ",  "YZ",  ""),
            ("XYZ", "XYZ", ""),
        ],
        default="XYZ",
    )  # type: ignore

    show_text_location: BoolProperty(
        name="Show in Text",
        default=True,
        description="Show Location values in text object",
    )  # type: ignore

    use_rotation: BoolProperty(
        name="Rotation",
        default=False,
        description="Receive Rotation data (degrees)",
    )  # type: ignore

    selected_axes_rotation: EnumProperty(
        name="Rotation Axes",
        items=[
            ("X",   "X",   ""),
            ("Y",   "Y",   ""),
            ("Z",   "Z",   ""),
            ("XY",  "XY",  ""),
            ("XZ",  "XZ",  ""),
            ("YZ",  "YZ",  ""),
            ("XYZ", "XYZ", ""),
        ],
        default="XYZ",
    )  # type: ignore

    show_text_rotation: BoolProperty(
        name="Show in Text",
        default=False,
        description="Show Rotation values in text object",
    )  # type: ignore

    use_scale: BoolProperty(
        name="Scale",
        default=False,
        description="Receive Scale data",
    )  # type: ignore

    selected_axes_scale: EnumProperty(
        name="Scale Axes",
        items=[
            ("X",   "X",   ""),
            ("Y",   "Y",   ""),
            ("Z",   "Z",   ""),
            ("XY",  "XY",  ""),
            ("XZ",  "XZ",  ""),
            ("YZ",  "YZ",  ""),
            ("XYZ", "XYZ", ""),
        ],
        default="XYZ",
    )  # type: ignore

    show_text_scale: BoolProperty(
        name="Show in Text",
        default=False,
        description="Show Scale values in text object",
    )  # type: ignore

    text_object_axis: PointerProperty(
        name="Text Object for Axis",
        type=bpy.types.Object,
        poll=_poll_font_object,
    )  # type: ignore


class MyUIPanelTabs(PropertyGroup):
    tabs: EnumProperty(
        name="Tabs",
        items=[
            ('TAB1', "Receive", "Receive Data"),
            ('TAB2', "Send",    "Send Data"),
        ],
        default='TAB1',
    )  # type: ignore


class DynamicSendObjectProperties(PropertyGroup):
    sel_object: PointerProperty(
        name="Object",
        type=bpy.types.Object,
    )  # type: ignore

    send_location: BoolProperty(
        name="Location",
        default=True,
        description="Send current location",
    )  # type: ignore

    send_axes_location: EnumProperty(
        name="Location Axes",
        items=[
            ("X",   "X",   ""),
            ("Y",   "Y",   ""),
            ("Z",   "Z",   ""),
            ("XY",  "XY",  ""),
            ("XZ",  "XZ",  ""),
            ("YZ",  "YZ",  ""),
            ("XYZ", "XYZ", ""),
        ],
        default="XYZ",
    )  # type: ignore

    send_rotation: BoolProperty(
        name="Rotation",
        default=False,
        description="Send current rotation (in degrees)",
    )  # type: ignore

    send_axes_rotation: EnumProperty(
        name="Rotation Axes",
        items=[
            ("X",   "X",   ""),
            ("Y",   "Y",   ""),
            ("Z",   "Z",   ""),
            ("XY",  "XY",  ""),
            ("XZ",  "XZ",  ""),
            ("YZ",  "YZ",  ""),
            ("XYZ", "XYZ", ""),
        ],
        default="XYZ",
    )  # type: ignore

    send_scale: BoolProperty(
        name="Scale",
        default=False,
        description="Send current scale",
    )  # type: ignore

    send_axes_scale: EnumProperty(
        name="Scale Axes",
        items=[
            ("X",   "X",   ""),
            ("Y",   "Y",   ""),
            ("Z",   "Z",   ""),
            ("XY",  "XY",  ""),
            ("XZ",  "XZ",  ""),
            ("YZ",  "YZ",  ""),
            ("XYZ", "XYZ", ""),
        ],
        default="XYZ",
    )  # type: ignore


def register():
    bpy.types.Scene.serial_connection_properties = PointerProperty(
        type=SerialConnectionProperties,
    )
    bpy.types.Scene.custom_object_collection = CollectionProperty(
        type=DynamicObjectProperties,
    )
    bpy.types.Scene.send_object_collection = CollectionProperty(
        type=DynamicSendObjectProperties,
    )
    bpy.types.Scene.my_ui_tabs = PointerProperty(
        type=MyUIPanelTabs,
    )
    bpy.types.Scene.received_text = PointerProperty(
        name="Font",
        description="Select Text Object to display received text data in the 3D View",
        type=bpy.types.Object,
        poll=_poll_font_object,
    )
    bpy.types.Scene.axis_text_newline = BoolProperty(
        name="Display Axis on New Lines",
        description="Display each axis value on a new line instead of a single line",
        default=False,
    )
    bpy.types.Scene.axis_text_mode = EnumProperty(
        name="Axis Text Mode",
        items=[
            ('GROUP', "Grouped",  "Show XYZ on one line"),
            ('AXIS',  "Per Axis", "Show each axis on a new line"),
        ],
        default='GROUP',
    )
    bpy.types.Scene.updateSceneDelay = FloatProperty(
        name="Update Scene",
        description="Delay between scene animation updates",
        default=1.0, min=0.001, max=2.0, step=0.001,
    )
    bpy.types.WindowManager.serial_is_connected = BoolProperty(
        name="Connected",
        default=False,
        description="Indicates if the serial connection is established",
    )
    bpy.types.WindowManager.serial_connection_status = StringProperty(
        name="Connection Status",
        default="Disconnected",
        description="Shows the current connection status",
        update=_status_update,
    )


def unregister():
    del bpy.types.Scene.serial_connection_properties
    del bpy.types.Scene.custom_object_collection
    del bpy.types.Scene.send_object_collection
    del bpy.types.Scene.my_ui_tabs
    del bpy.types.Scene.received_text
    del bpy.types.Scene.axis_text_newline
    del bpy.types.Scene.axis_text_mode
    del bpy.types.Scene.updateSceneDelay
    del bpy.types.WindowManager.serial_is_connected
    del bpy.types.WindowManager.serial_connection_status