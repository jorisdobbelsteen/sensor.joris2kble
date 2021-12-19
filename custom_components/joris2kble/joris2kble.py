import struct
import time
from collections import namedtuple

import logging
from datetime import datetime

import bluepy.btle as btle

from uuid import UUID

_LOGGER = logging.getLogger(__name__)

# Use full UUID since we do not use UUID from bluepy.btle
#CHAR_SMARTMETER_POWER_SVC         = UUID("af880000-558d-47ca-bd46-cb3b6e84b8ac")
#CHAR_SMARTMETER_GAS_SVC           = UUID("4bf70000-e031-4a4f-a0bd-64459a589768")

CHAR_SMARTMETER_POWER_CONSUMPTION = UUID("af880001-558d-47ca-bd46-cb3b6e84b8ac")
CHAR_SMARTMETER_POWER_TARIFF      = UUID("af880002-558d-47ca-bd46-cb3b6e84b8ac")
CHAR_SMARTMETER_POWER_POWER       = UUID("af880003-558d-47ca-bd46-cb3b6e84b8ac")
CHAR_SMARTMETER_POWER_PHASEINFO   = UUID("af880004-558d-47ca-bd46-cb3b6e84b8ac")
CHAR_SMARTMETER_GAS_CONSUMPTION   = UUID("4bf70001-e031-4a4f-a0bd-64459a589768")

# These are tricky: they might be either for power or gas, depending on which
# service they are in
#CHAR_SMARTMETER_DATE              = UUID(10769)

Characteristic = namedtuple('Characteristic', ['uuid', 'name', 'format'])

class Joris2kBleDeviceInfo:
    def __init__(self, mac='', device_name=''):
        self.mac = mac
        self.device_name = device_name

    def __str__(self):
        return "Mac: {} Device:{}".format(
            self.mac, self.device_name)

sensors_characteristics_uuid = [CHAR_SMARTMETER_POWER_CONSUMPTION, CHAR_SMARTMETER_POWER_TARIFF,
                                #CHAR_SMARTMETER_POWER_POWER, CHAR_SMARTMETER_POWER_PHASEINFO,
                                CHAR_SMARTMETER_GAS_CONSUMPTION,
                                #CHAR_SMARTMETER_DATE,
                                ]

sensors_characteristics_uuid_str = [str(x) for x in sensors_characteristics_uuid]

def _checkedscale(value, divisor):
    if value == -1:
        return None
    return float(value) / divisor

class PowerConsumptionDecode:
    def decode_data(self, raw_data):
        val = struct.unpack("<iiii", raw_data)
        data = {}
        data['power_consumption_tariff1'] = _checkedscale(val[0], 1e3)
        data['power_consumption_tariff2'] = _checkedscale(val[1], 1e3)
        data['power_delivery_tariff1'] = _checkedscale(val[2], 1e3)
        data['power_delivery_tariff2'] = _checkedscale(val[3], 1e3)
        return data

class PowerTariffDecode:
    def decode_data(self, raw_data):
        val = struct.unpack("<B", raw_data)
        data = {}
        data['current_tariff'] = val[0]
        return data

class GasConsumptionDecode:
    def decode_data(self, raw_data):
        val = struct.unpack("<i", raw_data)
        data = {}
        data['gas_consumption'] = _checkedscale(val[0], 1e3)
        return data

sensor_decoders = {str(CHAR_SMARTMETER_POWER_CONSUMPTION):PowerConsumptionDecode(),
                   str(CHAR_SMARTMETER_POWER_TARIFF):PowerTariffDecode(),
                   str(CHAR_SMARTMETER_GAS_CONSUMPTION):GasConsumptionDecode(),
                   }


class Joris2kBleDetect:
    def __init__(self, scan_interval, mac=None):
        self.deviceinfos = {}
        self.devicemacs = [] if mac is None else [mac]
        self.sensors = []
        self.sensordata = {}
        self.scan_interval = scan_interval
        self.last_scan = -1
        self._dev = None

    def find_devices(self, scans=50, timeout=0.1):
        # Search for devices, scan for BLE devices scans times for timeout seconds
        # Use "complete name" in advertisement to detect sensor
        scanner = btle.Scanner()
        for _count in range(scans):
            advertisements = scanner.scan(timeout)
            for adv in advertisements:
                name = adv.getValue(btle.ScanEntry.COMPLETE_LOCAL_NAME)
                if name is not None and name == "SmartMeter":
                    if adv.addr not in self.devicemacs:
                        self.devicemacs.append(adv.addr)
                        self.deviceinfos[adv.addr] = Joris2kBleDeviceInfo(mac=adv.addr, device_name=name)

        _LOGGER.debug("Found {} Joris2k BLE device(s)".format(len(self.devicemacs)))
        return len(self.devicemacs)

    def connect(self, mac, retries=5):  
        tries = 0
        self.disconnect()
        while (tries < retries):
            tries += 1
            try:
                self._dev = btle.Peripheral(mac.lower())
                break
            except Exception as e:
                print(e)
                if tries == retries:
                    pass
                else:
                    _LOGGER.debug("Retrying {}".format(mac))

    def disconnect(self):
        if self._dev is not None:
            self._dev.disconnect()
            self._dev = None

    def get_info(self):
        return self.deviceinfos

    def get_sensors(self):
        self.sensors = {}
        for mac in self.devicemacs:
            self.connect(mac)
            if self._dev is not None:
                try:
                    characteristics = self._dev.getCharacteristics()
                    sensor_characteristics =  []
                    for characteristic in characteristics:
                        _LOGGER.debug(characteristic)
                        if characteristic.uuid in sensors_characteristics_uuid_str:
                            sensor_characteristics.append(characteristic)
                    self.sensors[mac] = sensor_characteristics
                except btle.BTLEDisconnectError:
                        _LOGGER.exception("Disconnected")
                        self._dev = None
            self.disconnect()
        return self.sensors

    def get_sensor_data(self):
        if time.monotonic() - self.last_scan > self.scan_interval or self.last_scan == -1:
            self.last_scan = time.monotonic()
            for mac, characteristics in self.sensors.items():
                self.connect(mac)
                if self._dev is not None:
                    try:
                        for characteristic in characteristics:
                            if str(characteristic.uuid) in sensor_decoders:
                                char = self._dev.getCharacteristics(uuid=characteristic.uuid)[0]
                                data = char.read()
                                sensor_data = sensor_decoders[str(characteristic.uuid)].decode_data(data)
                                _LOGGER.debug("{} Got sensordata {}".format(mac, sensor_data))
                                if self.sensordata.get(mac) is None:
                                    self.sensordata[mac] = sensor_data
                                else:
                                    self.sensordata[mac].update(sensor_data)
                    except btle.BTLEDisconnectError:
                        _LOGGER.exception("Disconnected")
                        self._dev = None
                self.disconnect()

        return self.sensordata

if __name__ == "__main__":
    logging.basicConfig()
    _LOGGER.setLevel(logging.DEBUG)
    ad = Joris2kBleDetect(0)
    num_dev_found = ad.find_devices()
    if num_dev_found > 0:
        devices = ad.get_info()
        for mac, dev in devices.items():
            _LOGGER.info("{}: {}".format(mac, dev))

        devices_sensors = ad.get_sensors()
        for mac, sensors in devices_sensors.items():
            for sensor in sensors:
                _LOGGER.info("{}: {}".format(mac, sensor))

        sensordata = ad.get_sensor_data()
        for mac, data in sensordata.items():
            for name, val in data.items():
                _LOGGER.info("{}: {}: {}".format(mac, name, val))
