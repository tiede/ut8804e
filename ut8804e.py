import cp2110
import time
import traceback
import struct
import click
import sys
from collections import OrderedDict
import datetime

commands = {
  'connect': b'\x00\x05\x01'
}

def parse_package(package, debug=False):
  if debug:
    print(f'Package: {len(package)} bytes')
    print(f'Package hex: {package.hex()}')
    print(f'Package: {package}')

  try:
    if len(package) >= 25 and package[0] == 0xab and package[1] == 0xcd:
      float_value = struct.unpack('f', package[10:14])[0]
      measurement = package[15:19].decode('ascii')
      
      if len(package) == 37:
        float_value2 = struct.unpack('f', package[23:27])[0]
        measurement_2 = package[27:31].decode('ascii')
      else:
        float_value2 = 0
        measurement_2 = ''
      mode_1 = package[8]
      mode_2 = package[9]
      mode_3 = package[14]

      # Check checksum
      checksum = sum(package[2:len(package) - 2]).to_bytes(2, 'little')
      if checksum != package[len(package) - 2 : len(package)]:
        print(f'Checksum mismatch: {checksum.hex()} != { package[len(package) - 2 : len(package)].hex()}', file=sys.stderr)
        print(f'Package: {package}', file=sys.stderr)
        return None
      
      data = OrderedDict([
        ('value_1', f'{float_value:.4f}'),
        ('measurement_1', measurement),
        ('value_2', f'{float_value2:.4f}'),
        ('measurement_2', measurement_2),
        ('mode_1', mode_1),
        ('mode_2', mode_2),
        ('mode_3', mode_3)
      ])

      return data

    else:
      print(f'Unknown package: Length: {len(package)}', file=sys.stderr)
      print(f'Unknown package: Content: {package} ({package.hex()})', file=sys.stderr)

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

def log(device, debug=False):
  package_no = 0
  buf = bytearray()
  while (True):
    rv = device.read(63)
    if (len(rv) > 0):
      for b in rv:
        if (b == 0xab):
          if (len(buf) > 0):
            data = parse_package(buf, debug)
            if (data):
              data['#'] = package_no
              data['timestamp'] = datetime.datetime.now().isoformat()
              if package_no == 0:
                print(','.join(data.keys()))              
              print(','.join([str(x) for x in data.values()]))
              package_no += 1
            buf = bytearray()
        buf.append(b)

@click.command()
@click.argument("cmd")
def main(cmd):
  # This will raise an exception if a device is not found. Called with no
  # parameters, this looks for the default (VID, PID) of the CP2110, which are
  # (0x10c4, 0xEA80).
  try:
    debug = False
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
      log(d, debug=debug)
    else:
      sys.exit('Unknown command')

  except Exception as e:
    print(f'Exception: {e}', file=sys.stderr)
    print(traceback.format_exc(), file=sys.stderr)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass