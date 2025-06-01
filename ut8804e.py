import cp2110
import time
import traceback
import struct

commands = {
  'connect': b'\x00\x05\x01'
}

def handlePackage(package):
  try:
    float_value = struct.unpack('f', package[10:14])[0]
    float_value2 = struct.unpack('f', package[23:27])[0]
    measurement = package[15:19].decode('ascii')
    measurement_2 = package[27:31].decode('ascii')
    print(f'Value: {float_value:.3f} {measurement}')
    print(f'Value2: {float_value2:.3f} {measurement_2}')
    
    print(f'Mode?: {package[8]}')
    print(f'Mode?: {package[9]}')
    print(f'Mode?: {package[14]}')

  except Exception as e:
    print('Error: {e} ')
    print(package.hex())
    print(package)
    

def send_request(device, command):
  payload_command = commands[command]
  
  start_package = b'\xab\xcd'
  #checksum = b'\x00'
  # Create the payload part of the package
  payload_buffer = bytearray()
  payload_buffer.extend(start_package)
  # We add 1 to the length of the command to include this byte
  payload_length = (len(payload_command) + 1).to_bytes(2)
  payload_buffer.extend(payload_length)
  payload_buffer.extend(payload_command)
  
  checksum = sum(payload_length + payload_command).to_bytes(2, 'little')
  payload_buffer.extend(checksum)

  # Create the complete package
  package_buffer = bytearray()
  package_buffer.extend(len(payload_buffer).to_bytes(2))
  package_buffer.extend(payload_buffer)

  device.write(package_buffer)


# This will raise an exception if a device is not found. Called with no
# parameters, this looks for the default (VID, PID) of the CP2110, which are
# (0x10c4, 0xEA80).
try:
  d = cp2110.CP2110Device()
  print(d)
  d.set_uart_config(cp2110.UARTConfig(
    baud=9600,
    parity=cp2110.PARITY.NONE,
    flow_control=cp2110.FLOW_CONTROL.DISABLED,
    data_bits=cp2110.DATA_BITS.EIGHT,
    stop_bits=cp2110.STOP_BITS.SHORT)
  )
  d.enable_uart()

  send_request(d, 'connect')
  #d.write(bytes.fromhex('08abcd040005010a00'))
  time.sleep(1)
  
  buf = bytearray()
  while (True):
    rv = d.read(63)
    if (len(rv) > 0):
      for b in rv:
        if (b == 0xab):
          if (len(buf) > 0):
            handlePackage(buf)
            buf = bytearray()
        buf.append(b)
except Exception as e:
  print('Exception')
  print(e)
  print(traceback.format_exc())
