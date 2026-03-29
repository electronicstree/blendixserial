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



bl_info = {
    "name": "blendixserial",
    "author": "Usman",
    "description": "Connect Blender to External Devices via Simple UART (Serial Communication)",
    "blender": (4, 2, 0),
    "version": (2, 0, 1),
    "location": "View3D > Properties > blendixserial",
    "category": "3D View",
}

ADDON_VERSION = ".".join(map(str, bl_info["version"]))

from . import auto_load


auto_load.init()


def register():
    auto_load.register()



def unregister():
    auto_load.unregister()
