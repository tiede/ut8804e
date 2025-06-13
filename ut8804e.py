from statistics import stdev
import cp2110
import time
import traceback
import struct
import click
import sys
from collections import OrderedDict
import datetime

class RunningAverage():
  def __init__(self):
    self.average = 0
    self.n = 0

  def __call__(self, new_value):
    self.n += 1
    self.average = (self.average * (self.n-1) + new_value) / self.n 

  def __float__(self):
    return self.average

  def __repr__(self):
    return f'{self.average:.4f}'

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
  
  def add_measurement(self, value_bytes, duration_bytes, measurement_name):
    self.__current_data[measurement_name] = UT8804e.convert_bytes_float(value_bytes)
    seconds = int.from_bytes(duration_bytes, 'little')
    self.__current_data[measurement_name + '_seconds'] = seconds
    self.__current_data[measurement_name + '_time'] = datetime.timedelta(seconds=seconds)

  def __init__(self, debug=False):
    self.__device = None
    self.__debug = debug
    self.__current_data = None
    self.__package_no = 0
    self.__packages = []
    self.__measurements = {}

  def parse_package(self, package):
    if self.__debug:
      print(f'Package: {len(package)} bytes', file=sys.stderr)
      print(f'Package hex: {package.hex()}', file=sys.stderr)
      print(f'Package: {package}', file=sys.stderr)

    try:
      if not (package[0] == 0xab and package[1] == 0xcd):
        print(f'Unknown package: Length: {len(package)}', file=sys.stderr)
        print(f'Unknown package: Content: {package} ({package.hex()})', file=sys.stderr)

        return False

      length_from_package = int(package[2])
      if length_from_package != len(package) - 4:
        print(f'Length mismatch: {length_from_package} != {len(package)}', file=sys.stderr)
        return False

      # Check checksum
      checksum = sum(package[2:len(package) - 2]).to_bytes(2, 'little')
      if checksum != package[len(package) - 2 : len(package)]:
        print(f'Checksum mismatch: {checksum.hex()} != { package[len(package) - 2 : len(package)].hex()}', file=sys.stderr)
        print(f'Package: {package}', file=sys.stderr)
        return None

      if (self.__current_data):
        self.__packages.append(self.__current_data)
        if (self.__debug):
          print(f'Stored {len(self.__packages)} packages', file=sys.stderr)

      self.__current_data = OrderedDict()
      self.__current_data['no_#'] = f'{self.__package_no:015}'

      if (package[5] & self.flag_max_min):
        self.__current_data['value_1'] = UT8804e.convert_bytes_float(package[10:14])
        self.__current_data['measurement_1'] = UT8804e.parse_measurement(package[42:46])
        
        self.add_measurement(package[15:19], package[20:24], 'max')
        self.add_measurement(package[24:28], package[29:33], 'avg')
        self.add_measurement(package[33:37], package[38:42], 'min')
      else:
        self.__current_data['value_1'] = UT8804e.convert_bytes_float(package[10:14])
        self.__current_data['measurement_1'] = UT8804e.parse_measurement(package[15:19]) # package[15:19].decode('ascii')
        
        self.__current_data['value_2'] = UT8804e.convert_bytes_float(package[23:27])
        self.__current_data['measurement_2'] = UT8804e.parse_measurement(package[27:31]) # package[27:31].decode('ascii')

      self.__current_data['range'] = package[9]  
      self.__current_data['hold'] = UT8804e.parse_flag(package[5], self.flag_hold)
      self.__current_data['manual'] = UT8804e.parse_flag(package[6], self.flag_manual)
      self.__current_data['overload'] = UT8804e.parse_flag(package[14], self.flag_overload)
      self.__current_data['error'] = UT8804e.parse_flag(package[6], self.flag_error)
      
      self.__current_data['properties'] = package[3:10].hex()

      self.__current_data['timestamp'] = datetime.datetime.now().isoformat()

      return True

    except Exception as e:
      print(f'Error handling package: {e} | {package} | {package.hex()}', file=sys.stderr)
      return False

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

  def log_handler(self, package):
    result = self.parse_package(package)
    if (result):
      if self.__package_no == 0:
        print(','.join(self.__current_data.keys()))
      print(','.join([str(x) for x in self.__current_data.values()]))
      return True

    return False

  def dump_handler(self, package):
    print(f'{self.__package_no:015} | {package.hex()}')
    return True

  def stat_handler(self, package):
    result = self.parse_package(package)
    if (result):
      if (self.__measurements.get('min')):
        prior_min = self.__measurements['min']
        if (self.__current_data['value_1'] < prior_min):
          self.__measurements['min'] = self.__current_data['value_1']
      else:
        self.__measurements['min'] = self.__current_data['value_1']

      if (self.__measurements.get('max')):
        prior_max = self.__measurements['max']
        if (self.__current_data['value_1'] > prior_max):
          self.__measurements['max'] = self.__current_data['value_1']
      else:
        self.__measurements['max'] = self.__current_data['value_1']
  
      if (self.__measurements.get('avg')):
        self.__measurements['avg'](float(self.__current_data['value_1']))
      else:
        self.__measurements['avg'] = RunningAverage()
        self.__measurements['avg'](float(self.__current_data['value_1']))

      print(f'Read: {self.__current_data["value_1"]}, Min: {self.__measurements["min"]}, Max: {self.__measurements["max"]}, Avg: {self.__measurements["avg"]}')
      return True
    return False

  def read_packages(self, handler):
    buf = bytearray()
    while (True):
      rv = self.__device.read(63)
      if (len(rv) > 0):
        for b in rv:
          if (b == 0xab):
            if (len(buf) > 0):
              if (handler(buf)):
                self.__package_no += 1
              buf = bytearray()
          buf.append(b)

  def log(self):
    self.read_packages(self.log_handler)

  def dump(self):
    self.read_packages(self.dump_handler)

  def stats(self):
    self.read_packages(self.stat_handler)

  def connect(self):
    # This will raise an exception if a device is not found. Called with no
    # parameters, this looks for the default (VID, PID) of the CP2110, which are
    # (0x10c4, 0xEA80).
    print('Connecting', file=sys.stderr)
    try:
      self.__device = cp2110.CP2110Device()
      self.__device.set_uart_config(cp2110.UARTConfig(
        baud=9600,
        parity=cp2110.PARITY.NONE,
        flow_control=cp2110.FLOW_CONTROL.DISABLED,
        data_bits=cp2110.DATA_BITS.EIGHT,
        stop_bits=cp2110.STOP_BITS.SHORT)
      )
      self.__device.enable_uart()
      if self.__debug:
        print(f'Device: {self.__device}', file=sys.stderr)

      self.send_request(self.__device, 'connect')

      time.sleep(1)
    except Exception as e:
      print(f'Exception: {e}', file=sys.stderr)
      print(traceback.format_exc(), file=sys.stderr)

  def disconnect(self):
    self.send_request(self.__device, 'disconnect')

@click.command()
@click.argument('cmd', required=True, type=click.Choice(['log', 'dump', 'stats']))
@click.option('--debug', '-d', is_flag=True)
def main(cmd, debug):
  meter = UT8804e(debug)

  try:
    meter.connect()

    if cmd == 'log':
        meter.log()
    elif cmd == 'dump':
      meter.dump()
    elif cmd == 'stats':
      meter.stats()
    else:
      sys.exit('Unknown command')
  except KeyboardInterrupt:
      print('Interrupted', file=sys.stderr)
      meter.disconnect()

if __name__ == "__main__":
    main()
