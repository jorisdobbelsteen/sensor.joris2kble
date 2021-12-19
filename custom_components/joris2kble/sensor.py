"""
Support for Joris2k BLE Smart Meter sensor.
"""
import logging
from datetime import timedelta
from math import exp

from .joris2kble import Joris2kBleDetect

import homeassistant.helpers.config_validation as cv
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    STATE_CLASS_MEASUREMENT,
    SensorEntity,
)

from homeassistant.const import (ATTR_DEVICE_CLASS, ATTR_ICON, CONF_MAC,
                                 CONF_NAME, CONF_SCAN_INTERVAL,
                                 DEVICE_CLASS_ENERGY,
                                 DEVICE_CLASS_GAS,
                                 ENERGY_KILO_WATT_HOUR,
                                 VOLUME_CUBIC_METERS,
                                 EVENT_HOMEASSISTANT_STOP,
                                 STATE_UNKNOWN)

_LOGGER = logging.getLogger(__name__)
CONNECT_TIMEOUT = 5
SCAN_INTERVAL = timedelta(seconds=300)

DOMAIN = 'joris2kble'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_MAC, default=''): cv.string,
    vol.Optional(CONF_SCAN_INTERVAL, default=SCAN_INTERVAL): cv.time_period,
})


class Sensor:
    def __init__(self, unit, unit_scale, device_class, icon):
        self.unit = unit
        self.unit_scale = unit_scale
        self.device_class = device_class
        self.icon = icon

    def set_parameters(self, parameters):
        self.parameters = parameters

    def set_unit_scale(self, unit, unit_scale):
        self.unit = unit
        self.unit_scale = unit_scale

    def transform(self, value):
        if self.unit_scale is None:
            return value
        return round(float(value * self.unit_scale), 2)

    def get_extra_attributes(self, data):
        return {}

DEVICE_SENSOR_SPECIFICS = { "power_consumption_tariff1": Sensor(ENERGY_KILO_WATT_HOUR, None, DEVICE_CLASS_ENERGY, None),
                            "power_consumption_tariff2": Sensor(ENERGY_KILO_WATT_HOUR, None, DEVICE_CLASS_ENERGY, None),
                            "power_delivery_tariff1": Sensor(ENERGY_KILO_WATT_HOUR, None, DEVICE_CLASS_ENERGY, None),
                            "power_delivery_tariff2": Sensor(ENERGY_KILO_WATT_HOUR, None, DEVICE_CLASS_ENERGY, None),
                            "current_tariff": Sensor(None, None, None, None),
                            "gas_consumption": Sensor(VOLUME_CUBIC_METERS, None, DEVICE_CLASS_GAS, None)
                           }

def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Joris2k BLE sensor."""
    scan_interval = config.get(CONF_SCAN_INTERVAL).total_seconds()
    mac = config.get(CONF_MAC)
    mac = None if mac == '' else mac

    _LOGGER.debug("Searching for Joris2k BLE sensors...")
    detect = Joris2kBleDetect(scan_interval, mac)
    try:
        if mac is None:
            num_devices_found = detect.find_devices()
            _LOGGER.info("Found {} Joris2k BLE device(s)".format(num_devices_found))

        if mac is None and num_devices_found == 0:
            _LOGGER.warning("No Joris2k BLE devices found.")
            return

        _LOGGER.debug("Getting info about device(s)")
        devices_info = detect.get_info()
        for mac, dev in devices_info.items():
            _LOGGER.info("{}: {}".format(mac, dev))

        _LOGGER.debug("Getting sensors")
        devices_sensors = detect.get_sensors()
        for mac, sensors in devices_sensors.items():
            for sensor in sensors:
                _LOGGER.debug("{}: Found sensor UUID: {} Handle: {}".format(mac, sensor.uuid, sensor.handle))

        #
        # This code seems to imply the sensor must be available and ready at startup!
        # That might not always be the best situations to be in, so this might need
        # a little overhaul in the future.
        #
        _LOGGER.debug("Get initial sensor data to populate HA entities")
        ha_entities = []
        sensordata = detect.get_sensor_data()
        for mac, data in sensordata.items():
            for name, val in data.items():
                _LOGGER.debug("{}: {}: {}".format(mac, name, val))
                ha_entities.append(Joris2kBleSensor(mac, name, detect, devices_info[mac],
                                                   DEVICE_SENSOR_SPECIFICS[name]))
    except:
        _LOGGER.exception("Failed intial setup.")
        return

    add_entities(ha_entities, True)


class Joris2kBleSensor(SensorEntity):

    _attr_state_class = STATE_CLASS_MEASUREMENT

    """General Representation of an Joris2k BLE sensor."""
    def __init__(self, mac, name, device, device_info, sensor_specifics):
        """Initialize a sensor."""
        self.device = device
        self._mac = mac
        self._name = '{}-{}'.format(mac.upper(), name)
        _LOGGER.debug("Added sensor entity {}".format(self._name))
        self._sensor_name = name

        self._device_class = sensor_specifics.device_class
        self._state = STATE_UNKNOWN
        self._sensor_specifics = sensor_specifics

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return self._sensor_specifics.icon

    @property
    def device_class(self):
        """Return the icon of the sensor."""
        return self._sensor_specifics.device_class

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._sensor_specifics.unit

    @property
    def unique_id(self):
        return self._name

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the sensor."""
        attributes = self._sensor_specifics.get_extra_attributes(self._state)
        #try:
        #    attributes[ATTR_DEVICE_DATE_TIME] = self.device.sensordata[self._mac]['date_time']
        #except KeyError:
        #    _LOGGER.exception("No date time of sensor reading data available.")
        return attributes

    def update(self):
        """Fetch new state data for the sensor.
        This is the only method that should fetch new data for Home Assistant.
        """
        self.device.get_sensor_data()
        value = self.device.sensordata[self._mac][self._sensor_name]
        self._state = self._sensor_specifics.transform(value)
        _LOGGER.debug("State {} {}".format(self._name, self._state))
