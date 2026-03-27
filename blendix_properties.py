import bpy
from bpy.types import PropertyGroup
from bpy.props import EnumProperty, BoolProperty, StringProperty, PointerProperty, CollectionProperty, FloatProperty
from .blendix_connection import SerialConnection, serial_thread


class SerialConnectionProperties(PropertyGroup):
    port_name: EnumProperty(
        name="Port Name",
        description="Select a serial port",
        items=lambda self, context: [(port, port, "") for port in SerialConnection.list_ports()]
    ) # type: ignore

    baud_rate: EnumProperty(
        name="Baud Rate",
        description="Select baud rate for serial communication",
        items=[
            ("4800", "4800", ""),
            ("9600", "9600", ""),
            ("19200", "19200", ""),
            ("31250", "31250", ""),
            ("38400", "38400", ""),
            ("57600", "57600", ""),
            ("74880", "74880", ""),
            ("115200", "115200", ""),
            ("230400", "230400", ""),
            ("250000", "250000", ""),
            ("460800", "460800", "")
        ]
    ) # type: ignore

    is_connected: BoolProperty(
        name="Connected",
        default=False,
        description="Indicates if the serial connection is established"
    ) # type: ignore

    connection_status: StringProperty(
        name="Connection Status",
        default="Disconnected",
        description="Shows the current connection status"
    ) # type: ignore



class DynamicObjectProperties(PropertyGroup):
    sel_object: PointerProperty(
        name="Object",
        type=bpy.types.Object
    ) # type: ignore

    use_location: BoolProperty(
        name="Location",
        default=True,
        description="Receive Location data"
    ) # type: ignore

    selected_axes_location: EnumProperty(
        name="Location Axes",
        items=[
            ("X", "X", ""), ("Y", "Y", ""), ("Z", "Z", ""),
            ("XY", "XY", ""), ("XZ", "XZ", ""), ("YZ", "YZ", ""), ("XYZ", "XYZ", ""),
        ],
        default="XYZ",
    ) # type: ignore

    show_text_location: BoolProperty(
        name="Show in Text",
        default=True,
        description="Show Location values in the text object"
    ) # type: ignore

    use_rotation: BoolProperty(
        name="Rotation",
        default=False,
        description="Receive Rotation data (degrees)"
    ) # type: ignore

    selected_axes_rotation: EnumProperty(
        name="Rotation Axes",
        items=[("X", "X", ""), ("Y", "Y", ""), ("Z", "Z", ""),
               ("XY", "XY", ""), ("XZ", "XZ", ""), ("YZ", "YZ", ""), ("XYZ", "XYZ", "")],
        default="XYZ",
    ) # type: ignore

    show_text_rotation: BoolProperty(
        name="Show in Text",
        default=False,
        description="Show Rotation values in the text object"
    ) # type: ignore

    use_scale: BoolProperty(
        name="Scale",
        default=False,
        description="Receive Scale data"
    ) # type: ignore

    selected_axes_scale: EnumProperty(
        name="Scale Axes",
        items=[("X", "X", ""), ("Y", "Y", ""), ("Z", "Z", ""),
               ("XY", "XY", ""), ("XZ", "XZ", ""), ("YZ", "YZ", ""), ("XYZ", "XYZ", "")],
        default="XYZ",
    ) # type: ignore

    show_text_scale: BoolProperty(
        name="Show in Text",
        default=False,
        description="Show Scale values in the text object"
    ) # type: ignore

    
    text_object_axis: PointerProperty(
    name="Text Object for Axis",
    type=bpy.types.Object,
    poll=lambda self, obj: obj.type == 'FONT'  
    ) # type: ignore





class MyUIPanelTabs(bpy.types.PropertyGroup):
    tabs: bpy.props.EnumProperty(
        name="Tabs",
        items=[
            ('TAB1', "Receive", "Receive Data"),
            ('TAB2', "Send", "Send Data"),
        ],
        default='TAB1',
    ) # type: ignore



class DynamicSendObjectProperties(PropertyGroup):
    sel_object: PointerProperty(
        name="Object",
        type=bpy.types.Object
    ) # type: ignore

    send_location: BoolProperty(
        name="Location",
        default=True,
        description="Send current location"
    ) # type: ignore

    send_axes_location: EnumProperty(
        name="Location Axes",
        items=[
            ("X", "X", ""), ("Y", "Y", ""), ("Z", "Z", ""),
            ("XY", "XY", ""), ("XZ", "XZ", ""), ("YZ", "YZ", ""), ("XYZ", "XYZ", ""),
        ],
        default="XYZ",
    ) # type: ignore

    
    send_rotation: BoolProperty(
        name="Rotation",
        default=False,
        description="Send current rotation (in degrees)"
    ) # type: ignore

    send_axes_rotation: EnumProperty(
        name="Rotation Axes",
        items=[
            ("X", "X", ""), ("Y", "Y", ""), ("Z", "Z", ""),
            ("XY", "XY", ""), ("XZ", "XZ", ""), ("YZ", "YZ", ""), ("XYZ", "XYZ", ""),
        ],
        default="XYZ",
    ) # type: ignore

    send_scale: BoolProperty(
        name="Scale",
        default=False,
        description="Send current scale"
    ) # type: ignore

    send_axes_scale: EnumProperty(
        name="Scale Axes",
        items=[
            ("X", "X", ""), ("Y", "Y", ""), ("Z", "Z", ""),
            ("XY", "XY", ""), ("XZ", "XZ", ""), ("YZ", "YZ", ""), ("XYZ", "XYZ", ""),
        ],
        default="XYZ",
    ) # type: ignore



bpy.types.Scene.received_text = bpy.props.PointerProperty(
    name="Font", 
    description="Select Text Object to display received text data in the 3D View",
    type=bpy.types.Object,
    poll=lambda self, obj: obj.type == 'FONT' 
    )


def update_mode(self, context):
    serial_thread.set_mode(self.serial_thread_modes)




bpy.types.Scene.serial_thread_modes = bpy.props.EnumProperty(
    name="Serial Thread Mode",
    description="Choose the mode for the serial thread",
    items=[
        ('send', "Send", "Only send data"),
        ('receive', "Receive", "Only receive data"),
        ('Bidirectional', "Bidirectional", "Send and receive data"),
    ],
    default='receive',
    update=update_mode, 
)



bpy.types.Scene.updateSceneDelay = FloatProperty(
        name="Update Scene",
        default=1,
        min=0.001,
        max=2,
        description="Delay between scene anination updates",
        step=0.001
    ) # type: ignore


bpy.types.Scene.frame_skip_interval = bpy.props.IntProperty(
        name="Frame Skip Interval",
        description="Number of frames to skip before sending data again (set to 0 to send data every frame)",
        default=1,  
        min=0  
    )

bpy.types.Scene.axis_text_newline = bpy.props.BoolProperty(
    name="Display Axis on New Lines",
    description="Display each axis value on a new line instead of a single line",
    default=False
)

bpy.types.Scene.send_data_method = bpy.props.EnumProperty(
        name="Send Method",
        description="Choose how to send data: on frame change or using timer",
        items=[
            ('KEYFRAME', "Keyframe Based", "Send data using frame change events"),
            ('TIMER', "Timer Based", "Send data using a timer function")
        ],
        default='KEYFRAME'
    )

bpy.types.Scene.send_decimal_places = bpy.props.IntProperty(
    name="Decimal Places",
    description="Number of decimal places to use when sending transform values",
    default=2,
    min=0,
    max=6,
    soft_min=0,
    soft_max=4
)


bpy.types.Scene.protocol_format = bpy.props.EnumProperty(
    name="Data Format",
    description="Choose serial data format: CSV (legacy) or Protocol (efficient)",
    items=[
        ('CSV', "CSV", "Original fixed CSV format"),
        ('PROTOCOL', "Protocol", "New binary protocol with bitmasks"),
    ],
    default='CSV',
)


bpy.types.Scene.axis_text_mode = bpy.props.EnumProperty(
    name="Axis Text Mode",
    items=[
        ('GROUP', "Grouped", "Show XYZ on one line"),
        ('AXIS', "Per Axis", "Show each axis on a new line"),
    ],
    default='GROUP'
)

def register():
    bpy.types.Scene.serial_connection_properties = bpy.props.PointerProperty(type=SerialConnectionProperties)
    bpy.types.Scene.custom_object_collection = CollectionProperty(type=DynamicObjectProperties)
    bpy.types.Scene.received_text
    bpy.types.Scene.my_ui_tabs = bpy.props.PointerProperty(type=MyUIPanelTabs)
    bpy.types.Scene.send_object_collection = CollectionProperty(type=DynamicSendObjectProperties)
    bpy.types.Scene.serial_thread_modes
    bpy.types.Scene.frame_skip_interval
 

def unregister():
    del bpy.types.Scene.received_text
    del bpy.types.Scene.serial_thread_modes