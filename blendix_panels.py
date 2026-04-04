import bpy
from bpy.types import Panel
from .blendix_connection import worker_manager
from .blendix_vit_properties import get_allowed_controls, CONTROL_ORDER, ensure_valid_control_type


class SerialConnectionPanel(Panel):
    bl_label       = "BLENDIX SERIAL"
    bl_idname      = "SCENE_PT_serial_connection"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_category    = "blendixserial"

    def draw(self, context):
        layout = self.layout
        scene  = context.scene
        wm     = context.window_manager          
        serial_props = scene.serial_connection_properties

        layout.use_property_split    = True
        layout.use_property_decorate = False

        layout.label(text="Connection Settings", icon='PLUGIN')
        main_box = layout.box()
        row = main_box.row(align=True)

        if not wm.serial_is_connected:            
            row.operator("serial.connect", text="Connect", icon='LINKED')
        else:
            row.operator("serial.disconnect", text="Disconnect", icon='UNLINKED')

        row.separator()

        if hasattr(wm, "serial_debug_enabled"):   
            row.prop(wm, "serial_debug_enabled", text="", icon='CONSOLE', toggle=True)
        else:
            row.label(text="", icon='CONSOLE')

        row.operator("wm.object_prop_window_info", text="", icon="QUESTION")

        col = main_box.column(align=True)
        col.enabled = not wm.serial_is_connected  
        col.prop(serial_props, "port_name", text="Com Port")
        col.prop(serial_props, "baud_rate", text="Baud Rate")

        main_box.label(text=wm.serial_connection_status, icon='INFO') 


class UserInterfacePanel(Panel):
    bl_label       = "3D Object Control"
    bl_idname      = "OBJECT_PT_blendix_panel"
    bl_space_type  = "VIEW_3D"
    bl_region_type = "UI"
    bl_category    = "blendixserial"
    bl_parent_id   = "SCENE_PT_serial_connection"

    def draw(self, context):
        layout     = self.layout
        scene      = context.scene
        wm         = context.window_manager
        serial_mode = wm.serial_thread_modes      

        layout.use_property_split    = True
        layout.use_property_decorate = False

        main_box = layout.box()
        row = main_box.row()

        if worker_manager.pause_movement:
            row.operator("object.start_movement", text="Start Movement", icon='PLAY')
        else:
            row.operator("object.stop_movement",  text="Stop Movement",  icon='PAUSE')

        col = main_box.column(align=True)
        col.use_property_split    = True
        col.use_property_decorate = False

        col.prop(scene, "updateSceneDelay", text="Update Scene", slider=True)
        col.prop(wm, "serial_thread_modes", text="Mode")         
        col.prop(wm, "serial_thread_format", text="Data Format")  

        tab_col = main_box.column(align=True)

        if serial_mode == 'send':
            self.draw_send_tab(tab_col, scene)
        elif serial_mode == 'receive':
            self.draw_receive_tab(tab_col, scene)
        elif serial_mode == 'both':
            tab_col.prop(scene.my_ui_tabs, "tabs", expand=True)
            if scene.my_ui_tabs.tabs == 'TAB1':
                self.draw_receive_tab(tab_col, scene)
            else:
                self.draw_send_tab(tab_col, scene)

    def draw_receive_tab(self, layout, scene):
        main_box = layout.box()
        main_box.label(text="Receiving Mode", icon='IMPORT')

        col = main_box.column(align=True)
        col.use_property_split    = True
        col.use_property_decorate = False

        col.label(text="Text Object")
        col.prop_search(scene, "received_text", scene, "objects", text="")

        col.label(text="Add Object")
        col.operator("object.add_object", text="Add", icon="ADD", emboss=True)

        for i, item in enumerate(scene.custom_object_collection):
            split_main = col.split(factor=0.25)
            split_main.label(text=f"Object {i + 1}")

            split_content = split_main.split(factor=0.7)
            split_content.prop(item, "sel_object", text="")

            button_row = split_content.row(align=True)
            settings = button_row.operator("wm.object_prop_window", text="", icon="PRESET")
            settings.index = i
            remove = button_row.operator("object.remove_custom_object", text="", icon="X")
            remove.index = i

    def draw_send_tab(self, layout, scene):
        obj = bpy.context.active_object

        main_box = layout.box()
        main_box.label(text="Sending Mode", icon="EXPORT")

        col = main_box.column(align=True)
        col.use_property_split    = True
        col.use_property_decorate = False

        col.prop(scene, "send_data_method", text="Send Method")
        col.prop(scene, "send_decimal_places", text="Decimal Places")
        col.prop(scene, "frame_skip_interval", text="Frame Skip")

        col.separator()
        col.operator("object.add_send_object", text="Add Object", icon="ADD")
        col.separator()

        send_object_factor = 0.25
        dropdown_factor    = 0.7

        for i, item in enumerate(scene.send_object_collection):
            split_main = col.split(factor=send_object_factor)
            split_main.label(text=f"Object {i + 1}")

            split_content = split_main.split(factor=dropdown_factor)
            split_content.prop(item, "sel_object", text="")

            button_row = split_content.row(align=True)
            settings = button_row.operator("wm.object_prop_window_send", text="", icon="PRESET")
            settings.index = i
            remove = button_row.operator("object.remove_send_object", text="", icon="X")
            remove.index = i

        layout.separator(factor=0.5)

        element_box = layout.box()
        element_box.label(text="Interactive 3D Viewport Mode", icon='VIEW3D')

        if not obj:
            element_box.label(text="Select an object first", icon='ERROR')
            return

        if not getattr(obj, "vim_is_element", False):
            element_box.operator("vim.mark_element", text="Mark as Element", icon='ADD')
            return

        element_box.operator("vim.unmark_element", text="Unmark", icon='X')

        col = element_box.column(align=True)
        col.use_property_split    = True
        col.use_property_decorate = False

        col.prop(obj, "vim_preset")
        col.prop(obj, "vim_name", text="Name")
        col.separator()

        if getattr(obj, "vim_joystick_2d", False):
            col.prop(obj, "vim_sensitivity")
            col.prop(obj, "vim_joystick_radius", text="Max Radius")
            col.prop(obj, "vim_spring_return")

        else:
            ensure_valid_control_type(obj)
            allowed = get_allowed_controls(obj)
            split = col.split(factor=0.4, align=True)

            left = split.row(align=True)
            left.alignment = 'RIGHT'
            left.label(text="Control Type")
            right = split.row(align=True)
            ICON_MAP = {
                'rotation': 'DRIVER_ROTATIONAL_DIFFERENCE',
                'location': 'EMPTY_ARROWS',
                'scale':    'FULLSCREEN_ENTER',
            }

            if len(allowed) == 1:
                only = next(iter(allowed))
                right.label(text=only.capitalize())
            else:
                for control in CONTROL_ORDER:
                    sub = right.row(align=True)
                    sub.enabled = control in allowed
                    sub.prop_enum(
                        obj, "vim_control_type", control,
                        text="", icon=ICON_MAP.get(control, 'DOT'),
                    )

            if allowed.intersection({'rotation', 'location', 'scale'}):
                col.prop(obj, "vim_axis")
                col.prop(obj, "vim_min")
                col.prop(obj, "vim_max")
                col.prop(obj, "vim_sensitivity")

            if getattr(obj, "vim_multi_position", False):
                col.prop(obj, "vim_positions")

        layout.separator()
        layout.operator("vim.interactive_mode", text="Start Interactive Mode", icon='MOD_ARMATURE')
        layout.label(text="Press Esc or RMB to exit.")
