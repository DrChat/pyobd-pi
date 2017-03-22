#!/usr/bin/env python
###########################################################################
# obd_sensors.py
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

def hex_to_int(str):
    return int(str, 16)

def maf(code):
    code = hex_to_int(code)
    return code * 0.00132276

def throttle_pos(code):
    code = hex_to_int(code)
    return code * 100.0 / 255.0

def intake_m_pres(code): # in kPa
    code = hex_to_int(code)
    return code / 0.14504
  
def rpm(code):
    code = hex_to_int(code)
    return code / 4

def speed(code):
    code = hex_to_int(code)
    return code / 1.609

def percent_scale(code):
    code = hex_to_int(code)
    return code * 100.0 / 255.0

def timing_advance(code):
    code = hex_to_int(code)
    return (code - 128) / 2.0

def sec_to_min(code):
    code = hex_to_int(code)
    return code / 60

def temp(code):
    code = hex_to_int(code)
    c = code - 40 
    return 32 + (9 * c / 5) 

def cpass(code):
    #fixme
    return code

def fuel_trim_percent(code):
    code = hex_to_int(code)
    #return (code - 128.0) * 100.0 / 128
    return (code - 128) * 100 / 128

def dtc_decrypt(code):
    #first byte is byte after PID and without spaces
    num = hex_to_int(code[:2]) #A byte
    res = []

    if num & 0x80: # is mil light on
        mil = 1
    else:
        mil = 0
        
    # bit 0-6 are the number of dtc's. 
    num = num & 0x7f
    
    res.append(num)
    res.append(mil)
    
    numB = hex_to_int(code[2:4]) #B byte
      
    for i in range(0,3):
        res.append(((numB>>i)&0x01)+((numB>>(3+i))&0x02))
    
    numC = hex_to_int(code[4:6]) #C byte
    numD = hex_to_int(code[6:8]) #D byte
       
    for i in range(0,7):
        res.append(((numC>>i)&0x01)+(((numD>>i)&0x01)<<1))
    
    res.append(((numD>>7)&0x01)) #EGR SystemC7  bit of different 
    
    return res

def hex_to_bitstring(str):
    bitstring = ''
    for i in str:
        # silly type safety, we don't want to eval random stuff
        if type(i) == type('') or type(i) == type(u''): 
            v = eval("0x%s" % i)
            if v & 8 :
                bitstring += '1'
            else:
                bitstring += '0'
            if v & 4:
                bitstring += '1'
            else:
                bitstring += '0'
            if v & 2:
                bitstring += '1'
            else:
                bitstring += '0'
            if v & 1:
                bitstring += '1'
            else:
                bitstring += '0'                
    return bitstring

class Sensor:
    def __init__(self, shortName, sensorName, id, bytesReturned, sensorValueFunction, u):
        self.shortname = shortName
        self.name   = sensorName
        self.id     = id
        self.length = bytesReturned
        self.value  = sensorValueFunction
        self.unit   = u

SENSORS = [
    Sensor("pids_00"               , "Supported PIDs [1-32]"    	, 0x00, 4, hex_to_bitstring ,""       ),
    Sensor("dtc_status"            , "S-S DTC Cleared"				, 0x01, 4, dtc_decrypt      ,""       ),
    Sensor("dtc_ff"                , "DTC C-F-F"					, 0x02, 2, cpass            ,""       ),
    Sensor("fuel_status"           , "Fuel System Stat"				, 0x03, 2, cpass            ,""       ),
    Sensor("load"                  , "Calc Load Value"				, 0x04, 1, percent_scale    ,""       ),
    Sensor("temp"                  , "Coolant Temp"					, 0x05, 1, temp             ,"F"      ),
    Sensor("short_term_fuel_trim_1", "S-T Fuel Trim"				, 0x06, 1, fuel_trim_percent,"%"      ),
    Sensor("long_term_fuel_trim_1" , "L-T Fuel Trim"				, 0x07, 1, fuel_trim_percent,"%"      ),
    Sensor("short_term_fuel_trim_2", "S-T Fuel Trim"				, 0x08, 1, fuel_trim_percent,"%"      ),
    Sensor("long_term_fuel_trim_2" , "L-T Fuel Trim"				, 0x09, 1, fuel_trim_percent,"%"      ),
    Sensor("fuel_pressure"         , "FuelRail Pressure"			, 0x0A, 1, cpass            ,""       ),
    Sensor("manifold_pressure"     , "Intk Manifold"				, 0x0B, 1, intake_m_pres    ,"psi"    ),
    Sensor("rpm"                   , "Engine RPM"					, 0x0C, 2, rpm              ,""       ),
    Sensor("speed"                 , "Vehicle Speed"				, 0x0D, 1, speed            ,"MPH"    ),
    Sensor("timing_advance"        , "Timing Advance"				, 0x0E, 1, timing_advance   ,"degrees"),
    Sensor("intake_air_temp"       , "Intake Air Temp"				, 0x0F, 1, temp             ,"F"      ),
    Sensor("maf"                   , "AirFlow Rate(MAF)"			, 0x10, 2, maf              ,"lb/min" ),
    Sensor("throttle_pos"          , "Throttle Position"			, 0x11, 1, throttle_pos     ,"%"      ),
    Sensor("secondary_air_status"  , "2nd Air Status"				, 0x12, 1, cpass            ,""       ),
    Sensor("o2_sensor_positions"   , "Loc of O2 sensors"			, 0x13, 1, cpass            ,""       ),
    Sensor("o211"                  , "O2 Sensor: 1 - 1"				, 0x14, 2, fuel_trim_percent,"%"      ),
    Sensor("o212"                  , "O2 Sensor: 1 - 2"				, 0x15, 2, fuel_trim_percent,"%"      ),
    Sensor("o213"                  , "O2 Sensor: 1 - 3"				, 0x16, 2, fuel_trim_percent,"%"      ),
    Sensor("o214"                  , "O2 Sensor: 1 - 4"				, 0x17, 2, fuel_trim_percent,"%"      ),
    Sensor("o221"                  , "O2 Sensor: 2 - 1"				, 0x18, 2, fuel_trim_percent,"%"      ),
    Sensor("o222"                  , "O2 Sensor: 2 - 2"				, 0x19, 2, fuel_trim_percent,"%"      ),
    Sensor("o223"                  , "O2 Sensor: 2 - 3"				, 0x1A, 2, fuel_trim_percent,"%"      ),
    Sensor("o224"                  , "O2 Sensor: 2 - 4"				, 0x1B, 2, fuel_trim_percent,"%"      ),
    Sensor("obd_standard"          , "OBD Designation"				, 0x1C, 1, cpass            ,""       ),
    Sensor("o2_sensor_position_b"  , "Loc of O2 sensor" 			, 0x1D, 1, cpass            ,""       ),
    Sensor("aux_input"             , "Aux input status"				, 0x1E, 1, cpass            ,""       ),
    Sensor("engine_time"           , "Engine Start MIN"				, 0x1F, 2, sec_to_min       ,"min"    ),
    # 0x20 = PIDs supported [0x21 - 0x40]
    Sensor("pids_20"               , "Supported PIDs [33-64]"    	, 0x20, 4, hex_to_bitstring ,""       ),
    # Sensor("mil_distance"          , "Distance traveled with MIL"   , 0x21, 2, None             ,"km"     ),
    Sensor("fuel_level"            , "Fuel tank level input"		, 0x2F, 1, percent_scale    ,"%"      ),
    Sensor("pids_40"               , "Supported PIDs [65-96]"    	, 0x40, 4, hex_to_bitstring ,""       ),
    Sensor("engine_mil_time"       , "Engine Run MIL"				, 0x4D, 2, sec_to_min       ,"min"    ),
    Sensor("pids_60"               , "Supported PIDs [97-128]"    	, 0x60, 4, hex_to_bitstring ,""       ),
    Sensor("pids_80"               , "Supported PIDs [129-160]"    	, 0x80, 4, hex_to_bitstring ,""       ),
    ]
     
def get_sensor(id):
    for sensor in SENSORS:
        if sensor.id == id:
            return sensor
    
    return None
    
#___________________________________________________________

def test():
    for i in SENSORS:
        print i.name, i.value("F")

if __name__ == "__main__":
    test()
