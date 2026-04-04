import bpy
import threading
import time


class DebugManager:
    def __init__(self):
        self.enabled = False
        self.lock = threading.Lock()

    def set_enabled(self, enabled: bool):
        self.enabled = enabled

    def log(self, message: str):
        if not self.enabled:
            return
        timestamp = time.strftime("%H:%M:%S")
        with self.lock:
            print(f"[{timestamp}] {message}")

    def error(self,   msg): self.log(f"[ERROR] {msg}")
    def event(self,   msg): self.log(f"[EVENT] {msg}")
    def data(self,    msg): self.log(f"[DATA] {msg}")
    def verbose(self, msg): self.log(f"[VERBOSE] {msg}")


debug_manager = DebugManager()


def _update_debug_state(self, context):
    debug_manager.set_enabled(self.serial_debug_enabled)


def register():
    if not hasattr(bpy.types.WindowManager, "serial_debug_enabled"):
        bpy.types.WindowManager.serial_debug_enabled = bpy.props.BoolProperty(
            name="Enable Debug",
            description="Enable or disable serial logging",
            default=False,
            update=_update_debug_state,
        )


def unregister():
    if hasattr(bpy.types.WindowManager, "serial_debug_enabled"):
        del bpy.types.WindowManager.serial_debug_enabled
