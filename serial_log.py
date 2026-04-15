# serial_log.py | blendixserial

import bpy
import time


class SerialLogger:
    def __init__(self):
        self.enabled = False

    def set_enabled(self, enabled: bool):
        self.enabled = enabled

    def log(self, message: str):
        if not self.enabled:
            return
        timestamp = time.strftime("%H:%M:%S")
        print(f"[blendixserial {timestamp}] {message}")

    def error(self,   msg): self.log(f"[ERROR] {msg}")
    def event(self,   msg): self.log(f"[EVENT] {msg}")
    def data(self,    msg): self.log(f"[DATA]  {msg}")
    def verbose(self, msg): self.log(f"[INFO]  {msg}")


serial_logger = SerialLogger()


def _update_log_state(self, context):
    serial_logger.set_enabled(self.serial_log_enabled)


def register():
    if not hasattr(bpy.types.WindowManager, "serial_log_enabled"):
        bpy.types.WindowManager.serial_log_enabled = bpy.props.BoolProperty(
            name="Diagnostic Log",
            description=(
                "Enable diagnostic logging to Blender's system console. "
                "Useful for identifying whether issues originate from the "
                "addon or the connected serial device."
            ),
            default=False,
            update=_update_log_state,
        )


def unregister():
    if hasattr(bpy.types.WindowManager, "serial_log_enabled"):
        del bpy.types.WindowManager.serial_log_enabled