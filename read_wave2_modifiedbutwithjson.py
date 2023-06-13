from itertools import count
import bluepy.btle as btle
import argparse
import signal
import struct
import sys
import time
import os
import csv
import json
import re
import adafruit_am2320
import board
import busio
import requests
import socket
import asyncio

host = socket.gethostname()
ip = socket.gethostbyname(host)
print(ip)
newHeaders = {'Content-type': 'application/json', 'Accept': 'text/plain'}
#url = 'http://'+ip+'/api/Logs'
url = 'http://10.176.69.101:5206/api/Logs'
i2c = busio.I2C(board.SCL, board.SDA)

class Wave2():

    def get_piID():
        with open ("/proc/cpuinfo") as file:
            for line in file.readlines():
                if re.search(r"1000000",line):
                    return (line[10:]).split("\n")[0]


    def getTime(self):
        return [int(time.time())]

    CURR_VAL_UUID = btle.UUID("b42e4dcc-ade7-11e4-89d3-123b93f75cba")

    def __init__(self, serial_number):
        self._periph = None
        self._char = None
        self.mac_addr = None
        self.serial_number = serial_number

    def is_connected(self):
        try:
            return self._periph.getState() == "conn"
        except Exception:
            return False

    def discover(self):
        scan_interval = 0.1
        timeout = 3
        scanner = btle.Scanner()
        for _count in range(int(timeout / scan_interval)):
            advertisements = scanner.scan(scan_interval)
            for adv in advertisements:
                if self.serial_number == _parse_serial_number(adv.getValue(btle.ScanEntry.MANUFACTURER)):
                    return adv.addr
        return None

    def connect(self, retries=1):
        tries = 0
        while (tries < retries and self.is_connected() is False):
            tries += 1
            if self.mac_addr is None:
                self.mac_addr = self.discover()
            try:
                self._periph = btle.Peripheral(self.mac_addr)
                self._char = self._periph.getCharacteristics(uuid=self.CURR_VAL_UUID)[0]
            except Exception:
                if tries == retries:
                    raise
                else:
                    pass

    def read(self):
        rawdata = self._char.read()
        return CurrentValues.from_bytes(rawdata)

    def disconnect(self):
        if self._periph is not None:
            self._periph.disconnect()
            self._periph = None
            self._char = None


class CurrentValues():

    def __init__(self, humidity, radon_sta, radon_lta, temperature):
        self.humidity = humidity
        self.radon_sta = radon_sta
        self.radon_lta = radon_lta
        self.temperature = temperature

    @classmethod
    def from_bytes(cls, rawdata):
        ID = Wave2.get_piID()
        sensor = adafruit_am2320.AM2320(i2c)
        print(ID)
        data = struct.unpack("<4B8H", rawdata)
        if data[0] != 1:
            raise ValueError("Incompatible current values version (Expected 1, got {})".format(data[0]))
        json_objection = {
            "id": "",
            "serialnumber":ID,
            "outside":{
                "Temperature":sensor.temperature,
                "Humidity":sensor.relative_humidity
    },
            "inside":{
                "Temperature":data[6] / 100,
                "Humidity":data[1] / 2,
                "Radon":data[4],
                "RadonLTA":data[5]
    }
}

        return json_objection
        #return [data[1]/2.0, data[4], data[5], data[6]/100.0]

    def __str__(self):
        msg = "Humidity: {} %rH, ".format(self.humidity)
        msg += "Temperature: {} *C, ".format(self.temperature)
        msg += "Radon STA: {} Bq/m3, ".format(self.radon_sta)
        msg += "Radon LTA: {} Bq/m3".format(self.radon_lta)
        return msg
    



def _parse_serial_number(manufacturer_data):
    try:
        (ID, SN, _) = struct.unpack("<HLH", manufacturer_data)
    except Exception:  # Return None for non-Airthings devices
        return None
    else:  # Executes only if try-block succeeds
        if ID == 0x0334:
            return SN


def _argparser():
    parser = argparse.ArgumentParser(prog="read_wave2", description="Script for reading current values from a 2nd Gen Wave product")
    parser.add_argument("SERIAL_NUMBER", type=int, help="Airthings device serial number found under the magnetic backplate.")
    parser.add_argument("SAMPLE_PERIOD", type=int, default=60, help="Time in seconds between reading the current values")
    args = parser.parse_args()
    return args


def _main():
    args = _argparser()
    wave2 = Wave2(args.SERIAL_NUMBER)
    id = Wave2.get_piID()

   # geturl = 'http://10.176.69.101:5206/api/Dataloggers/'+id
   # puturl = 'http://10.176.69.101:5206/api/Dataloggers/'

    

    #getreponse = requests.get(geturl, headers=newHeaders)
     #   if(getreponse = "something null lol change this")
      #      wtf = requests.post(puturl)
    

    def _signal_handler(sig, frame):
        wave2.disconnect()
        sys.exit(0)

    signal.signal(signal.SIGINT, _signal_handler)

    with open('datalog.json', 'w') as file:
            

            while True:
                wave2.connect(retries=3)
                current_values = wave2.read()
                print(current_values)
                print(id)
                json.dump(current_values,file, indent=4)

                response = requests.post(url, json.dumps(current_values), headers=newHeaders)
                print(response)
               # file.write(current_values) #the readings
              #  writer.writerow(outsidereadings) #the reading of outside values
                wave2.disconnect()
                time.sleep(args.SAMPLE_PERIOD)

if __name__ == "__main__":
    _main()
