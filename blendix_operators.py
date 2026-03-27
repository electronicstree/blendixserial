import bpy
from bpy.types import Operator
from .blendix_connection import serial_connection, serial_thread
import addon_utils



class AddCustomObject(Operator):
    """Click to Add Custom Object"""
    bl_idname = "object.add_object"
    bl_label = "Add Custom Object"

    def execute(self, context):
        scene = context.scene

        new_item = scene.custom_object_collection.add()
        new_item.sel_object = None  
        self.report({'INFO'}, "Object Added")
        return {'FINISHED'}

class RemoveCustomObject(Operator):
    """Click to Remove Custom Object"""
    bl_idname = "object.remove_custom_object"
    bl_label = "Remove Custom Object"

    index: bpy.props.IntProperty() # type: ignore

    def execute(self, context):
        scene = context.scene
        scene.custom_object_collection.remove(self.index)
        self.report({'INFO'}, "Object Removed")
        return {'FINISHED'}


class ShowSettingsPopup(bpy.types.Operator):
    """Show Settings Popup"""
    bl_idname = "wm.object_prop_window"
    bl_label = "Preferences"

    index: bpy.props.IntProperty()  # type: ignore


    # EXECUTE
    def execute(self, context):
        return {'FINISHED'}


    # INVOKE (Controlled Width)
    def invoke(self, context, event):
        # 300 = sleek and compact
        return context.window_manager.invoke_props_dialog(self, width=230)

    # DRAW UI
    def draw(self, context):
        layout = self.layout
        scene = context.scene
        item = scene.custom_object_collection[self.index]

        # Make layout compact
        layout.use_property_split = False
        layout.use_property_decorate = False

        object_number = self.index + 1


        # Header
        layout.label(
            text=f"Object {object_number} Transform Settings",
            icon="OUTLINER_DATA_MESH"
        )
        layout.separator()


        # Main Box
        box = layout.box()
        col = box.column(align=True)

        def draw_row(name, use_prop, axes_prop, text_prop):
            row = col.row(align=True)
            row.scale_y = 1.0 # slightly shorter height

            # Enable Checkbox
            row.prop(item, use_prop, text="")

            sub = row.row(align=True)
            sub.enabled = getattr(item, use_prop)

            # Label
            sub.label(text=name)

            # Axis Selection (compact)
            axes = sub.row(align=True)
            axes.scale_x = 0.9
            axes.prop(item, axes_prop, text="")

            # Small Text Toggle Icon
            text_toggle = sub.row(align=True)
            text_toggle.scale_x = 0.9
            text_toggle.prop(
                item,
                text_prop,
                text="",
                icon="CHECKBOX_HLT",
                toggle=True
            )

        # Transform Rows
        draw_row("Location", "use_location", "selected_axes_location", "show_text_location")
        draw_row("Rotation", "use_rotation", "selected_axes_rotation", "show_text_rotation")
        draw_row("Scale", "use_scale", "selected_axes_scale", "show_text_scale")


        col.separator()
        col.separator()
        row = col.row(align=True)
        row.scale_y = 0.95

        sub = row.row(align=True)

        split = sub.split(factor=0.57, align=True)  

        split.label(text="Text")
        split.prop(item, "text_object_axis", text="")
        toggle = sub.row(align=True)
        toggle.scale_x = 0.95
        toggle.prop(
            scene,
            "axis_text_newline",
            text="",
            icon="CHECKBOX_HLT",
            toggle=True
        )

        col.separator(factor=0.5)
        row = col.row(align=True)
        row.scale_y = 0.95

        split = row.split(factor=0.52, align=True) 
        split.label(text="Axis Mode")
        split.prop(scene, "axis_text_mode", text="")

        layout.separator()

        reset_operator = layout.operator(
            ResetTransformsOperator.bl_idname,
            text="Reset Transforms",
            icon="LOOP_BACK"
        )

        reset_operator.object_name = (
            item.sel_object.name if item.sel_object else ""
        )


class ResetTransformsOperator(bpy.types.Operator):
    """Click to reset the transforms of an object to default values."""
    bl_idname = "object.reset_transforms_base"
    bl_label = "Reset Transforms Base"

    object_name: bpy.props.StringProperty() # type: ignore

    def execute(self, context):
        obj = context.scene.objects.get(self.object_name)
        
        if obj is not None:
            obj.location = (0, 0, 0)
            obj.rotation_euler = (0, 0, 0)
            obj.scale = (1, 1, 1)
            return {'FINISHED'}
        else:
            self.report({'WARNING'}, f"Object '{self.object_name}' not found.")
            return {'CANCELLED'}



class StartMovementOperator(Operator):
    """Click to start object movement."""
    bl_idname = "object.start_movement"
    bl_label = "Start Movement"

    def execute(self, context):

        serial_thread.pause_movement = False
        self.report({'INFO'}, "Movement started")
        return {'FINISHED'}


class StopMovementOperator(Operator):
    """Click to stop object movement."""
    bl_idname = "object.stop_movement"
    bl_label = "Stop Movement"

    def execute(self, context):

        serial_thread.pause_movement = True
        self.report({'INFO'}, "Movement stopped")
        return {'FINISHED'}


class ConnectSerialOperator(Operator):
    """Click to connect to a serial port."""
    bl_idname = "serial.connect"
    bl_label = "Connect to Serial"

    def execute(self, context):
        props = context.scene.serial_connection_properties
        serial_connection._port_name = props.port_name
        serial_connection._baud_rate = int(props.baud_rate)

        serial_connection.connect_serial()
        serial_thread.start_serial_thread() 

        try:

            if serial_connection._serial_connection and serial_connection._serial_connection.is_open:
                props.is_connected = True
                props.connection_status = "Connected"
                self.report({'INFO'}, "Connected")

        except:
            self.report({'ERROR'}, f"Failed to connect to serial port {serial_connection._port_name}")
        return {'FINISHED'}


class DisconnectSerialOperator(Operator):
    """Click to disconnect from a serial port."""
    bl_idname = "serial.disconnect"
    bl_label = "Disconnect from Serial"

    def execute(self, context):
        serial_connection.disconnect(serial_thread)
        props = context.scene.serial_connection_properties
        if not serial_connection._serial_connection or not serial_connection._serial_connection.is_open:
            props.is_connected = False
            props.connection_status = "Disconnected"
            self.report({'INFO'}, "Disconnected")
        return {'FINISHED'}





class ShowSettingsPopupSend(bpy.types.Operator):
    """Show Send Settings Popup"""
    bl_idname = "wm.object_prop_window_send"
    bl_label = "Preferences"

    index: bpy.props.IntProperty()  # type: ignore

    def execute(self, context):
        return {'FINISHED'}


    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=230)


    def draw(self, context):
        layout = self.layout
        scene = context.scene
        item = scene.send_object_collection[self.index]

        # Compact layout
        layout.use_property_split = False
        layout.use_property_decorate = False

        object_number = self.index + 1

        # Header
        layout.label(
            text=f"Send Keyframe Data {object_number}",
            icon='ANIM'
        )
        layout.separator()

        # Main Box
        box = layout.box()
        col = box.column(align=True)

        def draw_row(name, use_prop, axes_prop):
            row = col.row(align=True)
            row.scale_y = 0.9  # slightly shorter height

            # Enable checkbox
            row.prop(item, use_prop, text="")

            sub = row.row(align=True)
            sub.enabled = getattr(item, use_prop)

            # Label
            sub.label(text=name)

            # Compact axis enum
            axes = sub.row(align=True)
            axes.scale_x = 0.9
            axes.prop(item, axes_prop, text="")

        # Transform rows
        draw_row("Location", "send_location", "send_axes_location")
        draw_row("Rotation", "send_rotation", "send_axes_rotation")
        draw_row("Scale", "send_scale", "send_axes_scale")

        col.separator()


       

class AddSendObject(Operator):
    """Add Custom Object for Data Sending"""
    bl_idname = "object.add_send_object"
    bl_label = "Add Object to Send"

    def execute(self, context):
        scene = context.scene
        new_item = scene.send_object_collection.add()
        new_item.sel_object = None  
        self.report({'INFO'}, "Object Added for Sending")
        return {'FINISHED'}

class RemoveSendObject(Operator):
    """Click to remove the custom object"""
    bl_idname = "object.remove_send_object"
    bl_label = "Remove Object to Send"

    index: bpy.props.IntProperty() # type: ignore

    def execute(self, context):
        scene = context.scene
        scene.send_object_collection.remove(self.index)
        self.report({'INFO'}, "Object Removed")
        return {'FINISHED'}


class SerialThreadModeOperator(bpy.types.Operator):
    """Operator to select serial thread mode"""
    bl_idname = "serial_thread.select_mode"
    bl_label = "Select Serial Thread Mode"

    modes: bpy.props.StringProperty() # type: ignore

    def execute(self, context):
        selected_mode = self.modes
        serial_thread.set_mode(selected_mode)  
        self.report({'INFO'}, f"Serial Thread mode set to: {selected_mode}")
        return {'FINISHED'}
    




import bpy
import sys




class ShowInfoPopup(bpy.types.Operator):
    """About BlendixSerial"""
    bl_idname = "wm.object_prop_window_info"
    bl_label = "About BlendixSerial"

    def execute(self, context):
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_popup(self, width=340)

    def draw(self, context):
        layout = self.layout

        # Get version safely
        try:
            addon_module = sys.modules[__package__]
            version = addon_module.bl_info.get("version", (0, 0, 0))
            version_str = ".".join(map(str, version))
        except:
            version_str = "Unknown"

        box = layout.box()
        col = box.column(align=True)

        # Header 
        header = col.row()
        header.label(text="BlendixSerial", icon="PLUGIN")

        col.label(text=f"Version {version_str}")
        col.separator()

        #Description
        col.label(text="A real-time Serial communication bridge between Blender and")
        col.label(text="external devices (USB/COM). Send and receive structured data")
        col.label(text="between Blender and microcontrollers or custom applications.")
        col.separator()

        col.label(text="Communication Modes:")
        col.label(text="• CSV Streaming")
        col.label(text="• Custom Binary Protocol")
        col.separator()

        # Buttons 
        btn_row = col.row(align=True)

        btn_row.operator(
            "wm.url_open",
            text="Documentation",
            icon="HELP"
        ).url = "https://electronicstree.com/blendixserial-addon/"

        btn_row.operator(
            "wm.url_open",
            text="GitHub",
            icon="URL"
        ).url = "https://github.com/electronicstree"

        col.separator()

        #Footer
        footer = col.row()
        footer.alignment = 'CENTER'
        footer.label(text="Made with")
        footer.label(icon="FUND")
        footer.label(text="by M. Usman | Pakistan")

