import cp2110
import time
import traceback
import struct
import click
import sys
from collections import OrderedDict
import datetime


class UT8804e:
  """
  Represents a UT8804e multimeter connected via a CP2110 USB-to-UART bridge.
  """

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

  @staticmethod
  def parse_measurement(measurement_as_bytes):
    # Ohms (omega) is represented as thilde
    as_ascii = measurement_as_bytes.decode('ascii')
    as_ascii = as_ascii.replace('~', 'Ω')
    return as_ascii

  @staticmethod
  def parse_flag(byte, flag):
    if byte & flag > 0:
      return 1
    return 0

  @staticmethod
  def convert_bytes_float(value_as_float):
    if len(value_as_float) != 4:
      raise Exception('Can only convert 4-bytes numbers')

    float_value = struct.unpack('f', value_as_float)[0]
    return f'{float_value:.4f}'
  
  

  @staticmethod
  def add_measurement(value_bytes, duration_bytes, data, measurement_name):
    data[measurement_name] = UT8804e.convert_bytes_float(value_bytes)
    seconds = int.from_bytes(duration_bytes, 'little')
    data[measurement_name + '_seconds'] = seconds
    data[measurement_name + '_time'] = datetime.timedelta(seconds=seconds)

  def __init__(self, debug=False):
    self.device = None
    self.debug = debug

  def parse_package(self, package):
    if self.debug:
      print(f'Package: {len(package)} bytes', file=sys.stderr)
      print(f'Package hex: {package.hex()}', file=sys.stderr)
      print(f'Package: {package}', file=sys.stderr)

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

      if (package[5] & self.flag_max_min):
        data['value_1'] = UT8804e.convert_bytes_float(package[10:14])
        data['measurement_1'] = UT8804e.parse_measurement(package[42:46])
        
        self.add_measurement(package[15:19], package[20:24], data, 'max')
        self.add_measurement(package[24:28], package[29:33], data, 'avg')
        self.add_measurement(package[33:37], package[38:42], data, 'min')
      else:
        data['value_1'] = UT8804e.convert_bytes_float(package[10:14])
        data['measurement_1'] = UT8804e.parse_measurement(package[15:19]) # package[15:19].decode('ascii')
        
        data['value_2'] = UT8804e.convert_bytes_float(package[23:27])
        data['measurement_2'] = UT8804e.parse_measurement(package[27:31]) # package[27:31].decode('ascii')

      data['range'] = package[9]  
      data['hold'] = UT8804e.parse_flag(package[5], self.flag_hold)
      data['manual'] = UT8804e.parse_flag(package[6], self.flag_manual)
      data['overload'] = UT8804e.parse_flag(package[14], self.flag_overload)
      data['error'] = UT8804e.parse_flag(package[6], self.flag_error)
      
      data['properties'] = package[3:10].hex()

      return data

    except Exception as e:
      print(f'Error handling package: {e} | {package} | {package.hex()}', file=sys.stderr)
    
    return None

  def send_request(self, device, command):
    payload_command = self.commands[command]
    
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

  def log_handler(self, package, package_no):
    data = self.parse_package(package)
    if (data):
      data['no_#'] = f'{package_no:015}'
      data['timestamp'] = datetime.datetime.now().isoformat()
      data.move_to_end('no_#', False)
      if package_no == 0:
        print(','.join(data.keys()))
      print(','.join([str(x) for x in data.values()]))
      return True
    
    return False

  def dump_handler(self, package, package_no):
    print(f'{package_no:015} | {package.hex()}')
    return True

  def read_packages(self, handler):
    package_no = 0
    buf = bytearray()
    while (True):
      #print('Reading from device')
      rv = self.device.read(63)
      if (len(rv) > 0):
        for b in rv:
          if (b == 0xab):
            if (len(buf) > 0):
              if (handler(buf, package_no)):
                package_no += 1
              buf = bytearray()
          buf.append(b)

  def log(self):
    self.read_packages(self.log_handler)

  def dump(self):
    self.read_packages(self.dump_handler)

  def connect(self):
    # This will raise an exception if a device is not found. Called with no
    # parameters, this looks for the default (VID, PID) of the CP2110, which are
    # (0x10c4, 0xEA80).
    print('Connecting', file=sys.stderr)
    try:
      self.device = cp2110.CP2110Device()
      self.device.set_uart_config(cp2110.UARTConfig(
        baud=9600,
        parity=cp2110.PARITY.NONE,
        flow_control=cp2110.FLOW_CONTROL.DISABLED,
        data_bits=cp2110.DATA_BITS.EIGHT,
        stop_bits=cp2110.STOP_BITS.SHORT)
      )
      self.device.enable_uart()
      if self.debug:
        print(f'Device: {self.device}', file=sys.stderr)

      self.send_request(self.device, 'connect')

      time.sleep(1)
    except Exception as e:
      print(f'Exception: {e}', file=sys.stderr)
      print(traceback.format_exc(), file=sys.stderr)

  def disconnect(self):
    self.send_request(self.device, 'disconnect')

@click.command()
@click.argument('cmd', required=True, type=click.Choice(['log', 'dump']))
@click.option('--debug', '-d', default=False)
def main(cmd, debug):
  meter = UT8804e(debug)
  
  try:
    meter.connect()

    if cmd == 'log':
        meter.log()
    elif cmd == 'dump':
      meter.dump()
    else:
      sys.exit('Unknown command')
  except KeyboardInterrupt:
      print('Interrupted', file=sys.stderr)
      meter.disconnect()

if __name__ == "__main__":
    main()
