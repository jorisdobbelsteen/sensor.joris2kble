# sensor.joris2kble

hassio support for BLE sensors.

Much of the code to build this component was inspired by this project:
* https://github.com/custom-components/sensor.airthings_wave

## Getting started

Download
```
/custom_components/airthings_wave/
```
into
```
<config directory>/custom_components/airthings_wave/
```
**Example configuration.yaml:**

```yaml
# Example configuration.yaml entry
sensor:
  - platform: joris2kble
    scan_interval: 120
```
### Optional Configuration Variables

**mac**

  (string)(Optional) The airthings_wave mac address, if not provided will scan for all airthings devices at startup

**scan_interval**

  (string)(Optional) The interval between polls. Defaults to 60 seconds (1 minutes)

## Limitations

You main need to pair with the sensor using guideline described in since the sensor has a 
https://gitlab.com/jorisdobbelsteen/python-joris2k-ble

## Known Issues

* Not yet able to specify the `monitored_conditions` configuration

* No translations available yet


## Hardware Requirements

* Supported sensor

* Bluetooth Adapter that support Bluetooth Low Energy (at least version 4.2). The Raspberry Pi 3/4 built-in Bluetooth adapter works.
