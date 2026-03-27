import struct
import time
import serial
import serial.tools.list_ports
import threading
import queue
import bpy
from .debug_manager import debug_manager


class SerialConnection:

    def __init__(self, port_name='', baud_rate=9600):
        self._serial_connection = None
        self._port_name = port_name
        self._baud_rate = baud_rate


    def connect_serial(self):
        try:
            if self._serial_connection is not None:
                self._serial_connection.close()

            self._serial_connection = serial.Serial(self._port_name, self._baud_rate)
            debug_manager.event(f"[SERIAL] Connected → {self._port_name} @ {self._baud_rate}")
        except serial.SerialException as error:
            debug_manager.error(f"[SERIAL] Connection FAILED → {error}")
            self._serial_connection = None


    def disconnect(self, serial_thread):
        if serial_thread:
            serial_thread.stop_serial_thread()  
        
        if self._serial_connection is not None and self._serial_connection.is_open:
            try:
                self._serial_connection.flush()
                self._serial_connection.close()
                self._serial_connection = None
                debug_manager.event(f"[SERIAL] Disconnected from {self._port_name}")

            except Exception as e:
                debug_manager.error(f"[SERIAL] Disconnect failed → {type(e).__name__}: {e}")


    @staticmethod
    def list_ports():
        return [port.device for port in serial.tools.list_ports.comports()]




class SerialThread:

    def __init__(self, serial_connection):
        self.serial_connection = serial_connection
        self.data_queue = queue.Queue()
        self.pause_movement = True
        self.running = False  
        self.send_queue = queue.Queue() 
        self.mode = None  


    def set_mode(self, mode):
        if mode in ["send", "receive", "both"]:
            if self.mode != mode:  
                self.mode = mode
                debug_manager.event(f"[THREAD] Mode changed → {self.mode}")


    def serial_thread(self):

        scene = bpy.context.scene
        debug_manager.set_enabled(scene.serial_debug_enabled)

        debug_manager.event("[THREAD] Starting serial thread")

        self.running = True
        self.rx_buffer = bytearray()


        while self.running:
            try:
                ser = self.serial_connection._serial_connection
                current_mode = self.mode

                if ser is None or not ser.is_open:
                    debug_manager.event("[THREAD] Serial not open. Exiting.")
                    break
                # RECEIVE SECTION
  
                if current_mode in ['receive', 'both']:

                    if bpy.context.scene.protocol_format == 'PROTOCOL':

                        if ser.in_waiting:
                            data = ser.read(ser.in_waiting)
                            self.rx_buffer.extend(data)
                        while True:

                            if len(self.rx_buffer) < 5:
                                break

                            if self.rx_buffer[0] != 0x02:
                                self.rx_buffer.pop(0)
                                continue

                            msg_type = self.rx_buffer[1]
                            obj_count = self.rx_buffer[2]
                            payload_len = struct.unpack(">H", self.rx_buffer[3:5])[0]

                            full_packet_len = 5 + payload_len + 2

                            if len(self.rx_buffer) < full_packet_len:
                                break  

                            full_msg = self.rx_buffer[:full_packet_len]

                            if full_msg[-1] != 0x03:
                                self.rx_buffer.pop(0)
                                continue

                            received_checksum = full_msg[-2]
                            calc_checksum = 0
                            for b in full_msg[1:-2]:
                                calc_checksum ^= b

                            if calc_checksum != received_checksum:
                                debug_manager.error("[RX-PROTOCOL] Checksum mismatch")
                                self.rx_buffer.pop(0)
                                continue

                            self.data_queue.put(("PROTOCOL", bytes(full_msg)))

                            debug_manager.data(f"[RX-PROTOCOL] Packet received ({len(full_msg)} bytes)")

                            self.rx_buffer = self.rx_buffer[full_packet_len:]

                    # CSV MODE
                    else:
                        if ser.in_waiting:
                            data = ser.readline().decode(errors='replace').rstrip()

                            debug_manager.data(f"[RX-CSV] {data}")

                            if not data:
                                continue

                            if self.is_valid_data(data):
                                self.data_queue.put(("CSV", data))
                            else:
                                debug_manager.error(f"[RX-CSV] Invalid data → {data}")

                # SENDING SECTION 
                if current_mode in ['send', 'both']:
                    try:
                        if not self.send_queue.empty():
                            data_to_send = self.send_queue.get_nowait()
                            if self.is_valid_send_data(data_to_send):
                                self.send_serial_data(data_to_send)
                        else:
                            time.sleep(0.005)
                    except queue.Empty:
                        pass

            except serial.SerialException as error:
                debug_manager.error(f"[THREAD] Serial exception → {error}")
                break
        debug_manager.event("[THREAD] Serial thread stopped")


    def start_serial_thread(self):
        thread = threading.Thread(target=self.serial_thread)
        thread.daemon = True  
        thread.start()

    def stop_serial_thread(self):
        self.running = False

    def get_data_from_queue(self):
        try:
            return self.data_queue.get_nowait()
        except queue.Empty:
            return None
        


    def is_valid_data(self, serial_data):
        if not serial_data:
            return False  

        parts = serial_data.split(';')

        if len(parts[0].strip()) > 0:
            numerical_part = parts[0].strip()
            try:
                list(map(float, numerical_part.split(',')))
            except ValueError:
                return False

        if len(parts) > 1:
            text_part = parts[1].strip()
            if text_part:
                return True  
        return True



    def parse_serial_data(self, serial_data):
        if not serial_data:
            return [], ""

        numerical_values = []
        text_data = ""

        if ';' in serial_data:
            parts = serial_data.split(';', 1)
            numerical_part = parts[0].strip()
            
            if numerical_part:
                try:
                    numerical_values = list(map(float, numerical_part.split(',')))  
                except ValueError:
                    pass

            if len(parts) > 1:
                text_data = parts[1].strip()

        elif serial_data.startswith(';'):
            text_data = serial_data[1:].strip()  

        return numerical_values, text_data




    def parse_protocol_message(self, full_msg):
        try:
            if len(full_msg) < 7 or full_msg[0] != 0x02 or full_msg[-1] != 0x03:
                return [], ""

            msg_type = full_msg[1]
            obj_count = full_msg[2]
            payload_len = struct.unpack('>H', full_msg[3:5])[0]
            debug_manager.data(f"[PARSE] msg_type={msg_type}, obj_count={obj_count}")
            payload = full_msg[5:5 + payload_len]
            received_checksum = full_msg[5 + payload_len]

            calc = 0
            for b in full_msg[1:5 + payload_len]:
                calc ^= b
            if calc != received_checksum:
                debug_manager.error("[POTOCOL] checksum fail")
                return [], ""

            numerical = []
            text = ""
            pos = 0

            if msg_type in (1, 3):
                for _ in range(obj_count):
                    if pos + 3 > len(payload):
                        break
                    obj_id, bitmask = struct.unpack('>BH', payload[pos:pos+3])
                    pos += 3

                    for bit in range(9):
                        if bitmask & (1 << bit):
                            if pos + 4 > len(payload):
                                break
                            val = struct.unpack('>f', payload[pos:pos+4])[0]
                            numerical.append(val)
                            pos += 4
                        else:
                            numerical.append(None)

            if msg_type in (2, 3):
                if msg_type == 3 and pos < len(payload):
                    text_len = payload[pos]
                    pos += 1
                    if pos + text_len <= len(payload):
                        text = payload[pos:pos + text_len].decode('utf-8', errors='replace')
                elif msg_type == 2:
                    text = payload.decode('utf-8', errors='replace')
                    
            debug_manager.data(f"[PARSED] msg_type={msg_type}, obj_count={obj_count}, "f"values={numerical}, text='{text}'")
            return numerical, text

        except Exception as e:
            debug_manager.error(f"[POTOCOL] parse error → {e}")
            return [], ""


    def is_valid_send_data(self, send_data):
        if isinstance(send_data, bytes):
            if len(send_data) < 7:
                return False
            if not (send_data.startswith(b'\x02') and send_data.endswith(b'\x03')):
                return False
            return True

        # Old CSV path
        if not isinstance(send_data, str):
            return False
        
        if not send_data.endswith(';'):
            return False
        
        try:
            numerical_data = send_data[:-1].split(',')
            for value in numerical_data:
                if '.' in value:
                    float_value = float(value)
                    if len(value.split('.')[-1]) > 2:  
                        return False
                else:
                    int(value)  
            return True
        except (ValueError, IndexError):
            return False


    def send_serial_data(self, send_data):
        try:
            if self.serial_connection._serial_connection is not None and self.serial_connection._serial_connection.is_open:
                
                if isinstance(send_data, str):
                    to_write = send_data
                    if not to_write.endswith('\n'):
                        to_write += '\n'
                    write_bytes = to_write.encode('utf-8')
                
                elif isinstance(send_data, bytes):
                    write_bytes = send_data
                else:
                    debug_manager.error(f"[TX] Unsupported data type: {type(send_data).__name__}")
                    return

                # Actual write
                self.serial_connection._serial_connection.write(write_bytes)
                self.serial_connection._serial_connection.flush()
                debug_manager.data(f"[TX] Sent {len(write_bytes)} bytes")
            else:
                debug_manager.error("[TX] Serial not open")
                    
        except serial.SerialException as error:
            debug_manager.error(f"[TX] Send failed → {error}")




    def queue_send_data(self, data):

        if isinstance(data, str):
            prepared = data  
        elif isinstance(data, bytes):
            prepared = data
        else:
            debug_manager.error("[QUEUE] Unsupported data type")
            return
        self.send_queue.put(prepared)




serial_connection = SerialConnection()
serial_thread = SerialThread(serial_connection)
