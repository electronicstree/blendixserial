import bpy
import math


# Enum definitions
AXIS_ITEMS = [
    ('X', "X Axis", "Move/rotate/scale along X"),
    ('Y', "Y Axis", "Move/rotate/scale along Y"),
    ('Z', "Z Axis", "Move/rotate/scale along Z"),
]

CONTROL_ITEMS = [
    ('rotation', "Rotation", "Rotate around selected axis"),
    ('location', "Location", "Translate along selected axis"),
    ('scale', "Scale", "Scale along selected axis"),
]

 
# Presets
PRESETS = {
    'TOGGLE_SWITCH': {
        'name': 'Toggle Switch',
        'control_type': 'rotation',
        'axis': 'Y',
        'min': 0.0,
        'max': math.radians(39.5),
        'sensitivity': 0.015,
        'binary': True,
    },
    'MULTI_POSITION_SWITCH': {
        'name': 'Multi Position Switch',
        'control_type': 'rotation',
        'axis': 'Z',
        'min': 0.0,
        'max': -math.radians(120),
        'sensitivity': 0.09,
        'binary': False,
    },
    'PUSH_BUTTON': {
        'name': 'Push Button',
        'control_type': 'location',
        'axis': 'Z',
        'min': 0.0,
        'max': -0.15,
        'sensitivity': 0.02,
        'binary': True,
    },
    'SLIDER': {
        'name': 'Slider',
        'control_type': 'location',
        'axis': 'X',
        'min': -1.0,
        'max': 1.0,
        'sensitivity': 0.0050,
        'binary': False,
    },
    'ROTARY_KNOB': {
        'name': 'Rotary Knob',
        'control_type': 'rotation',
        'axis': 'Z',
        'min': 0.0,
        'max': -math.radians(270),
        'sensitivity': 0.11,
        'binary': False,
    },
    'JOYSTICK_2D': {
        'name': 'Joystick 2D (XY)',
        'control_type': 'location',
        'axis': 'Z',  # dummy axis
        'min': -1.0,
        'max': 1.0,
        'sensitivity': 0.16,
        'binary': False,
    },
}



# Static Enum List 
PRESET_ITEMS = []
for key, preset in PRESETS.items():
    PRESET_ITEMS.append((key, preset['name'], ""))



# Preset Update Function
def update_preset(self, context):

    preset = PRESETS.get(self.vim_preset)
    if not preset:
        return

    self.vim_control_type = preset['control_type']
    self.vim_axis = preset['axis']
    self.vim_min = preset['min']
    self.vim_max = preset['max']
    self.vim_sensitivity = preset['sensitivity']
    self.vim_binary = preset['binary']

    # Special cases
    self.vim_joystick_2d = (self.vim_preset == 'JOYSTICK_2D')
    self.vim_multi_position = (self.vim_preset == 'MULTI_POSITION_SWITCH')



# Register
def register():

    bpy.types.Object.vim_is_element = bpy.props.BoolProperty(
        name="Is Interactive Element",
        default=False
    )

    bpy.types.Object.vim_name = bpy.props.StringProperty(
        name="Element Name"
    )

    bpy.types.Object.vim_preset = bpy.props.EnumProperty(
        name="Preset",
        description="Select preset configuration",
        items=PRESET_ITEMS,
        default='PUSH_BUTTON',
        update=update_preset
    )

    bpy.types.Object.vim_control_type = bpy.props.EnumProperty(
        name="Control Type",
        items=CONTROL_ITEMS,
        default='rotation'
    )

    bpy.types.Object.vim_axis = bpy.props.EnumProperty(
        name="Axis",
        items=AXIS_ITEMS,
        default='Z'
    )

    bpy.types.Object.vim_min = bpy.props.FloatProperty(
        name="Min",
        default=0.0
    )

    bpy.types.Object.vim_max = bpy.props.FloatProperty(
        name="Max",
        default=1.0
    )

    bpy.types.Object.vim_sensitivity = bpy.props.FloatProperty(
        name="Sensitivity",
        default=0.02,
        step=1,          
        precision=4 
    )

    bpy.types.Object.vim_binary = bpy.props.BoolProperty(
        name="Binary",
        default=False,
        options={'HIDDEN'}
    )

    bpy.types.Object.vim_joystick_2d = bpy.props.BoolProperty(
        name="2D Joystick Mode",
        default=False,
        options={'HIDDEN'}
    )

    bpy.types.Object.vim_joystick_radius = bpy.props.FloatProperty(
        name="Joystick Max Radius",
        default=0.50,
        min=0.1,
        max=5.0
    )

    bpy.types.Object.vim_spring_return = bpy.props.BoolProperty(
        name="Spring Return",
        default=True,
        options={'HIDDEN'}
    )

    bpy.types.Object.vim_output_x = bpy.props.FloatProperty(
        name="Joystick X Output",
        default=0.0,
        options={'HIDDEN'}
    )

    bpy.types.Object.vim_output_y = bpy.props.FloatProperty(
        name="Joystick Y Output",
        default=0.0,
        options={'HIDDEN'}
    )

    bpy.types.Object.vim_multi_position = bpy.props.BoolProperty(
        name="Multi Position Mode",
        default=False,
        options={'HIDDEN'}
    )

    bpy.types.Object.vim_positions = bpy.props.IntProperty(
        name="Positions",
        default=3,
        min=2,
        max=20
    )

    bpy.types.Object.vim_output_step = bpy.props.IntProperty(
        name="Current Step",
        default=0,
        options={'HIDDEN'}
    )


# Unregister
def unregister():

    del bpy.types.Object.vim_is_element
    del bpy.types.Object.vim_name
    del bpy.types.Object.vim_preset
    del bpy.types.Object.vim_control_type
    del bpy.types.Object.vim_axis
    del bpy.types.Object.vim_min
    del bpy.types.Object.vim_max
    del bpy.types.Object.vim_sensitivity
    del bpy.types.Object.vim_binary
    del bpy.types.Object.vim_joystick_2d
    del bpy.types.Object.vim_joystick_radius
    del bpy.types.Object.vim_spring_return
    del bpy.types.Object.vim_output_x
    del bpy.types.Object.vim_output_y
    del bpy.types.Object.vim_multi_position
    del bpy.types.Object.vim_positions
    del bpy.types.Object.vim_output_step