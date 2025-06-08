# Python script for UT8804E USB HID interface

This script uses the `pycp2110` library to interface with the UT8804E USB HID interface.

## Description

The UT8804E is a USB HID interface for the UT8804E multimeter. It can be used to read the measurements from the multimeter.

The script can be used to log the measurements to a CSV or to dump the raw data to the console.

The script is based on the [UT88043](https://github.com/philpagel/ut8803e) project. The protocol is pretty different, but the basic idea is the same.

It currently supports:

- Standard measurement mode
- Max/Min measurement mode

## Installation

```bash
pip install -r requirements.txt
```

The script will look for the default (VID, PID) of the CP2110, which are (0x10c4, 0xEA80).

When plugging in the device, it will show up as `/dev/usbhidraw*`, be 
owned by root and not accessible to regular users:

    $ ls -la /dev/hid*
    crw------- 1 root root 241, 0 Okt 12 17:15 /dev/hidraw*

So running the program as a regular user will fail. For initial testing, you can
run as root:

    sudo python3 ut8804e.py log

But it is not recommended to do that for productive use. Instead, you need to install 
a `udev` rule file that makes the device user accessible. Create a file 
/etc/udev/rules.d/50-CP2110-hid.rules and put this into it:

    # Make CP2110 usb hid devices user read/writeable
    KERNEL=="hidraw*", ATTRS{idVendor}=="10c4", ATTRS{idProduct}=="ea80", MODE="0666"

## Requirements

- Python 3.12
- `pycp2110` library
- `click` library

## Usage

```bash
python3 ut8804e.py log
python3 ut8804e.py dump
```

This is a simple command line tool that takes exactly on argument and supports a
few options:

    Usage: ut8804e.py [OPTIONS] CMD

        Commands:

            log             start logging data

            dump            dump raw data

        Options:
            -d, --debug     debug mode