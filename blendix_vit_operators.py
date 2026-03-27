import bpy
import mathutils
from mathutils import Vector, Quaternion
import math
from bpy_extras.view3d_utils import region_2d_to_origin_3d, region_2d_to_vector_3d, location_3d_to_region_2d
from .blendix_vit_properties import PRESETS


class VIM_OT_ApplyPreset(bpy.types.Operator):
    """Apply a preset to the selected element"""
    bl_idname = "vim.apply_preset"
    bl_label = "Apply Preset"
    preset: bpy.props.EnumProperty(
        name="Preset",
        items=[(k, v['name'], '') for k, v in PRESETS.items()],
    ) # type: ignore

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj and obj.vim_is_element

    def execute(self, context):
        obj = context.active_object
        p = PRESETS[self.preset]
        obj.vim_control_type = p['control_type']
        obj.vim_axis = p['axis']
        obj.vim_min = p['min']
        obj.vim_max = p['max']
        obj.vim_sensitivity = p['sensitivity']
 

        obj.vim_binary = p['binary']
        obj.vim_preset_label = p['name']
        
        obj.vim_joystick_2d = (self.preset == 'JOYSTICK_2D')
        obj.vim_multi_position = (self.preset == 'MULTI_POSITION_SWITCH')

        self.report({'INFO'}, f"Applied: {p['name']}")
        return {'FINISHED'}

class VIM_OT_MarkElement(bpy.types.Operator):
    """Mark active object as interactive element"""
    bl_idname = "vim.mark_element"
    bl_label = "Mark as Element"

    @classmethod
    def poll(cls, context):
        return context.active_object is not None

    def execute(self, context):
        obj = context.active_object
        obj.vim_is_element = True
        obj.vim_name = obj.name
        default = PRESETS['PUSH_BUTTON']
        obj.vim_control_type = default['control_type']
        obj.vim_axis = default['axis']
        obj.vim_min = default['min']
        obj.vim_max = default['max']
        obj.vim_sensitivity = default['sensitivity']
        obj.vim_binary = default['binary']
        obj.vim_joystick_2d = False
        obj.vim_multi_position = False
        obj.vim_positions = 3
        obj.vim_output_step = 0
        self.report({'INFO'}, f"Marked {obj.name}")
        return {'FINISHED'}

class VIM_OT_UnmarkElement(bpy.types.Operator):
    """Remove interactive properties from active object"""
    bl_idname = "vim.unmark_element"
    bl_label = "Unmark Element"

    @classmethod
    def poll(cls, context):
        return context.active_object and context.active_object.vim_is_element

    def execute(self, context):
        obj = context.active_object
        obj.vim_is_element = False
        obj.vim_name = ""
        obj.vim_control_type = 'rotation'
        obj.vim_axis = 'Z'
        obj.vim_min = 0.0
        obj.vim_max = 1.0
        obj.vim_sensitivity = 0.02
        obj.vim_binary = False
        obj.vim_joystick_2d = False
        obj.vim_output_x = 0.0
        obj.vim_output_y = 0.0
        self.report({'INFO'}, f"Unmarked {obj.name}")
        return {'FINISHED'}


# Main Interactive Modal Operator
class VIM_OT_InteractiveMode(bpy.types.Operator):
    """Enter interactive mode - control elements with mouse"""
    bl_idname = "vim.interactive_mode"
    bl_label = "Interactive Mode"
    bl_options = {'REGISTER', 'UNDO'}

    active_element = None
    is_dragging = False
    is_pressed = False
    last_mouse = Vector((0, 0))
    current_value = 0.0
    object_center_2d = Vector((0, 0))
    min_value = 0.0
    max_value = 1.0
    initial_location = None
    delta_norm = 0.0


    def get_element_under_mouse(self, context, event):
        region = context.region
        rv3d = context.region_data
        coord = (event.mouse_region_x, event.mouse_region_y)
        origin = region_2d_to_origin_3d(region, rv3d, coord)
        direction = region_2d_to_vector_3d(region, rv3d, coord)
        depsgraph = context.evaluated_depsgraph_get()
        result, _, _, _, obj, _ = context.scene.ray_cast(depsgraph, origin, direction)
        if result and obj and obj.vim_is_element:
            return obj
        return None

    def modal(self, context, event):
        context.area.tag_redraw()

        if event.type in {'ESC', 'RIGHTMOUSE'}:
            self.finish(context)
            self.report({'INFO'}, "Interactive mode cancelled")
            return {'CANCELLED'}

        element = self.active_element

        if event.type == 'MOUSEMOVE':
            if self.is_dragging and element:
                new_mouse = Vector((event.mouse_x, event.mouse_y))

                if element.vim_joystick_2d:
                    delta_mouse = new_mouse - self.last_mouse
                    sens = element.vim_sensitivity * 0.05

                    if not hasattr(self, "joy_offset"):
                        self.joy_offset = Vector((0.0, 0.0))

                    rv3d = context.region_data
                    view_right = rv3d.view_rotation @ Vector((1, 0, 0))
                    view_up = rv3d.view_rotation @ Vector((0, 1, 0))
                    move_vec = (view_right * delta_mouse.x + view_up * delta_mouse.y) * sens
                    local_move = element.matrix_world.inverted().to_3x3() @ move_vec

                    self.joy_offset.x += local_move.x
                    self.joy_offset.y += local_move.y

                    max_r = element.vim_joystick_radius
                    if self.joy_offset.length > max_r:
                        self.joy_offset = self.joy_offset.normalized() * max_r

                    nx = self.joy_offset.x / max_r if max_r > 0 else 0.0
                    ny = self.joy_offset.y / max_r if max_r > 0 else 0.0

                    element.vim_output_x = nx
                    element.vim_output_y = ny

                    element.rotation_mode = 'QUATERNION'
                    max_tilt = math.radians(25)
                    magnitude = Vector((nx, ny)).length

                    if magnitude > 0.0001:
                        axis = Vector((-ny, nx, 0)).normalized()
                        angle = magnitude * max_tilt
                        element.rotation_quaternion = Quaternion(axis, angle)
                    else:
                        element.rotation_quaternion = Quaternion((1, 0, 0, 0))

                else:
                
                    ct = element.vim_control_type
                    axis = element.vim_axis

                    # Always initialize
                    delta_norm = 0.0

                    if ct == 'rotation':

                        center_2d = location_3d_to_region_2d(
                            context.region,
                            context.region_data,
                            element.location
                        )

                        if center_2d:

                            v1 = self.last_mouse - center_2d
                            v2 = new_mouse - center_2d

                            if v1.length > 5 and v2.length > 5:

                                angle1 = math.atan2(v1.y, v1.x)
                                angle2 = math.atan2(v2.y, v2.x)

                                delta_angle = angle2 - angle1

                                if delta_angle > math.pi:
                                    delta_angle -= 2 * math.pi
                                elif delta_angle < -math.pi:
                                    delta_angle += 2 * math.pi

                                delta_norm = delta_angle * element.vim_sensitivity * 5

                    else:
                        delta_mouse = new_mouse - self.last_mouse

                        if axis == 'X':
                            delta_pixels = delta_mouse.x
                        elif axis == 'Y':
                            delta_pixels = delta_mouse.y
                        else:
                            delta_pixels = delta_mouse.y

                        delta_norm = delta_pixels * element.vim_sensitivity

                    self.current_value += delta_norm
                    self.current_value = max(self.min_value, min(self.max_value, self.current_value))
                    self.apply_to_object()

                self.last_mouse = new_mouse

            if self.get_element_under_mouse(context, event):
                context.window.cursor_set("HAND")
            else:
                context.window.cursor_set("DEFAULT")

        elif event.type == 'LEFTMOUSE':
            if event.value == 'PRESS':
                hit_obj = self.get_element_under_mouse(context, event)
                if hit_obj:
                    self.active_element = hit_obj
                    self.last_mouse = Vector((event.mouse_x, event.mouse_y))
                    self.object_center_2d = location_3d_to_region_2d(
                        context.region, context.region_data, hit_obj.location
                    ) or Vector((event.mouse_x, event.mouse_y))

                    self.load_initial_value()

                    if hit_obj.vim_joystick_2d:
                        self.initial_location = hit_obj.location.copy()
                        self.joy_offset = Vector((0.0, 0.0))
                        self.is_dragging = True
                    elif hit_obj.vim_binary:
                        is_momentary = (
                            hit_obj.vim_max < 0 or
                            "button" in (hit_obj.vim_name or "").lower()
                        )
                        if is_momentary:
                            self.current_value = 1.0
                            self.is_pressed = True
                        else:
                            self.current_value = 1.0 if self.current_value < 0.5 else 0.0
                        self.apply_to_object()
                        self.output_state()
                    else:
                        self.is_dragging = True
                    return {'RUNNING_MODAL'}

            elif event.value == 'RELEASE':
                self.is_dragging = False

                if self.active_element:
                    elem = self.active_element
                    if elem.vim_joystick_2d and elem.vim_spring_return:
                        elem.rotation_mode = 'QUATERNION'
                        elem.rotation_quaternion = Quaternion((1, 0, 0, 0))
                        elem.vim_output_x = 0.0
                        elem.vim_output_y = 0.0
                        self.joy_offset = Vector((0.0, 0.0))

                    if self.is_pressed and elem.vim_binary:
                        is_momentary = (
                            elem.vim_max < 0 or
                            "button" in (elem.vim_name or "").lower()
                        )
                        if is_momentary:
                            self.current_value = 0.0
                            self.apply_to_object()
                            self.output_state()
                    self.output_state()

                self.is_pressed = False

        return {'RUNNING_MODAL'}

    def apply_to_object(self):
        obj = self.active_element
        if not obj:
            return

        if obj.vim_joystick_2d:
            bpy.context.view_layer.update()
            return

        ct = obj.vim_control_type
        axis = obj.vim_axis
        ai = {'X': 0, 'Y': 1, 'Z': 2}[axis]
        minp = obj.vim_min
        maxp = obj.vim_max
        binary = obj.vim_binary
        val = self.current_value
        if binary:
            val = 0.0 if val < 0.5 else 1.0
        prop_val = minp + val * (maxp - minp)

        if ct == 'rotation':
            if obj.vim_multi_position:
                steps = max(2, obj.vim_positions)
                step_size = (maxp - minp) / (steps - 1)
                raw = minp + val * (maxp - minp)
                idx = round((raw - minp) / step_size)
                idx = max(0, min(steps - 1, idx))
                snapped = minp + idx * step_size
                obj.rotation_euler[ai] = snapped
                obj.vim_output_step = idx
            else:
                obj.rotation_euler[ai] = prop_val
        elif ct == 'location':
            obj.location[ai] = prop_val
        elif ct == 'scale':
            obj.scale[ai] = prop_val

        bpy.context.view_layer.update()

    def load_initial_value(self):
        obj = self.active_element
        if not obj:
            return
        if obj.vim_joystick_2d:
            return

        ct = obj.vim_control_type
        axis = obj.vim_axis
        ai = {'X':0, 'Y':1, 'Z':2}[axis]

        if ct == 'rotation':
            pv = obj.rotation_euler[ai]
        elif ct == 'location':
            pv = obj.location[ai]
        elif ct == 'scale':
            pv = obj.scale[ai]
        else:
            pv = obj.vim_min

        rg = obj.vim_max - obj.vim_min
        self.current_value = (pv - obj.vim_min) / rg if rg != 0 else 0.0
        self.current_value = max(0.0, min(1.0, self.current_value))
        self.min_value = 0.0
        self.max_value = 1.0

    def output_state(self):
        if not self.active_element:
            return
        obj = self.active_element
        name = obj.vim_name or obj.name

        if obj.vim_joystick_2d:
            state = f"X:{obj.vim_output_x:.3f}  Y:{obj.vim_output_y:.3f}"
        elif obj.vim_multi_position:
            state = f"Step {obj.vim_output_step}"
        else:
            state = 1 if self.current_value > 0.5 else 0 if obj.vim_binary else round(self.current_value, 3)

        

    def invoke(self, context, event):
        if context.mode != 'OBJECT':
            self.report({'WARNING'}, "Switch to Object Mode first")
            return {'CANCELLED'}
        context.window_manager.modal_handler_add(self)
        self.report({'INFO'}, "Interactive mode active | ESC/RMB to exit")
        return {'RUNNING_MODAL'}

    def finish(self, context):
        context.window.cursor_set("DEFAULT")