import serial
import platform

HAS_PYBLUEZ = True
try:
    import bluetooth as bt
except ImportError:
    HAS_PYBLUEZ = False

def scanBluetooth(time=4):
    """Scan for available bluetooth ports. Returns a list of MAC addresses"""
    if not HAS_PYBLUEZ:
      return []

    available = []
    try:
      available = bt.discover_devices(time)
    except IOError:
      return []
    
    return available

def scanSerial():
    """scan for available ports. return a list of serial names"""
    available = []
 # Enable Bluetooh connection
    for i in range(10):
      try:
		s = serial.Serial("/dev/rfcomm"+str(i))
		available.append( (str(s.port)))
		s.close()   # explicit close 'cause of delayed GC in java
      except serial.SerialException:
		pass
 # Enable USB connection
    for i in range(256):
      try:
        s = serial.Serial("/dev/ttyUSB"+str(i))
        available.append(s.portstr)
        s.close()   # explicit close 'cause of delayed GC in java
      except serial.SerialException:
        pass
 # Enable obdsim 
    #for i in range(256):
      #try: #scan Simulator
        #s = serial.Serial("/dev/pts/"+str(i))
        #available.append(s.portstr)
        #s.close()   # explicit close 'cause of delayed GC in java
      #except serial.SerialException:
        #pass
    
    return available