import bpy
from mathutils import Vector, Quaternion
import math
from bpy_extras.view3d_utils import (
    region_2d_to_origin_3d,
    region_2d_to_vector_3d,
    location_3d_to_region_2d,
)

from .blendix_vit_properties import (
    PRESETS,
    apply_preset_to_object,
    ensure_valid_control_type,
    initialize_interactive_object,
    validate_interactive_object,
)


# Helpers
AXIS_INDEX = {'X': 0, 'Y': 1, 'Z': 2}


def _is_momentary(obj):
    return getattr(obj, 'vim_momentary', False)



# Apply Preset Operator
class VIM_OT_ApplyPreset(bpy.types.Operator):
    """Apply a preset to the selected element"""
    bl_idname = "vim.apply_preset"
    bl_label = "Apply Preset"

    preset: bpy.props.EnumProperty(
        name="Preset",
        items=[(k, v['name'], '') for k, v in PRESETS.items()],
    )  # type: ignore

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and obj.vim_is_element

    def execute(self, context):
        obj = context.active_object
        if not obj:
            self.report({'WARNING'}, "No active object selected")
            return {'CANCELLED'}

        if self.preset not in PRESETS:
            self.report({'ERROR'}, f"Unknown preset: {self.preset}")
            return {'CANCELLED'}

        obj.vim_preset = self.preset

        context.view_layer.update()
        self.report({'INFO'}, f"Applied preset: {PRESETS[self.preset]['name']}")
        return {'FINISHED'}


# Mark / Unmark Operators
class VIM_OT_MarkElement(bpy.types.Operator):
    """Mark active object as interactive element"""
    bl_idname = "vim.mark_element"
    bl_label = "Mark as Element"

    @classmethod
    def poll(cls, context):
        return context.active_object is not None

    def execute(self, context):
        obj = context.active_object
        if not obj:
            self.report({'WARNING'}, "No active object selected")
            return {'CANCELLED'}

        obj.vim_is_element = True
        obj.vim_name = obj.name

        initialize_interactive_object(obj)

        context.view_layer.update()
        self.report({'INFO'}, f"Marked {obj.name} as interactive element")
        return {'FINISHED'}


class VIM_OT_UnmarkElement(bpy.types.Operator):
    """Remove interactive properties from active object"""
    bl_idname = "vim.unmark_element"
    bl_label = "Unmark Element"

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        return obj is not None and obj.vim_is_element

    def execute(self, context):
        obj = context.active_object
        if not obj:
            self.report({'WARNING'}, "No active object selected")
            return {'CANCELLED'}

        obj.vim_is_element     = False
        obj.vim_name           = ""
        obj.vim_control_type   = 'location'
        obj.vim_axis           = 'Z'
        obj.vim_min            = 0.0
        obj.vim_max            = 1.0
        obj.vim_sensitivity    = 0.02
        obj.vim_binary         = False
        obj.vim_momentary      = False
        obj.vim_joystick_2d    = False
        obj.vim_multi_position = False
        obj.vim_positions      = 3
        obj.vim_output_step    = 0
        obj.vim_output_x       = 0.0
        obj.vim_output_y       = 0.0

        context.view_layer.update()
        self.report({'INFO'}, f"Unmarked {obj.name}")
        return {'FINISHED'}



# Interactive Modal Operator
class VIM_OT_InteractiveMode(bpy.types.Operator):
    """Enter interactive mode – control elements with the mouse"""
    bl_idname = "vim.interactive_mode"
    bl_label  = "Interactive Mode"
    bl_options = {'REGISTER', 'UNDO'}


    def invoke(self, context, event):
        if context.mode != 'OBJECT':
            self.report({'WARNING'}, "Switch to Object Mode first")
            return {'CANCELLED'}

        # make sure any active interactive object is always in a valid state
        obj = context.active_object
        if obj and getattr(obj, "vim_is_element", False):
            validate_interactive_object(obj, reset_transform=False)

        self.active_element   = None
        self.is_dragging      = False
        self.is_pressed       = False
        self.last_mouse       = Vector((0, 0))
        self.current_value    = 0.0
        self.min_value        = 0.0
        self.max_value        = 1.0
        self.joy_offset       = Vector((0.0, 0.0))

        context.window_manager.modal_handler_add(self)
        self.report({'INFO'}, "Interactive mode active  |  ESC / RMB to exit")
        return {'RUNNING_MODAL'}


    # Modal loop
    def modal(self, context, event):
        context.area.tag_redraw()

        if event.type in {'ESC', 'RIGHTMOUSE'}:
            self._finish(context)
            self.report({'INFO'}, "Interactive mode exited")
            return {'CANCELLED'}

        if event.type == 'MOUSEMOVE':
            self._handle_mouse_move(context, event)

        elif event.type == 'LEFTMOUSE':
            if event.value == 'PRESS':
                self._handle_press(context, event)
            elif event.value == 'RELEASE':
                self._handle_release(context, event)

        return {'RUNNING_MODAL'}


    # Event sub-handlers
    def _handle_mouse_move(self, context, event):
        new_mouse = Vector((event.mouse_x, event.mouse_y))

        if self.is_dragging and self.active_element:
            element = self.active_element

            if element.vim_joystick_2d:
                self._update_joystick(context, element, new_mouse)
            else:
                delta_norm = self._compute_delta(context, element, new_mouse)
                self.current_value += delta_norm
                self.current_value = max(self.min_value,
                                         min(self.max_value, self.current_value))
                self._apply_to_object()

        self.last_mouse = new_mouse

        # rotary knobs are gizmo-only, don't show HAND
        under = self._get_element_under_mouse(context, event)
        is_knob = under and getattr(under, 'vim_preset', '') == 'ROTARY_KNOB'
        context.window.cursor_set("DEFAULT" if (not under or is_knob) else "HAND")

    def _handle_press(self, context, event):
            hit = self._get_element_under_mouse(context, event)
            if not hit:
                return

            # Rotary Knob is controlled exclusively via its gizmo, skip here.
            if getattr(hit, 'vim_preset', '') == 'ROTARY_KNOB':
                return

            # Validate the object before using it.
            validate_interactive_object(hit, reset_transform=False)

            self.active_element = hit
            self.last_mouse = Vector((event.mouse_x, event.mouse_y))
            
            if hit.vim_multi_position:
                total_steps = max(2, hit.vim_positions)
                current_step = hit.vim_output_step
                
                direction = getattr(hit, "vim_direction", 1)
                if direction == 0: direction = 1 # Safety fallback

                # Calculate next step
                next_step = current_step + direction

                # Check for boundaries to flip direction
                if next_step >= total_steps - 1:
                    next_step = total_steps - 1
                    hit.vim_direction = -1 
                elif next_step <= 0:
                    next_step = 0
                    hit.vim_direction = 1  

                # Save step and update visual
                hit.vim_output_step = next_step
                self.current_value = next_step / (total_steps - 1)
                
                self._apply_to_object()
                self._output_state()
                return

            #LOGIC FOR OTHER ELEMENTS
            self._load_initial_value()

            if hit.vim_joystick_2d:
                self.joy_offset   = Vector((0.0, 0.0))
                self.is_dragging  = True

            elif hit.vim_binary:
                if _is_momentary(hit):
                    self.current_value = 1.0
                    self.is_pressed    = True
                else:
                    self.current_value = 1.0 if self.current_value < 0.5 else 0.0

                self._apply_to_object()
                self._output_state()

            else:
                self.is_dragging = True

    def _handle_release(self, context, event):
        self.is_dragging = False

        elem = self.active_element
        if not elem:
            return

        # Joystick spring return
        if elem.vim_joystick_2d and elem.vim_spring_return:
            elem.rotation_mode       = 'QUATERNION'
            elem.rotation_quaternion = Quaternion((1, 0, 0, 0))
            elem.vim_output_x        = 0.0
            elem.vim_output_y        = 0.0
            self.joy_offset          = Vector((0.0, 0.0))

        # Momentary button release
        if self.is_pressed and elem.vim_binary and _is_momentary(elem):
            self.current_value = 0.0
            self._apply_to_object()
            self._output_state()

        self._output_state()
        self.is_pressed = False

  
    # Joystick update
    def _update_joystick(self, context, element, new_mouse):
        delta_mouse = new_mouse - self.last_mouse
        sens = element.vim_sensitivity * 0.05

        rv3d       = context.region_data
        view_right = rv3d.view_rotation @ Vector((1, 0, 0))
        view_up    = rv3d.view_rotation @ Vector((0, 1, 0))
        move_vec   = (view_right * delta_mouse.x + view_up * delta_mouse.y) * sens
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

        # Visual tilt
        element.rotation_mode = 'QUATERNION'
        max_tilt  = math.radians(25)
        magnitude = math.sqrt(nx * nx + ny * ny)

        if magnitude > 0.0001:
            tilt_axis = Vector((-ny, nx, 0.0)).normalized()
            element.rotation_quaternion = Quaternion(tilt_axis, magnitude * max_tilt)
        else:
            element.rotation_quaternion = Quaternion((1, 0, 0, 0))

        context.view_layer.update()


    # Delta computation (non-joystick)
    def _compute_delta(self, context, element, new_mouse):
        ensure_valid_control_type(element)
        
        # Multi-position switches should not move during a drag
        if getattr(element, "vim_multi_position", False):
            return 0.0

        ct = element.vim_control_type
        axis_idx = AXIS_INDEX[element.vim_axis]

        if ct == 'rotation':
            total_range = element.vim_max - element.vim_min   # already in radians
            if abs(total_range) < 0.0001: return 0.0

            # World-space rotation axis for this element
            axis_vec = Vector((0, 0, 0))
            axis_vec[axis_idx] = 1.0
            world_axis   = element.matrix_world.to_quaternion() @ axis_vec
            view_forward = context.region_data.view_rotation @ Vector((0, 0, -1))
            dot = world_axis.dot(view_forward)

            if abs(dot) >= 0.4:
                center_2d = location_3d_to_region_2d(
                    context.region, context.region_data, element.location
                )
                if center_2d is None: return 0.0
                v_last = self.last_mouse - center_2d
                v_new  = new_mouse      - center_2d
                if v_last.length < 5.0 or v_new.length < 5.0: return 0.0

                angle_last  = math.atan2(v_last.y, v_last.x)
                angle_new   = math.atan2(v_new.y,  v_new.x)
                delta_angle = angle_new - angle_last
                if delta_angle >  math.pi: delta_angle -= 2 * math.pi
                if delta_angle < -math.pi: delta_angle += 2 * math.pi

                # dot carries the sign: axis into screen → CCW = positive angle
                return (delta_angle * math.copysign(1.0, dot)) / total_range

            rv3d       = context.region_data
            view_right = rv3d.view_rotation @ Vector((1, 0, 0))
            view_up    = rv3d.view_rotation @ Vector((0, 1, 0))

            # Screen-space projection of the world axis (pixels per unit)
            screen_axis = Vector((
                world_axis.dot(view_right),
                world_axis.dot(view_up),
            ))
            screen_axis_len = screen_axis.length
            if screen_axis_len < 0.0001: return 0.0
            screen_axis.normalize()

            mouse_delta = new_mouse - self.last_mouse
            # How far the mouse moved along the projected axis (in pixels)
            drag_px = mouse_delta.dot(screen_axis)

            pixels_for_full_range = 200.0
            return drag_px / pixels_for_full_range
        
        else:
            start_3d = element.location.copy()
            end_3d   = element.location.copy()
            axis_vec = Vector((0, 0, 0))
            axis_vec[axis_idx] = 1.0
            world_axis = element.matrix_world.to_quaternion() @ axis_vec
            start_3d = element.location + (world_axis * element.vim_min)
            end_3d   = element.location + (world_axis * element.vim_max)
            p1 = location_3d_to_region_2d(context.region, context.region_data, start_3d)
            p2 = location_3d_to_region_2d(context.region, context.region_data, end_3d)

            if not p1 or not p2:
                return 0.0

            screen_line = p2 - p1
            line_length_sq = screen_line.length_squared
            
            if line_length_sq < 1.0: 
                return 0.0
            mouse_delta_vec = new_mouse - self.last_mouse
            
            normalized_delta = mouse_delta_vec.dot(screen_line) / line_length_sq
            
            return normalized_delta


    # Apply value to the Blender object
    def _apply_to_object(self):
        obj = self.active_element
        if not obj or obj.vim_joystick_2d:
            return

        ensure_valid_control_type(obj)

        ct     = obj.vim_control_type
        ai     = AXIS_INDEX[obj.vim_axis]
        minp   = obj.vim_min
        maxp   = obj.vim_max
        val    = self.current_value

        # Binary snap
        if obj.vim_binary:
            val = 1.0 if val >= 0.5 else 0.0

        prop_val = minp + val * (maxp - minp)

        if ct == 'rotation':
            obj.rotation_mode = 'XYZ'

            if obj.vim_multi_position:
                steps     = max(2, obj.vim_positions)
                step_size = (maxp - minp) / (steps - 1)
                idx       = round((prop_val - minp) / step_size) if step_size != 0 else 0
                idx       = max(0, min(steps - 1, idx))
                snapped   = minp + idx * step_size
                obj.rotation_euler[ai] = snapped
                obj.vim_output_step    = idx
            else:
                obj.rotation_euler[ai] = prop_val

        elif ct == 'location':
            obj.location[ai] = prop_val

        elif ct == 'scale':
            obj.scale[ai] = prop_val

        context = bpy.context
        if context and context.view_layer:
            context.view_layer.update()


    # Load current transform as the starting current_value
    def _load_initial_value(self):
        obj = self.active_element
        if not obj or obj.vim_joystick_2d:
            self.current_value = 0.0
            self.min_value     = 0.0
            self.max_value     = 1.0
            return

        ensure_valid_control_type(obj)
        if obj.vim_multi_position:
            steps = max(2, obj.vim_positions)
            self.current_value = obj.vim_output_step / (steps - 1)

        else:
            ct = obj.vim_control_type
            ai = AXIS_INDEX[obj.vim_axis]

            if ct == 'rotation':
                pv = obj.rotation_euler[ai]
            elif ct == 'location':
                pv = obj.location[ai]
            elif ct == 'scale':
                pv = obj.scale[ai]
            else:
                pv = obj.vim_min

            rg = obj.vim_max - obj.vim_min
            if rg != 0:
                self.current_value = (pv - obj.vim_min) / rg
            else:
                self.current_value = 0.0

        self.current_value = max(0.0, min(1.0, self.current_value))
        self.min_value = 0.0
        self.max_value = 1.0


    # Output / report state
    def _output_state(self):
        obj = self.active_element
        if not obj:
            return

        name = obj.vim_name or obj.name

        if obj.vim_joystick_2d:
            state = f"X:{obj.vim_output_x:.3f}  Y:{obj.vim_output_y:.3f}"
        elif obj.vim_multi_position:
            state = f"Step {obj.vim_output_step}"
        elif obj.vim_binary:
            state = "ON" if self.current_value >= 0.5 else "OFF"
        else:
            state = f"{round(self.current_value, 3)}"

        self.report({'INFO'}, f"[{name}] → {state}")


    # Ray-cast helper
    def _get_element_under_mouse(self, context, event):
        region    = context.region
        rv3d      = context.region_data
        coord     = (event.mouse_region_x, event.mouse_region_y)
        origin    = region_2d_to_origin_3d(region, rv3d, coord)
        direction = region_2d_to_vector_3d(region, rv3d, coord)
        depsgraph = context.evaluated_depsgraph_get()
        result, _, _, _, obj, _ = context.scene.ray_cast(depsgraph, origin, direction)
        if result and obj and obj.vim_is_element:
            return obj
        return None


    # Cleanup
    def _finish(self, context):
        context.window.cursor_set("DEFAULT")