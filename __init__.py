# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTIBILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.



# ---- Development Notes ----
# Summary of major changes and features for quick reference.
# Full history available in version control.



# 17/5/2025 - M.Usman - electronicstree.com
#------------------------------------------
# Cross-platform serial port detection | Automatic PySerial installation | Text data receiving issue fix in receiving mode


# 26/5/2025 - M.Usman - electronicstree.com
#------------------------------------------
# Dual Send Mode Support


# 27/5/2025 - M.Usman - electronicstree.com
#------------------------------------------
# Patch: (Send) Resolves Timer Registration issue


# 27/3/2026 - M.Usman - electronicstree.com
#------------------------------------------
# v2.0.0 Major Release:
# - Added Interactive 3D Viewport Mode (VIM)
# - Added CSV format and binary protocol support
# - PySerial now bundled as a wheel (no pip/admin required)


# 29/3/2026 - M.Usman - electronicstree.com
#------------------------------------------
# - Fixed thread-safety issue by removing bpy access from background thread


# 4/4/2026 - M.Usman - electronicstree.com
#------------------------------------------
# - Added new gizmo function for improved rotary knob interaction.
# - Serial engine migrated from threading to subprocess + TCP for better stability.


# 5/4/2026 - M.Usman - electronicstree.com
#-------------------------------------------
# - Replaced auto_load with explicit module registration (Blender extension platform requirement).
# - Moved runtime-only properties (connection state, mode, format, debug) to WindowManager.


# 15/4/2026 - M.Usman - electronicstree.com
#-------------------------------------------
# - Worker subprocess now passes bpy.app.python_args to stay inside Blender's Python environment.
# - Renamed debug_manager.py to serial_log.py to reflect its purpose as a user-facing diagnostic tool.
# - Removed leftover threading import from serial_log.py.


import bpy
import inspect

from . import (
    blendix_connection,
    blendix_properties,
    blendix_vit_properties,
    blendix_operators,
    blendix_vit_operators,
    blendix_vit_gizmo,
    blendix_panels,
    blendix_gdaoc,
    serial_log,
)



_modules = [
    serial_log,
    blendix_connection,
    blendix_properties,
    blendix_vit_properties,
    blendix_operators,
    blendix_vit_operators,
    blendix_vit_gizmo,
    blendix_panels,
    blendix_gdaoc,
]

_BLENDER_BASES = None


def _get_blender_bases():
    global _BLENDER_BASES
    if _BLENDER_BASES is None:
        _BLENDER_BASES = tuple(
            getattr(bpy.types, n) for n in (
                "Panel", "Operator", "PropertyGroup", "AddonPreferences",
                "Header", "Menu", "Node", "NodeSocket", "NodeTree",
                "UIList", "RenderEngine", "Gizmo", "GizmoGroup",
            )
        )
    return _BLENDER_BASES


_classes = []


def _collect_classes():
    bases = _get_blender_bases()
    seen, result = set(), []
    for mod in _modules:
        for _, obj in inspect.getmembers(mod, inspect.isclass):
            if obj in seen:
                continue
            seen.add(obj)
            if issubclass(obj, bases) and not getattr(obj, "is_registered", False):
                result.append(obj)
    return result


def register():
    global _classes
    _classes = _collect_classes()
    for cls in _classes:
        bpy.utils.register_class(cls)
    for mod in _modules:
        if hasattr(mod, "register"):
            mod.register()


def unregister():
    for mod in reversed(_modules):
        if hasattr(mod, "unregister"):
            mod.unregister()
    for cls in reversed(_classes):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass
