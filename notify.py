import serial
import serial.tools.list_ports
import sys
import time

ESPRESSIF_VENDOR_ID = 0x303A
BAUDRATE = 115200

def find_gadget_port():
    for port in serial.tools.list_ports.comports():
        if port.vid == ESPRESSIF_VENDOR_ID:
            return port.device
    return None



def notify_gadget():
    gadget_com_port = find_gadget_port()

    if not gadget_com_port:
        return False
    
    try:
        with serial.Serial(gadget_com_port, BAUDRATE, timeout=1) as ser:
            time.sleep(0.05)
            ser.write(b"1")
            return True
    except serial.SerialException as e:
        print(f"ESP32 communication error: {e}", file=sys.stderr)
        return False


if __name__ == "__main__":
    notify_gadget()