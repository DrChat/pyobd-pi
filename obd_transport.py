#!/usr/bin/env python
###########################################################################
# odb_io.py
#
# Copyright 2004 Donour Sizemore (donour@uchicago.edu)
# Copyright 2009 Secons Ltd. (www.obdtester.com)
# Copyright 2018 Justin Moore
#
# This file is part of pyOBD.
#
# pyOBD is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# pyOBD is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with pyOBD; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
###########################################################################

from enum import Enum
import re

import serial

HAS_PYBLUEZ = True
try:
    import bluetooth as bt
except ImportError as e:
    print("Bluetooth disabled: PyBluez not found")
    print(e)
    HAS_PYBLUEZ = False


def is_mac_address(str):
    # http://stackoverflow.com/questions/7629643/how-do-i-validate-the-format-of-a-mac-address
    return re.match("[0-9a-f]{2}([:])[0-9a-f]{2}(\\1[0-9a-f]{2}){4}$", str.lower())


class TransportType(Enum):
    SERIAL = 0
    BLUETOOTH = 1


class OBDTransport:
    """ OBDTransport abstracts the underlying communication layer (bluetooth/COM) """

    def __init__(self):
        self._connected = False
        self._error = ""

    def _OnConnected(self):
        self._connected = True

    def _OnDisconnected(self):
        self._connected = False

    def IsConnected(self):
        return self._connected

    def GetErrorString(self):
        return self._error

    def Discover(self):
        raise NotImplementedError()

    def Connect(self, address, **kwargs):
        raise NotImplementedError()

    def Close(self):
        raise NotImplementedError()

    def Recv(self, len):
        raise NotImplementedError()

    def Send(self, data):
        raise NotImplementedError()


class BluetoothTransport(OBDTransport):
    def __init__(self):
        super(BluetoothTransport, self).__init__()

    def Discover(self, **kwargs):
        time = kwargs.get('time', 4)

        try:
            return bt.discover_devices(time)
        except IOError as e:
            self._error = str(e)
            return None
        
        return None

    def Connect(self, address, **kwargs):
        if not is_mac_address(address):
            raise ValueError("MAC address required")

        try:
            self._socket = bt.BluetoothSocket(bt.RFCOMM)
            self._socket.connect((address, 1))
            self._OnConnected()
        except IOError as e:
            self._error = str(e)
            return False

        return True

    def Recv(self, len):
        if not self._connected:
            raise IOError("Not connected")

        return self._socket.recv(len)

    def Send(self, data):
        if not self._connected:
            raise IOError("Not connected")

        return self._socket.send(data)


class SerialTransport(OBDTransport):
    def Connect(self, address, **kwargs):
        try:
            self._port = serial.Serial(address, kwargs['baud'], kwargs['parity'],
                                    kwargs['stopbits'], kwargs['bytesize'],
                                    kwargs['timeout'])
        except serial.SerialException as e:
            return False
        
        return True


def CreateTransport(typ):
    if typ == TransportType.BLUETOOTH and HAS_PYBLUEZ:
        return BluetoothTransport()
    elif typ == TransportType.SERIAL:
        return SerialTransport()

    return None
