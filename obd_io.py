#!/usr/bin/env python
###########################################################################
# odb_io.py
#
# Copyright 2004 Donour Sizemore (donour@uchicago.edu)
# Copyright 2009 Secons Ltd. (www.obdtester.com)
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

import re
import string
import time
from datetime import datetime
from math import ceil

import bluetooth as bt
import serial

import obd_sensors
from debugEvent import DebugEvent, debug_display
from obd_sensors import hex_to_int
from obd_transport import CreateTransport, TransportType

HAS_PYBLUEZ = True
try:
    import bluetooth as bt
except ImportError as e:
    print("Bluetooth disabled: PyBluez not found")
    print(e)
    HAS_PYBLUEZ = False



GET_DTC_COMMAND = b"\x03"  # Mode 03 (no PID)
CLEAR_DTC_COMMAND = b"\x04"  # Mode 04 (no PID)
GET_PENDING_DTC_COMMAND = b"\x07"  # Mode 07 (no PID)


#__________________________________________________________________________


def decrypt_dtc_code(code):
    """Returns the 5-digit DTC code from hex encoding"""
    dtc = []
    current = code
    for i in range(0, 3):
        if len(current) < 4:
            raise "Tried to decode bad DTC: %s" % code

        tc = obd_sensors.hex_to_int(current[0])  # typecode
        tc = tc >> 2
        if tc == 0:
            type = "P"
        elif tc == 1:
            type = "C"
        elif tc == 2:
            type = "B"
        elif tc == 3:
            type = "U"
        else:
            raise tc

        dig1 = str(obd_sensors.hex_to_int(current[0]) & 3)
        dig2 = str(obd_sensors.hex_to_int(current[1]))
        dig3 = str(obd_sensors.hex_to_int(current[2]))
        dig4 = str(obd_sensors.hex_to_int(current[3]))
        dtc.append(type + dig1 + dig2 + dig3 + dig4)
        current = current[4:]
    return dtc
#__________________________________________________________________________


def is_mac_address(str):
    # http://stackoverflow.com/questions/7629643/how-do-i-validate-the-format-of-a-mac-address
    return re.match("[0-9a-f]{2}([:])[0-9a-f]{2}(\\1[0-9a-f]{2}){4}$", str.lower())

#__________________________________________________________________________

def is_hex_string(s):
    encountered_newline = False

    for i in range(0, len(s)):
        if s[i] in ['\r', '\n']:
            # Newlines can be skipped (if they are at the end of the string)
            encountered_newline = True
            continue

        if encountered_newline:
            # A newline has been encountered, but the string is not over yet. Spit it back at the user.
            return False

        # Check if this is a hex digit or a space character
        if (i % 3) == 2:
            # Hex characters separated by a space
            if s[i] != ' ':
                return False
            
            continue
        
        # Check for hex characters.
        if s[i] not in string.hexdigits:
            return False
    
    # This is a hex string! (including len = 0)
    return True

#__________________________________________________________________________


class OBDPort:
    """ OBDPort abstracts all communication with OBD-II device."""

    def __init__(self, portnum, _notify_window, SERTIMEOUT, RECONNATTEMPTS):
        """Initializes port by resetting device and gettings supported PIDs. """
        # These should really be set by the user.
        baud = 38400
        databits = 8
        par = serial.PARITY_NONE  # parity
        sb = 1                   # stop bits
        to = SERTIMEOUT
        self.ELMver = "Unknown"
        self.PortName = "Unknown"

        # state SERIAL is 1 connected, 0 disconnected (connection failed)
        self.State = 0
        self.Error = None
        self._echo_enabled = True  # enabled by default
        self._monitor_mode = False  # flagged if we're in monitor mode
        self._recv_buf = ''

        self._notify_window = _notify_window

        if is_mac_address(portnum):
            debug_display(self._notify_window, DebugEvent.DISPLAY_DEBUG,
                          "Opening interface (bluetooth RFCOMM)")
            self._transport = CreateTransport(TransportType.BLUETOOTH)
        else:
            debug_display(self._notify_window, DebugEvent.DISPLAY_DEBUG,
                          "Opening interface (serial port)")
            self._transport = CreateTransport(TransportType.SERIAL)

        for i in range(0, RECONNATTEMPTS):
            if self._transport.Connect(portnum):
                break
        
        if not self._transport.IsConnected():
            debug_display(self._notify_window, DebugEvent.DISPLAY_ERROR, "Exhausted connection attempts.")
            self.Error = self._transport.GetErrorString()
            return None

        debug_display(self._notify_window, DebugEvent.DISPLAY_DEBUG,
                      "Interface successfully opened")
        debug_display(self._notify_window,
                      DebugEvent.DISPLAY_DEBUG, "Connecting to ECU...")

        self.State = 1
        try:
            self.send_command("ATZ")  # initialize
        except IOError as e:
            debug_display(self._notify_window, 2,
                          "failed to send atz (%s)" % e)
            return None

        # Disable command echo - we don't need it.
        self.enable_echo(False)

        # Verify the ELM327 version
        self.ELMver = self.send_command("ATI")
        if self.ELMver[0:6] != 'ELM327':
            debug_display(self._notify_window, DebugEvent.DISPLAY_DEBUG,
                          "Invalid ELM327 version \"%s\" returned" % self.ELMver)
            self.Error = "Invalid ELM327 version \"%s\" returned" % self.ELMver
            return None

        initial_protocol = 0  # Automatic search
        debug_display(self._notify_window, DebugEvent.DISPLAY_DEBUG,
                      "ELM Version: " + self.ELMver)
        res = self.send_command("ATSP%.1X" % initial_protocol)
        if res != 'OK':
            debug_display(self._notify_window, DebugEvent.DISPLAY_ERROR,
                          "Failed to select protocol 6")
            return None

        # Query available PIDs
        res = self.send_command("0100")
        ready = True
        proto = initial_protocol
        if 'UNABLE TO CONNECT' in res or 'ERROR' in res or 'NO DATA' in res:
            debug_display(self._notify_window, DebugEvent.DISPLAY_ERROR,
                          "Protocol %d: error %s" % (initial_protocol, res))

            # Loop through all possible protocols
            for i in range(0x1, 0xB):
                res = self.send_command("ATTP%.1X" % i)
                if res != 'OK':
                    print(("Unable to select protocol %.1X" % i))
                    break

                res = self.send_command("0100")
                if 'UNABLE TO CONNECT' in res or 'NO DATA' in res or 'ERROR' in res:
                    debug_display(
                        self._notify_window, DebugEvent.DISPLAY_ERROR, "Protocol %d: error %s" % (i, res))
                    ready = False
                    continue
                else:
                    proto = i
                    ready = True
                    break

            # Found a protocol. Save it.
            if ready:
                res = self.send_command("ATSP%.1X" % proto)
                if res != 'OK':
                    debug_display(self._notify_window, DebugEvent.DISPLAY_ERROR,
                                  "Failed to select protocol %.1X" % proto)
                    self.State = 0
                    return None

        if not ready:
            self.Error = "Failed to connect to ECU (is the car on?)"
            self.State = 0
            self.close()
            return None

        # Now connected
        self.State = 1

        debug_display(self._notify_window, DebugEvent.DISPLAY_DEBUG,
                      "Connected to ECU on protocol 0x%.1X" % proto)
        debug_display(self._notify_window,
                      DebugEvent.DISPLAY_DEBUG, "0100 response: " + res)
        return None

    def close(self, reset=True):
        """ Resets device and closes all associated filehandles"""

        # Reset device
        if reset and self.State == 1:
            self.send_command("ATZ")

        self._transport.Close()
        self._transport = None

        self.ELMver = "Unknown"
        self.PortName = "Unknown"

    def send_command(self, cmd, wait_response=True):
        """Sends a command and waits for a response"""
        self.send_raw(cmd + "\r\n")
        if wait_response:
            res = self.recv_result()
            debug_display(self._notify_window, DebugEvent.DISPLAY_DEBUG,
                          "cmd: \"%s\" -> \"%s\"" % (cmd, res.replace('\r', '\\r')))
            if res == "CAN ERROR":
                raise IOError("Disconnected from CAN bus")

            return res

        debug_display(self._notify_window,
                      DebugEvent.DISPLAY_DEBUG, "cmd: \"%s\"" % cmd)
        return None
    
    def send_command_binary(self, cmd, wait_response=True):
        if type(cmd) != bytearray and type(cmd) != bytes:
            raise TypeError('cmd must be convertable to bytearray')

        res = self.send_command(' '.join('%02X' % i for i in bytearray(cmd)), wait_response)
        if wait_response:
            # Convert the response to binary.
            if not is_hex_string(res):
                raise IOError("CAN bus nonbinary response: '%s'" % res)
            
            return bytearray.fromhex(res)
        
        return None

    def send_raw(self, data):
        """Internal use only: not a public interface"""
        if self.State != 1:
            raise IOError("Not connected")

        self._transport.Send(bytes(data, 'ascii'))

    def recv_raw(self, len):
        if self.State != 1:
            raise IOError("Not connected")

        return self._transport.Recv(len)

    def recv_data(self):
        """Receives at least line of data

        raises an IOError if connection is lost"""
        lines = []
        # Continously receive until we accumulate a line
        while b'\r' not in self._recv_buf:
            self._recv_buf += self.recv_raw(1024)

        while b'\r' in self._recv_buf:
            # We've received (one or more) full lines! Return them!
            end = self._recv_buf.find(b'\r')
            line = self._recv_buf[0:end]
            lines.append(str(line, 'ascii'))

            # Remove the received part from the buffer.
            if len(self._recv_buf) > end:
                self._recv_buf = self._recv_buf[end + 1:]
            else:
                self._recv_buf = ''

        return lines

    def recv_result(self, strip_newlines=True):
        """Internal use only: not a public interface
        
        Retrieves the result of a command"""
        #time.sleep(0.01)
        repeat_count = 0
        buffer = bytearray()
        while True:
            data = self._transport.Recv(4096)
            if len(data) == 0:
                print("Socket closed.")
                return None

            buffer.extend(data)

            # Chevron marks end of response
            if b'>' in data:
                break

        data = buffer.decode()

        # Strip off the ending
        end = data.find('\r\r>')
        data = data[0:end]
        if strip_newlines:
            data = data.replace('\r', '')

        return data

    def enable_headers(self, enable):
        """Internal use only: Not a public interface"""
        result = self.send_command("ATH%d" % (
            enable and 1 or 0))  # Disable headers
        if 'OK' in result:
            self._headers_enabled = enable

    def enable_echo(self, enable):
        """Internal use only: not a public interface"""
        result = self.send_command("ATE%d" % (
            enable and 1 or 0))  # toggle echo
        if 'OK' == result:
            self._echo_enabled = enable

    def is_monitoring(self):
        return self._monitor_mode

    def enable_monitor(self, enable):
        """Puts the ELM327 into monitor mode (or takes it out). Use recv_data to read data.

        When in monitor mode, attempting to use any other functionality is undefined."""
        if enable and not self._monitor_mode:
            self.enable_headers(True)  # Enable headers
            self.send_command("ATAL")  # Allow long messages
            self.send_command("ATCAF0")  # Disable CAN Automatic Formatting
            self.send_command("ATMA", wait_response=False)  # MA: Monitor All
            self._monitor_mode = True
        elif not enable and self._monitor_mode:
            # any character input (empty command) will disable monitor mode
            while "STOPPED" not in self.send_command(''):
                pass
            self.send_command("ATCAF1")  # Enable CAN Automatic Formatting
            self.enable_headers(False)  # Disable headers
            self._monitor_mode = False

    def monitor_set_filter(self, id):
        """Filter monitor messages to just a certain ID (or IDs) (X is wildcard character)

        Pass None as id to disable."""
        monitor_enabled = self._monitor_mode
        if monitor_enabled:
            # Disable monitor mode for now
            self.enable_monitor(False)

        # Set filter to ID
        res = self.send_command('ATCRA' + (id is None and '' or ' ' + id))
        if res != 'OK':
            print(("Failed to set CAN filter as " + id))

        # Re-enable the monitor if it was enabled.
        if monitor_enabled:
            self.enable_monitor(True)

    def interpret_result(self, code, data_len, arrayed=False):
        """Internal use only: not a public interface"""
        # Code will be the string returned from the device.
        # It should look something like this:
        # '41 11 00 00\r\r'

        # 9 seems to be the length of the shortest valid response
        if len(code) < 7:
            #raise Exception("BogusCode")
            print(("boguscode?" + code))

        # get the first thing returned, echo should be off
        code = code.split("\r")
        code = code[0]

        # remove whitespace
        code = code.split()
        code = ''.join(code)

        #cables can behave differently
        if code[:6] == "NODATA":  # there is no such sensor
            return "NODATA"

        # first 4 characters are code from ELM
        code = code[4:]

        # Some commands can be split into two, e.g.
        # '41 00 BF 9F B9 93 41 00 98 18 80 11 \r\r'
        # If specified, we'll split the code on each boundary.
        res = []
        res.append(code[:data_len * 2])
        if arrayed:
            i = data_len * 2
            while i < len(code):
                # Append more data
                res.append(code[i+4:i+4 + (data_len * 2)])
                i += 4 + data_len * 2
            
            return res

        # Return just the first result.
        return res[0]

    # get sensor value from command
    def get_sensor_value(self, sensor):
        """Internal use only: not a public interface"""
        command = "01%.2X" % (sensor.id & 0xFF)
        data = self.send_command(command)
        if not is_hex_string(data):
            return data

        if data:
            data = self.interpret_result(data, sensor.length)
            data = sensor.value(data)
        else:
            return "NORESPONSE"

        return data

    # return string of sensor name and value from sensor index
    def sensor(self, sensor_index):
        """Returns 3-tuple of given sensors. 3-tuple consists of
        (Sensor Name (string), Sensor Value (string), Sensor Unit (string) ) """
        sensor = obd_sensors.get_sensor(sensor_index)
        if sensor == None:
            return None

        r = self.get_sensor_value(sensor)
        return (sensor.name, r, sensor.unit)

    def sensor_names(self):
        """Internal use only: not a public interface"""
        names = []
        for s in obd_sensors.SENSORS:
            names.append(s.name)
        return names

    def get_tests_MIL(self):
        statusText = ["Unsupported", "Supported - Completed",
                      "Unsupported", "Supported - Incompleted"]

        statusRes = self.sensor(1)[1]  # GET values
        statusTrans = []  # translate values to text

        statusTrans.append(str(statusRes[0]))  # DTCs

        if statusRes[1] == 0:  # MIL
           statusTrans.append("Off")
        else:
           statusTrans.append("On")

        for i in range(2, len(statusRes)):  # Tests
             statusTrans.append(statusText[statusRes[i]])

        return statusTrans

    #
    # FIXME: j1979 specifies that the program should poll until the number
    # of returned DTCs matches the number indicated by a call to PID 01
    #
    def get_dtc(self):
        """Returns a list of all pending DTC codes. Each element consists of
        a 2-tuple: (DTC code (string), Code description (string) )"""
        dtcLetters = ["P", "C", "B", "U"]
        DTCCodes = []

        # Grab the DTC pseudo-sensor
        r = self.sensor(1)[1]
        dtcNumber = r[0]
        mil = r[1]

        print(("Number of stored DTC: " + str(dtcNumber) + ", MIL " + (mil and "ACTIVE" or "inactive")))
        # get all DTC, 3 per mesg response
        for i in range(0, int((dtcNumber + 2) / 3)):
            res = self.send_command_binary(GET_DTC_COMMAND)
            for i in range(0, 3):
                val = (res[i + 1] << 8) | res[i + 2]  # DTC val as int
                if val == 0:  # skip fill of last packet
                    break

                DTCStr = dtcLetters[(val & 0xC000) >> 14] + \
                                str((val & 0x3000) >> 12) + \
                                str((val & 0x0f00) >> 8) + \
                                str((val & 0x00f0) >> 4) + \
                                str(val & 0x000f)

                DTCCodes.append(["Active", DTCStr])

        # TODO: The following code is broken.
        # Re-read the datasheets for FREEZE DTC, the ELM327 device is not returning
        # the expected amount of data (too little data returned)
        if dtcNumber > 0:
            # read mode 7
            try:
                res = self.send_command_binary(GET_PENDING_DTC_COMMAND)
            except IOError:
                # Bail, we have our codes.
                return DTCCodes

            print(("DTC pending result: " + res))
            for i in range(0, 3):
                val = (res[i + 1] << 8) | res[i + 2]
                if val == 0:  # skip fill of last packet
                    break

                DTCStr = dtcLetters[(val & 0xC000) >> 14] + \
                                str((val & 0x3000) >> 12) + \
                                str((val & 0x0f00) >> 8) + \
                                str((val & 0x00f0) >> 4) + \
                                str(val & 0x000f)
                DTCCodes.append(["Passive", DTCStr])

        return DTCCodes

    def clear_dtc(self):
        """Clears all DTCs and freeze frame data"""
        return self.send_command_binary(CLEAR_DTC_COMMAND)

    def log(self, sensor_index, filename):
         file = open(filename, "w")
         start_time = time.time()
         if file:
              data = self.sensor(sensor_index)
              file.write("%s     \t%s(%s)\n" %
                         ("Time", data[0].strip(), data[2]))
              while 1:
                   now = time.time()
                   data = self.sensor(sensor_index)
                   line = "%.6f,\t%s\n" % (now - start_time, data[1])
                   file.write(line)
                   file.flush()
