import bpy
import math
from mathutils import Matrix, Vector


# Axis helpers
_AXIS_COLOR = {
    'X': (0.8, 0.2, 0.2),
    'Y': (0.2, 0.8, 0.2),
    'Z': (0.2, 0.4, 1.0),
}

_AXIS_INDEX = {'X': 0, 'Y': 1, 'Z': 2}

_AXIS_VEC = {
    'X': Vector((1.0, 0.0, 0.0)),
    'Y': Vector((0.0, 1.0, 0.0)),
    'Z': Vector((0.0, 0.0, 1.0)),
}


# Gizmo Group
class VIM_GGT_RotaryKnob(bpy.types.GizmoGroup):
    bl_label       = "VIM Rotary Knob"
    bl_space_type  = 'VIEW_3D'
    bl_region_type = 'WINDOW'
    bl_options     = {'3D', 'PERSISTENT', 'SHOW_MODAL_ALL'}

    @classmethod
    def poll(cls, context):
        if context.mode != 'OBJECT':
            return False
        return any(_is_rotary_knob(o) for o in context.selected_objects)

    def setup(self, context):
        self._gz_map = {}
        self._gizmo_state = {} 
        self._rebuild(context)

    def refresh(self, context):
        self._rebuild(context)

    def draw_prepare(self, context):
        for name, gz in self._gz_map.items():
            obj = context.scene.objects.get(name)
            if obj:
                _set_gz_matrix(gz, obj, obj.vim_axis)

    def _rebuild(self, context):
        targets      = [o for o in context.selected_objects if _is_rotary_knob(o)]
        target_names = {o.name for o in targets}

        # Remove old gizmos
        for name in list(self._gz_map.keys()):
            if name not in target_names:
                self.gizmos.remove(self._gz_map.pop(name))
                self._gizmo_state.pop(name, None)

        for obj in targets:
            axis   = obj.vim_axis
            ai     = _AXIS_INDEX[axis]
            col    = _AXIS_COLOR[axis]
            col_hi = tuple(min(c + 0.3, 1.0) for c in col)

            # Reset state when rebuilding
            self._gizmo_state.pop(obj.name, None)

            if obj.name not in self._gz_map:
                gz = self.gizmos.new("GIZMO_GT_dial_3d")
                self._gz_map[obj.name] = gz
            else:
                gz = self._gz_map[obj.name]

            # Blender-like clean ring
            gz.color           = col
            gz.alpha           = 0.25              # subtle like Blender
            gz.color_highlight = col
            gz.alpha_highlight = 0.9

            gz.line_width      = 2.0               # thinner = pro look
            gz.scale_basis     = 1.2               # slightly larger

            # Remove angle text
            gz.draw_options    = {'CLIP'}
            gz.use_draw_value  = False

            _set_gz_matrix(gz, obj, axis)

            gz.target_set_handler(
                'offset',
                get   = _make_get(obj),
                set   = _make_set(obj, ai, self._gizmo_state),
                range = _make_range(obj),
            )

# Handlers
def _make_get(obj):
    def get_angle():
        return obj.vim_angle
    return get_angle


def _make_set(obj, idx, state_dict):
    def set_angle(value):
        lo = min(obj.vim_min, obj.vim_max)
        hi = max(obj.vim_min, obj.vim_max)

        key = obj.name

        # First frame init
        if key not in state_dict:
            state_dict[key] = value
            return

        last_value = state_dict[key]

        # Compute delta from gizmo
        delta = value - last_value

        # Handle wrap-around
        if delta > math.pi:
            delta -= 2 * math.pi
        elif delta < -math.pi:
            delta += 2 * math.pi

        state_dict[key] = value

        # Apply delta to our own stored angle
        new_angle = obj.vim_angle - delta

        # HARD LIMIT (true stop)
        if new_angle < lo:
            new_angle = lo
        elif new_angle > hi:
            new_angle = hi

        obj.vim_angle = new_angle

        if obj.rotation_mode != 'XYZ':
            obj.rotation_mode = 'XYZ'

        eul = obj.rotation_euler.copy()
        eul[idx] = new_angle
        obj.rotation_euler = eul

    return set_angle


def _make_range(obj):
    def get_range():
        lo = min(obj.vim_min, obj.vim_max)
        hi = max(obj.vim_min, obj.vim_max)
        return (lo, hi)
    return get_range


# Matrix helper
def _set_gz_matrix(gz, obj, axis):
    if obj.parent:
        parent_rot3 = obj.parent.matrix_world.to_3x3().normalized()
    else:
        parent_rot3 = Matrix.Identity(3)

    world_axis = (parent_rot3 @ _AXIS_VEC[axis]).normalized()

    z_ref = Vector((0.0, 0.0, 1.0))
    dot   = max(-1.0, min(1.0, z_ref.dot(world_axis)))

    if dot > 0.9999:
        ring_rot = Matrix.Identity(4)
    elif dot < -0.9999:
        ring_rot = Matrix.Rotation(math.pi, 4, Vector((1.0, 0.0, 0.0)))
    else:
        cross    = z_ref.cross(world_axis).normalized()
        ring_rot = Matrix.Rotation(math.acos(dot), 4, cross)

    ws        = obj.matrix_world.to_scale()
    avg_scale = (abs(ws.x) + abs(ws.y) + abs(ws.z)) / 3.0

    gz.matrix_basis = (
        Matrix.Translation(obj.matrix_world.translation)
        @ ring_rot
    )

    # Consistent size 
    gz.scale_basis = 1.0


# Predicate
def _is_rotary_knob(obj):
    return (
        getattr(obj, 'vim_is_element',      False)
        and getattr(obj, 'vim_preset',      '') == 'ROTARY_KNOB'
        and getattr(obj, 'vim_control_type','') == 'rotation'
        and not getattr(obj, 'vim_joystick_2d', False)
    )

