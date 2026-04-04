import bpy
from bpy.types import Operator
from .blendix_connection import worker_manager


#  Receive-side object management
class AddCustomObject(Operator):
    """Click to Add Custom Object"""
    bl_idname = "object.add_object"
    bl_label  = "Add Custom Object"

    def execute(self, context):
        context.scene.custom_object_collection.add().sel_object = None
        self.report({"INFO"}, "Object Added")
        return {"FINISHED"}


class RemoveCustomObject(Operator):
    """Click to Remove Custom Object"""
    bl_idname = "object.remove_custom_object"
    bl_label  = "Remove Custom Object"

    index: bpy.props.IntProperty()  # type: ignore

    def execute(self, context):
        context.scene.custom_object_collection.remove(self.index)
        self.report({"INFO"}, "Object Removed")
        return {"FINISHED"}


#  Settings popup (receive side)
class ShowSettingsPopup(bpy.types.Operator):
    """Show Settings Popup"""
    bl_idname = "wm.object_prop_window"
    bl_label  = "Preferences"

    index: bpy.props.IntProperty()  # type: ignore

    def execute(self, context):
        return {"FINISHED"}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=230)

    def draw(self, context):
        layout = self.layout
        scene  = context.scene
        item   = scene.custom_object_collection[self.index]

        layout.use_property_split    = False
        layout.use_property_decorate = False

        layout.label(text=f"Object {self.index + 1} Transform Settings",
                     icon="OUTLINER_DATA_MESH")
        layout.separator()

        box = layout.box()
        col = box.column(align=True)

        def draw_row(name, use_prop, axes_prop, text_prop):
            row = col.row(align=True)
            row.prop(item, use_prop, text="")
            sub = row.row(align=True)
            sub.enabled = getattr(item, use_prop)
            sub.label(text=name)
            axes = sub.row(align=True)
            axes.scale_x = 0.9
            axes.prop(item, axes_prop, text="")
            toggle = sub.row(align=True)
            toggle.scale_x = 0.9
            toggle.prop(item, text_prop, text="", icon="CHECKBOX_HLT", toggle=True)

        draw_row("Location", "use_location", "selected_axes_location", "show_text_location")
        draw_row("Rotation", "use_rotation", "selected_axes_rotation", "show_text_rotation")
        draw_row("Scale",    "use_scale",    "selected_axes_scale",    "show_text_scale")

        col.separator()
        col.separator()
        row = col.row(align=True)
        sub = row.row(align=True)
        split = sub.split(factor=0.57, align=True)
        split.label(text="Text")
        split.prop(item, "text_object_axis", text="")
        toggle = sub.row(align=True)
        toggle.scale_x = 0.95
        toggle.prop(scene, "axis_text_newline", text="", icon="CHECKBOX_HLT", toggle=True)

        col.separator(factor=0.5)
        row = col.row(align=True)
        split = row.split(factor=0.52, align=True)
        split.label(text="Axis Mode")
        split.prop(scene, "axis_text_mode", text="")

        layout.separator()
        reset_op = layout.operator(ResetTransformsOperator.bl_idname,
                                   text="Reset Transforms", icon="LOOP_BACK")
        reset_op.object_name = item.sel_object.name if item.sel_object else ""


class ResetTransformsOperator(bpy.types.Operator):
    """Click to reset the transforms of an object to default values."""
    bl_idname = "object.reset_transforms_base"
    bl_label  = "Reset Transforms Base"

    object_name: bpy.props.StringProperty()  # type: ignore

    def execute(self, context):
        obj = context.scene.objects.get(self.object_name)
        if obj is not None:
            obj.location       = (0, 0, 0)
            obj.rotation_euler = (0, 0, 0)
            obj.scale          = (1, 1, 1)
            return {"FINISHED"}
        self.report({"WARNING"}, f"Object '{self.object_name}' not found.")
        return {"CANCELLED"}


#  Movement control
class StartMovementOperator(Operator):
    """Click to start object movement."""
    bl_idname = "object.start_movement"
    bl_label  = "Start Movement"

    def execute(self, context):
        worker_manager.pause_movement = False
        self.report({"INFO"}, "Movement started")
        return {"FINISHED"}


class StopMovementOperator(Operator):
    """Click to stop object movement."""
    bl_idname = "object.stop_movement"
    bl_label  = "Stop Movement"

    def execute(self, context):
        worker_manager.pause_movement = True
        self.report({"INFO"}, "Movement stopped")
        return {"FINISHED"}


#  Serial connect / disconnect
class ConnectSerialOperator(Operator):
    """Click to connect to a serial port."""
    bl_idname = "serial.connect"
    bl_label  = "Connect to Serial"

    def execute(self, context):
        scene  = context.scene
        wm     = context.window_manager
        props  = scene.serial_connection_properties
        port   = props.port_name
        baud   = int(props.baud_rate)
        fmt    = wm.serial_thread_format          

        if port == "NONE":
            self.report({"WARNING"}, "No serial port available. Please connect a device first.")
            return {"CANCELLED"}

        worker_manager.connect(port, baud, fmt)
        worker_manager.set_mode(wm.serial_thread_modes)  

        wm.serial_is_connected      = True           
        wm.serial_connection_status = "Connecting…"  

        self.report({"INFO"}, f"Connecting to {port} @ {baud}")
        return {"FINISHED"}


class DisconnectSerialOperator(Operator):
    """Click to disconnect from a serial port."""
    bl_idname = "serial.disconnect"
    bl_label  = "Disconnect from Serial"

    def execute(self, context):
        worker_manager.disconnect()
        wm = context.window_manager
        wm.serial_is_connected      = False         
        wm.serial_connection_status = "Disconnected"
        self.report({"INFO"}, "Disconnected")
        return {"FINISHED"}


#  Send-side object management
class ShowSettingsPopupSend(bpy.types.Operator):
    """Show Send Settings Popup"""
    bl_idname = "wm.object_prop_window_send"
    bl_label  = "Preferences"

    index: bpy.props.IntProperty()  # type: ignore

    def execute(self, context):
        return {"FINISHED"}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=230)

    def draw(self, context):
        layout = self.layout
        scene  = context.scene
        item   = scene.send_object_collection[self.index]

        layout.use_property_split    = False
        layout.use_property_decorate = False

        layout.label(text=f"Send Keyframe Data {self.index + 1}", icon="ANIM")
        layout.separator()

        box = layout.box()
        col = box.column(align=True)

        def draw_row(name, use_prop, axes_prop):
            row = col.row(align=True)
            row.scale_y = 0.9
            row.prop(item, use_prop, text="")
            sub = row.row(align=True)
            sub.enabled = getattr(item, use_prop)
            sub.label(text=name)
            axes = sub.row(align=True)
            axes.scale_x = 0.9
            axes.prop(item, axes_prop, text="")

        draw_row("Location", "send_location", "send_axes_location")
        draw_row("Rotation", "send_rotation", "send_axes_rotation")
        draw_row("Scale",    "send_scale",    "send_axes_scale")
        col.separator()


class AddSendObject(Operator):
    """Add Custom Object for Data Sending"""
    bl_idname = "object.add_send_object"
    bl_label  = "Add Object to Send"

    def execute(self, context):
        context.scene.send_object_collection.add().sel_object = None
        self.report({"INFO"}, "Object Added for Sending")
        return {"FINISHED"}


class RemoveSendObject(Operator):
    """Click to remove the custom object"""
    bl_idname = "object.remove_send_object"
    bl_label  = "Remove Object to Send"

    index: bpy.props.IntProperty()  # type: ignore

    def execute(self, context):
        context.scene.send_object_collection.remove(self.index)
        self.report({"INFO"}, "Object Removed")
        return {"FINISHED"}


#  Mode selector
class SerialThreadModeOperator(bpy.types.Operator):
    """Operator to select serial thread mode"""
    bl_idname = "serial_thread.select_mode"
    bl_label  = "Select Serial Thread Mode"

    modes: bpy.props.StringProperty()  # type: ignore

    def execute(self, context):
        worker_manager.set_mode(self.modes)
        self.report({"INFO"}, f"Mode set to: {self.modes}")
        return {"FINISHED"}


#  Info popup
class ShowInfoPopup(bpy.types.Operator):
    """blendixserial info"""
    bl_idname = "wm.object_prop_window_info"
    bl_label  = "About blendixserial"

    def execute(self, context):
        return {"FINISHED"}

    def invoke(self, context, event):
        return context.window_manager.invoke_popup(self, width=340)

    def draw(self, context):
        layout = self.layout
        box    = layout.box()
        col    = box.column(align=True)

        header = col.row()
        header.label(text="blendixserial", icon="PLUGIN")
        col.label(text="2.1.0")
        col.separator()

        col.label(text="A real-time Serial communication bridge between Blender and")
        col.label(text="external devices (USB/COM). Send and receive structured data")
        col.label(text="between Blender and microcontrollers or custom applications.")
        col.separator()

        col.label(text="Communication Modes:")
        col.label(text="• CSV Streaming")
        col.label(text="• Custom Binary Protocol")
        col.separator()

        btn_row = col.row(align=True)
        btn_row.operator("wm.url_open", text="Documentation",
                         icon="HELP").url = "https://electronicstree.com/blendixserial-addon/"
        btn_row.operator("wm.url_open", text="GitHub",
                         icon="URL").url  = "https://github.com/electronicstree/blendixserial"
        col.separator()

        footer = col.row()
        footer.alignment = "CENTER"
        footer.label(text="Made with")
        footer.label(icon="FUND")
        footer.label(text="by M. Usman | Pakistan")


def register():
    bpy.types.Scene.send_data_method = bpy.props.EnumProperty(
        name="Send Method",
        items=[
            ('KEYFRAME', "Keyframe Based", "Send data using frame change events"),
            ('TIMER',    "Timer Based",    "Send data using a timer function"),
        ],
        default='KEYFRAME',
    )
    bpy.types.Scene.send_decimal_places = bpy.props.IntProperty(
        name="Decimal Places",
        description="Number of decimal places when sending transform values",
        default=2, min=0, max=6, soft_min=0, soft_max=4,
    )
    bpy.types.Scene.frame_skip_interval = bpy.props.IntProperty(
        name="Frame Skip Interval",
        description="Frames to skip before sending data again (0 = every frame)",
        default=1, min=0,
    )


def unregister():
    del bpy.types.Scene.send_data_method
    del bpy.types.Scene.send_decimal_places
    del bpy.types.Scene.frame_skip_interval
