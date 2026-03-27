import bpy
from bpy.types import Panel
from .blendix_connection import serial_thread


class SerialConnectionPanel(Panel):
    bl_label = "BLENDIX SERIAL"
    bl_idname = "SCENE_PT_serial_connection"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "blendixserial"

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        serial_props = scene.serial_connection_properties

        layout.label(text="Connection Settings", icon='PLUGIN')
        main_box = layout.box()
        row = main_box.row(align=True)
        if not serial_props.is_connected:
            row.operator("serial.connect", text="Connect", icon='LINKED')
        else:
            row.operator("serial.disconnect", text="Disconnect", icon='UNLINKED')

        settings_box = main_box.box()
        settings_box.label(text="Serial Settings", icon='SETTINGS')
        split = settings_box.split(factor=0.45)
        split.label(text="Com Port:")
        split.prop(serial_props, "port_name", text="")
        split = settings_box.split(factor=0.45) 
        split.label(text="Baud Rate:")
        split.prop(serial_props, "baud_rate", text="")
        
        settings_box.enabled = not serial_props.is_connected
        status_row = main_box.row(align=True)
        status_row.label(icon='INFO')
        status_row.label(text=f"{serial_props.connection_status}")
        layout = row.prop(context.scene,"serial_debug_enabled",text="",icon='CONSOLE',toggle=True)
        layout = row.operator("wm.object_prop_window_info", text="", icon="QUESTION")

    

class UserInterfacePanel(Panel):
    bl_label = "3D Object Control"
    bl_idname = "OBJECT_PT_blendix_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Blendix Serial"
    bl_parent_id = "SCENE_PT_serial_connection"  

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        serial_mode = scene.serial_thread_modes  

        box = layout.box()
        col = box.column()
        col.use_property_split = False
        col.use_property_decorate = False

        factor = 0.45  

        # Update Scene
        split = col.split(factor=factor)
        split.label(text="Update Scene (s)")
        split.prop(scene, "updateSceneDelay", text="", slider=True)

        # Mode
        split = col.split(factor=factor)
        split.label(text="Mode")
        split.prop(scene, "serial_thread_modes", text="")

        serial_thread.set_mode(scene.serial_thread_modes)
        
        split = col.split(factor=factor)
        split.label(text="Data Format")
        split.prop(scene, "protocol_format", text="")

        # Movement
        split = col.split(factor=factor)
        split.label(text="Movement")

        if serial_thread.pause_movement:
            split.operator("object.start_movement", text="Start")
        else:
            split.operator("object.stop_movement", text="Stop")
 

        row = layout.row()
        if serial_mode == 'send':
            self.draw_send_tab(layout, scene)
        elif serial_mode == 'receive':
            self.draw_receive_tab(layout, scene)
        elif serial_mode == 'both':
            layout.prop(scene.my_ui_tabs, "tabs", expand=True)  
            if scene.my_ui_tabs.tabs == 'TAB1':
                self.draw_receive_tab(layout, scene)
            elif scene.my_ui_tabs.tabs == 'TAB2':
                self.draw_send_tab(layout, scene)


    def draw_receive_tab(self, layout, scene):
        main_box = layout.box()
        main_box.label(text="Data Receiving", icon='IMPORT')

        col = main_box.column()
        col.use_property_split = False
        col.use_property_decorate = False

        factor = 0.45  # to control horizontal spacing
        split = col.split(factor=factor)
        split.label(text="Text Object")
        split.prop_search(
            scene,
            "received_text",
            scene,
            "objects",
            text=""
        )

  
        split = col.split(factor=factor)
        split.label(text="Add Object")
        split.operator("object.add_object", text="Add", icon="ADD")

        col.separator()
        for i, item in enumerate(scene.custom_object_collection):

            item_box = col.box()

            split_main = item_box.split(factor=0.25)
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

        box = layout.box()
        box.label(text="Data Sending", icon="EXPORT")

        col = box.column()
        col.use_property_split = True
        col.use_property_decorate = False


        split = col.split(factor=0.45)  # adjust 0.3 – 0.5

        split.label(text="Send Method")
        split.prop(scene, "send_data_method", text="")

        split = col.split(factor=0.45)  # adjust 0.35–0.45

        split.label(text="Decimal Places")
        split.prop(scene, "send_decimal_places", text="")

        split = col.split(factor=0.45)
        split.label(text="Frame Skip")
        split.prop(scene, "frame_skip_interval", text="")

 

        split = col.split(factor=0.45)  # tweak 0.35–0.45 if needed
        split.label(text="Add Object")
        split.operator("object.add_send_object", text="Add", icon="ADD")

        col.separator()

        send_object_factor = 0.25  
        dropdown_factor = 0.7     

        for i, item in enumerate(scene.send_object_collection):

            item_box = layout.box()

            # First split → Label vs Content
            split_main = item_box.split(factor=send_object_factor)
            split_main.label(text=f"Object {i + 1}")

            # Second split → Dropdown vs Buttons
            split_content = split_main.split(factor=dropdown_factor)

            # Dropdown
            split_content.prop(item, "sel_object", text="")

            # Buttons
            button_row = split_content.row(align=True)

            settings = button_row.operator(
                "wm.object_prop_window_send",
                text="",
                icon="PRESET"
            )
            settings.index = i

            remove = button_row.operator(
                "object.remove_send_object",
                text="",
                icon="X"
            )
            remove.index = i

        layout.separator(factor=0.5)


        # ELEMENT SETUP SECTION 

        element_box = layout.box()
        element_box.label(text="Interactive 3D Viewport Mode", icon='VIEW3D')

        if not obj:
            element_box.label(text="Select an object first", icon='ERROR')
            return

        if not obj.vim_is_element:
            element_box.operator("vim.mark_element", text="Mark as Element", icon='ADD')
            return

        element_box.operator("vim.unmark_element", text="Unmark", icon='X')

        col = element_box.column()
        col.use_property_split = True
        col.use_property_decorate = False

        # Basic Settings
        col.prop(obj, "vim_preset")
        col.prop(obj, "vim_name", text="Name")

        col.separator()

  
        # Joystick Mode
        if obj.vim_joystick_2d:

            col.label(text="Joystick Settings", icon='INFO')

            col.prop(obj, "vim_sensitivity")
            col.prop(obj, "vim_joystick_radius", text="Max Radius")
            col.prop(obj, "vim_spring_return")


        # Normal Control Mode
        else:

            col.prop(obj, "vim_control_type")

            if obj.vim_control_type in {'rotation', 'location', 'scale'}:
                col.prop(obj, "vim_axis")
                col.prop(obj, "vim_min")
                col.prop(obj, "vim_max")
                col.prop(obj, "vim_sensitivity")

            if obj.vim_multi_position:
                col.prop(obj, "vim_positions")

        layout.separator()

        layout.operator(
            "vim.interactive_mode",
            text="Start Interactive Mode",
            icon='MOD_ARMATURE'
        )