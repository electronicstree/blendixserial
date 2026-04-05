import bpy
import math


# Enum items
AXIS_ITEMS = [
    ('X', "X Axis", "Move / rotate / scale along X"),
    ('Y', "Y Axis", "Move / rotate / scale along Y"),
    ('Z', "Z Axis", "Move / rotate / scale along Z"),
]

CONTROL_ITEMS = [
    ('rotation', "Rotation", "Rotate around selected axis"),
    ('location', "Location", "Translate along selected axis"),
    ('scale',    "Scale",    "Scale along selected axis"),
]

CONTROL_ORDER = ('rotation', 'location', 'scale')


PRESETS = {
    'PUSH_BUTTON': {
        'name':             'Push Button',
        'default_control':  'location',
        'allowed_controls': {'rotation', 'location'},   # scale not suitable
        'axis':             'Z',
        'min':              0.0,
        'max':              -0.15,
        'sensitivity':      0.02,
        'binary':           True,
        'momentary':        True,
        'joystick_2d':      False,
        'multi_position':   False,
    },
    'TOGGLE_SWITCH': {
        'name':             'Toggle Switch',
        'default_control':  'rotation',
        'allowed_controls': {'rotation', 'location'},   # rotation and location
        'axis':             'Y',
        'min':              0.0,
        'max':              math.radians(39.5),
        'sensitivity':      0.015,
        'binary':           True,
        'momentary':        False,
        'joystick_2d':      False,
        'multi_position':   False,
    },
    'MULTI_POSITION_SWITCH': {
        'name':             'Multi Position',
        'default_control':  'rotation',
        'allowed_controls': {'rotation'},               # rotation only
        'axis':             'Z',
        'min':              0.0,
        'max':              -math.radians(120),
        'sensitivity':      0.09,
        'binary':           False,
        'momentary':        False,
        'joystick_2d':      False,
        'multi_position':   True,
    },
    'SLIDER': {
        'name':             'Slider',
        'default_control':  'location',
        'allowed_controls': {'location'},               # location only
        'axis':             'X',
        'min':              -1.0,
        'max':              1.0,
        'sensitivity':      0.005,
        'binary':           False,
        'momentary':        False,
        'joystick_2d':      False,
        'multi_position':   False,
    },
    'ROTARY_KNOB': {
        'name':             'Rotary Knob',
        'default_control':  'rotation',
        'allowed_controls': {'rotation'},               # rotation only
        'axis':             'Z',
        'min': -math.radians(270),
        'max': 0.0,
        'sensitivity':      0.11,
        'binary':           False,
        'momentary':        False,
        'joystick_2d':      False,
        'multi_position':   False,
    },
    'JOYSTICK_2D': {
        'name':             'Joystick (XY)',
        'default_control':  'location',                 # kept for compatibility
        'allowed_controls': {'location'},               # UI bypassed in joystick mode
        'axis':             'Z',
        'min':              -1.0,
        'max':              1.0,
        'sensitivity':      0.16,
        'binary':           False,
        'momentary':        False,
        'joystick_2d':      True,
        'multi_position':   False,
    },
}


# Static list for EnumProperty items
PRESET_ITEMS = [(key, p['name'], "") for key, p in PRESETS.items()]

# Axis index helper (used by update callbacks)
_AXIS_INDEX = {'X': 0, 'Y': 1, 'Z': 2}



def get_preset_config(obj):
    preset_key = getattr(obj, "vim_preset", 'PUSH_BUTTON')
    return PRESETS.get(preset_key)


def get_allowed_controls(obj):
    preset = get_preset_config(obj)
    if not preset:
        return set(CONTROL_ORDER)

    allowed = preset.get('allowed_controls', CONTROL_ORDER)
    return set(allowed)


def get_first_allowed_control(allowed_controls):
    for control in CONTROL_ORDER:
        if control in allowed_controls:
            return control
    return 'location'


def get_default_control(obj):
    preset = get_preset_config(obj)
    if not preset:
        return 'location'

    allowed = get_allowed_controls(obj)
    default_control = preset.get('default_control', 'location')

    if default_control in allowed:
        return default_control

    return get_first_allowed_control(allowed)


def control_allowed(obj, control_name):
    return control_name in get_allowed_controls(obj)


def ensure_valid_control_type(obj):
    allowed = get_allowed_controls(obj)
    current = getattr(obj, "vim_control_type", 'location')

    if current not in allowed:
        obj.vim_control_type = get_first_allowed_control(allowed)


def apply_preset_to_object(obj):
    preset = get_preset_config(obj)
    if not preset:
        return

    # Mode flags first
    obj.vim_joystick_2d    = preset.get('joystick_2d', False)
    obj.vim_multi_position = preset.get('multi_position', False)

    # Control type must be valid for the preset
    obj.vim_control_type = get_default_control(obj)
    ensure_valid_control_type(obj)

    # Shared transform/config properties
    obj.vim_axis        = preset['axis']
    obj.vim_min         = preset['min']
    obj.vim_max         = preset['max']
    obj.vim_sensitivity = preset['sensitivity']
    obj.vim_binary      = preset['binary']
    obj.vim_momentary   = preset.get('momentary', False)



def _reset_transform_to_min(obj):
    ensure_valid_control_type(obj)

    if obj.vim_joystick_2d:
        obj.vim_output_x = 0.0
        obj.vim_output_y = 0.0
        obj.rotation_mode = 'QUATERNION'
        obj.rotation_quaternion = (1, 0, 0, 0)
        return

    ai  = _AXIS_INDEX.get(obj.vim_axis, 2)
    ct  = obj.vim_control_type
    val = obj.vim_min

    if ct == 'rotation':
        obj.rotation_mode = 'XYZ'
        obj.rotation_euler[ai] = val
    elif ct == 'location':
        obj.location[ai] = val
    elif ct == 'scale':
        obj.scale[ai] = val

    if obj.vim_multi_position:
        obj.vim_output_step = 0



def update_preset(self, context):
    apply_preset_to_object(self)
    _reset_transform_to_min(self)

    if context:
        context.view_layer.update()


def update_control_type(self, context):
    ensure_valid_control_type(self)
    _reset_transform_to_min(self)

    if context:
        context.view_layer.update()


def validate_interactive_object(obj, reset_transform=False):
    ensure_valid_control_type(obj)
    if reset_transform:
        _reset_transform_to_min(obj)


def initialize_interactive_object(obj):
    apply_preset_to_object(obj)
    _reset_transform_to_min(obj)


def update_multi_position(self, context):
    if self.vim_multi_position:
        # Clamp the current step to the new max
        if self.vim_output_step >= self.vim_positions:
            self.vim_output_step = self.vim_positions - 1
        
        # Visually snap the object to its current step
        _reset_transform_to_min(self)
        
        if context:
            context.view_layer.update()
    


def register():

    # Element identity 
    bpy.types.Object.vim_is_element = bpy.props.BoolProperty(
        name="Is Interactive Element",
        default=False,
    )
    bpy.types.Object.vim_name = bpy.props.StringProperty(
        name="Element Name",
    )

    # Preset selector 
    bpy.types.Object.vim_preset = bpy.props.EnumProperty(
        name="Preset",
        description="Select a preset configuration",
        items=PRESET_ITEMS,
        default='PUSH_BUTTON',
        update=update_preset,
    )

    #Core parameters (stable RNA schema)
    bpy.types.Object.vim_control_type = bpy.props.EnumProperty(
        name="Control Type",
        description="How the element drives its output transform",
        items=CONTROL_ITEMS,
        default='location',
        update=update_control_type,
    )
    bpy.types.Object.vim_axis = bpy.props.EnumProperty(
        name="Axis",
        items=AXIS_ITEMS,
        default='Z',
    )
    bpy.types.Object.vim_min = bpy.props.FloatProperty(
        name="Min",
        default=0.0,
    )
    bpy.types.Object.vim_max = bpy.props.FloatProperty(
        name="Max",
        default=1.0,
    )
    bpy.types.Object.vim_sensitivity = bpy.props.FloatProperty(
        name="Sensitivity",
        default=0.02,
        min=0.0001,
        step=1,
        precision=4,
    )

    # Behaviour flags
    bpy.types.Object.vim_binary = bpy.props.BoolProperty(
        name="Binary (On/Off)",
        description="Snap output to 0 or 1 instead of a continuous range",
        default=False,
    )
    bpy.types.Object.vim_momentary = bpy.props.BoolProperty(
        name="Momentary",
        description="Spring back to off-state when the mouse is released",
        default=False,
    )

    # Joystick
    bpy.types.Object.vim_joystick_2d = bpy.props.BoolProperty(
        name="2D Joystick Mode",
        default=False,
        options={'HIDDEN'},
    )
    bpy.types.Object.vim_joystick_radius = bpy.props.FloatProperty(
        name="Joystick Max Radius",
        description="Maximum physical tilt radius in local units",
        default=0.50,
        min=0.01,
        max=5.0,
    )
    bpy.types.Object.vim_spring_return = bpy.props.BoolProperty(
        name="Spring Return",
        description="Return joystick to centre when released",
        default=True,
    )
    bpy.types.Object.vim_output_x = bpy.props.FloatProperty(
        name="Joystick X Output",
        default=0.0,
        options={'HIDDEN'},
    )
    bpy.types.Object.vim_output_y = bpy.props.FloatProperty(
        name="Joystick Y Output",
        default=0.0,
        options={'HIDDEN'},
    )

    # Multi-position switch
    bpy.types.Object.vim_multi_position = bpy.props.BoolProperty(
        name="Multi-Position Mode",
        default=False,
        options={'HIDDEN'},
    )
    bpy.types.Object.vim_positions = bpy.props.IntProperty(
        name="Positions",
        description="Number of discrete detent positions",
        default=3,
        min=2,
        max=20,
        update=update_multi_position,
    )
    bpy.types.Object.vim_output_step = bpy.props.IntProperty(
        name="Current Step",
        default=0,
        options={'HIDDEN'},
    )
    bpy.types.Object.vim_direction = bpy.props.IntProperty(
        name="Direction",
        default=1, # 1 for forward, -1 for backward
        options={'HIDDEN'},
    )
    bpy.types.Object.vim_angle = bpy.props.FloatProperty(
    name="Rotary Angle",
    default=0.0,
    )


def unregister():
    props = [
        'vim_is_element',
        'vim_name',
        'vim_preset',
        'vim_control_type',
        'vim_axis',
        'vim_min',
        'vim_max',
        'vim_sensitivity',
        'vim_binary',
        'vim_momentary',
        'vim_joystick_2d',
        'vim_joystick_radius',
        'vim_spring_return',
        'vim_output_x',
        'vim_output_y',
        'vim_multi_position',
        'vim_positions',
        'vim_output_step',
    ]
    for p in props:
        try:
            delattr(bpy.types.Object, p)
        except AttributeError:
            pass