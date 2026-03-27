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

    def error(self, msg):
        self.log(f"[ERROR] {msg}")

    def event(self, msg):
        self.log(f"[EVENT] {msg}")

    def data(self, msg):
        self.log(f"[DATA] {msg}")

    def verbose(self, msg):
        self.log(f"[VERBOSE] {msg}")


# Only ONE instance in entire project
debug_manager = DebugManager()



# Sync with UI Toggle
def update_debug_state(self, context):
    debug_manager.set_enabled(context.scene.serial_debug_enabled)



# Register / Unregister
def register():
    bpy.types.Scene.serial_debug_enabled = bpy.props.BoolProperty(
        name="Enable Debug",
        default=False,
        update=update_debug_state
    )


def unregister():
    del bpy.types.Scene.serial_debug_enabled