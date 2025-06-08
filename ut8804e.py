import cp2110
import time
import traceback
import struct
import click
import sys
from collections import OrderedDict
import datetime

commands = {
  'connect': b'\x00\x05\x01',
  'disconnect': b'\x00\x05\x00'
}

# Flags for byte 5
flag_hold     = 0b10000000 # 0x80
flag_max_min  = 0b00100000 # 0x20

# Flags for byte 6
flag_manual   = 0b00000001 # 0x01
flag_error = 0b00001000 # 0x08

# Flags for byte 14
flag_overload = 0b00000001 # 0x01

def parse_measurement(measurement_as_bytes):
  # Ohms (omega) is represented as thilde
  as_ascii = measurement_as_bytes.decode('ascii')
  as_ascii = as_ascii.replace('~', 'Ω')
  return as_ascii

def parse_flag(byte, flag):
  if byte & flag > 0:
    return 1
  return 0

def convert_bytes_float(value_as_float):
  if len(value_as_float) != 4:
    raise Exception('Can only convert 4-bytes numbers')

  float_value = struct.unpack('f', value_as_float)[0]
  return f'{float_value:.4f}'

def add_measurement(value_bytes, duration_bytes, data, measurement_name):
  data[measurement_name] = convert_bytes_float(value_bytes)
  seconds = int.from_bytes(duration_bytes, 'little')
  data[measurement_name + '_seconds'] = seconds
  data[measurement_name + '_time'] = datetime.timedelta(seconds=seconds)

def parse_package(package, debug=False):
  if debug:
    print(f'Package: {len(package)} bytes')
    print(f'Package hex: {package.hex()}')
    print(f'Package: {package}')

  try:
    if not (package[0] == 0xab and package[1] == 0xcd):
      print(f'Unknown package: Length: {len(package)}', file=sys.stderr)
      print(f'Unknown package: Content: {package} ({package.hex()})', file=sys.stderr)

      return None
    
    length_from_package = int(package[2])
    if length_from_package != len(package) - 4:
      print(f'Length mismatch: {length_from_package} != {len(package)}', file=sys.stderr)
      return None

    # Check checksum
    checksum = sum(package[2:len(package) - 2]).to_bytes(2, 'little')
    if checksum != package[len(package) - 2 : len(package)]:
      print(f'Checksum mismatch: {checksum.hex()} != { package[len(package) - 2 : len(package)].hex()}', file=sys.stderr)
      print(f'Package: {package}', file=sys.stderr)
      return None

    data = OrderedDict()

    if (package[5] & flag_max_min):
      data['value_1'] = convert_bytes_float(package[10:14])
      data['measurement_1'] = parse_measurement(package[42:46])
      
      add_measurement(package[15:19], package[20:24], data, 'max')
      add_measurement(package[24:28], package[29:33], data, 'avg')
      add_measurement(package[33:37], package[38:42], data, 'min')
    else:
      data['value_1'] = convert_bytes_float(package[10:14])
      data['measurement_1'] = parse_measurement(package[15:19]) # package[15:19].decode('ascii')
      
      data['value_2'] = convert_bytes_float(package[23:27])
      data['measurement_2'] = parse_measurement(package[27:31]) # package[27:31].decode('ascii')

    data['range'] = package[9]  
    data['hold'] = parse_flag(package[5], flag_hold)
    data['manual'] = parse_flag(package[6], flag_manual)
    data['overload'] = parse_flag(package[14], flag_overload)
    data['error'] = parse_flag(package[6], flag_error)
    
    data['properties'] = package[3:10].hex()

    return data

  except Exception as e:
    print(f'Error handling package: {e} | {package} | {package.hex()}', file=sys.stderr)
  
  return None

def send_request(device, command):
  payload_command = commands[command]
  
  start_package = b'\xab\xcd'
  # Create the payload part of the package
  payload_buffer = bytearray()
  payload_buffer.extend(start_package)
  # We add 1 to the length of the command to include this byte
  payload_length = (len(payload_command) + 1).to_bytes()
  payload_buffer.extend(payload_length)
  payload_buffer.extend(payload_command)
  
  checksum = sum(payload_length + payload_command).to_bytes(2, 'little')
  payload_buffer.extend(checksum)

  # Create the complete package
  package_buffer = bytearray()
  package_buffer.extend(len(payload_buffer).to_bytes())
  package_buffer.extend(payload_buffer)

  device.write(package_buffer)

def log(package, package_no, debug):
  data = parse_package(package, debug)
  if (data):
    data['no_#'] = f'{package_no:015}'
    data['timestamp'] = datetime.datetime.now().isoformat()
    data.move_to_end('no_#', False)
    if package_no == 0:
      print(','.join(data.keys()))
    print(','.join([str(x) for x in data.values()]))
    return True
  
  return False

def dump(package, package_no, debug):
  print(f'{package_no:015} | {package.hex()}')
  return True

def read_packages(device, handler, debug=False):
  package_no = 0
  buf = bytearray()
  while (True):
    rv = device.read(63)
    if (len(rv) > 0):
      for b in rv:
        if (b == 0xab):
          if (len(buf) > 0):
            if (handler(buf, package_no, debug)):
              package_no += 1
            buf = bytearray()
        buf.append(b)

@click.command()
@click.argument('cmd')
@click.option('--debug', '-d', default=False, help='')
def main(cmd, debug):
  # This will raise an exception if a device is not found. Called with no
  # parameters, this looks for the default (VID, PID) of the CP2110, which are
  # (0x10c4, 0xEA80).
  try:
    d = cp2110.CP2110Device()
    d.set_uart_config(cp2110.UARTConfig(
      baud=9600,
      parity=cp2110.PARITY.NONE,
      flow_control=cp2110.FLOW_CONTROL.DISABLED,
      data_bits=cp2110.DATA_BITS.EIGHT,
      stop_bits=cp2110.STOP_BITS.SHORT)
    )
    d.enable_uart()
    if debug:
      print(f'Device: {d}')
      print('Sending connect request')
    send_request(d, 'connect')
    time.sleep(1)
    
    if cmd == 'log':
      read_packages(d, log, debug)
    elif cmd == 'dump':
      read_packages(d, dump, debug)
    else:
      sys.exit('Unknown command')

  except Exception as e:
    print(f'Exception: {e}', file=sys.stderr)
    print(traceback.format_exc(), file=sys.stderr)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
      if d:
        print('Sending disconnect request', file=sys.stderr)
        send_request(d, 'disconnect')