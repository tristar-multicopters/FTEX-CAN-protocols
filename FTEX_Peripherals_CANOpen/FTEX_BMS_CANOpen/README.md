# BMS Protocol

## Description

The current FTEX BMS protocol is defined in its entirety within the `FTEX_BMS_CANOpen_Protocol.json`.
As of today, the firmware defines two distinct FTEX BMS activation mode : 
- Fallback to default battery config
- Deactivate powertrain

If defined as fallback to config, the controller will fallback to the default battery config provided.
This allows the controller to keep using powertrain control with another config if the BMS communication fails during runtime.

If defined as stop powertrain, the controller will disable the bike's powertrain in order to prevent any damage that may
occur by the BMS communication fail.

As of right now, it is also possible to change the target BMS CAN node ID:
``` json
  "protocol": {
    "title": "FTEX BMS CANOpen protocol",
    "description": "CANOpen protocol specification that a BMS must follow in order to be compatible with the FTEX controller. See the protocol readme for details on node ID, baud rate, etc. The BMS is passive and must not proactively send anything on CAN. The controller or IoT (or HMI) may perform SDO reads on the BMS whenever it needs a value. The query frequency setting explains how often the controller may query the value from the BMS. The query frequency is approximate, and the controller may request data more or less often than what is specified there. A query frequency of ad-hoc means that the controller may get this value at any time. A query frequency of boot-up means that the controller will get this value once, every time the vehicle powers up. A query frequency of real-time means the controller will get this information very rapidly and very often, so the BMS must keep this value updated rapidly.",
    "version": "2.3.0",
    "CANOpen_NodeID": "5",
    "Notes": "If there are two batteries, the controller will only communicate with the main battery node ID. The second battery should still be on the CAN network for diagnostic purposes, but while the vehicle is running, the main battery node ID should communicate the capabilities of both batteries (eg. total max discharge current)."
  },
```

Another important option supported by our current firmware is the ability to raise a BMS error over CAN. If enabled (`raise_error_on_can`), 
the controller will raise an BMS error over CAN. This error is always accessible via the following CANOpen dictionary parameter : 
```json
"CO_ID_SYSTEM_ERRORS": {
  "CANOpen_Index": "0x2006",
  "Description": "Sytem error state as detected by the controller."
}
```

This setting is defined within the `FTEX_Controller_CANOpen_Protocol.json` : 
```json
"CO_PARAM_BMS_MISSING_CONFIG": {
  "Subindex": "0x31",
  "Access": "R/W",
  "Type": "uint8_t",
  "Description": "Behavior the controller should adopt if the BMS is missing. Set bitmask flags to enable/disable controller behaviors on a missing BMS.",
  "Valid_Range": "[0, 255]",
  "Persistence": "Persistent",
  "Notes": "The BMS must send frequent heartbeats to be detected as alive, and it must send valid messages to the controller. CO_PARAM_BMS_MISSING_CONFIG is only relevant if CO_PARAM_BMS_PROTOCOL_CONFIG !=0, otherwise this parameter is ignored. Default is 1.",
  "Bitmask_Definition": {
    "0x00000000": {
      "Bitmask_Name": "fallback_to_config",
      "Bitmask_Description": "If we lose the BMS communication, fallback to the configuration that is in the CO_PARAM_BATTERY_* parameters."
    },
    "0x00000001": {
      "Bitmask_Name": "stop_powertrain",
      "Bitmask_Description": "If we lose the BMS communication, stop the powertrain and prevent any power from being pushed to the motor."
    },
    "0x00000002": {
      "Bitmask_Name": "raise_error_on_can",
      "Bitmask_Description": "If we lose the BMS communication, raise an error on the controller's CAN parameter."
    }
  }
}
```

## Validation

Each BMS parameters has its own defined input value range. Additional cross parameters validation is also provided within the notes section of the parameter.
If the BMS sends a number of invalid inputs, the controller will deactivate the BMS communication, preventing any potential damage that could be triggered by invalid parameters.
As of right now, this number of invalid input threshold is pre-defined as 10 for the duration of the bike runtime.

Example : Undervoltage parameter. This values has an valid input range of [2000, 10000] and an additional note,
          this value needs to be lower than the CO_PARAM_EXTERNAL_BMS_OVERVOLTAGE_LIMIT. 
```json
"CO_PARAM_EXTERNAL_BMS_UNDERVOLTAGE_LIMIT": {
  "Subindex": "0x06",
  "Access": "R",
  "Type": "uint16_t",
  "Unit": "centivolts",
  "Description": "Undervoltage cutoff of the BMS. This value needs to be lower than CO_PARAM_EXTERNAL_BMS_OVERVOLTAGE_LIMIT.",
  "Query_frequency": "boot-up",
  "Valid_Range": "[2000, 10000]"
}
```
