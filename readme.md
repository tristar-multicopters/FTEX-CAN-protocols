# FTEX CANOpen Protocol

This folder contains the public and internal FTEX protocols. Most importantly are the CANOpen protocol which drive all of the configurability of the FTEX controller platform.

#### Notable files:
- *FTEX_Controller_CANOpen_Protocol.json: this is our "public" protocol, shareable with third parties*
- *FTEX_Controller_JSON_Schema.json: this is the JSON schema validation file*
- *FTEX_Schema_validator.py: this script validates a JSON file against a schema*

## Protocol specification:
FTEX follows standard CANOpen protocol: https://www.can-cia.org/canopen/

FTEX uses SDO expedited transfer for transferring objects with up to four bytes.

![CANframe](https://drive.google.com/uc?export=view&id=1d4pl2eg4_aW4hmxD5vwenTk4lDIGYi2R "Standard CAN frame")

Here, the <CMD> byte is dependent on the length of the data that are to be written or read. <CMD> can be one of the following values:
- 1 byte write: 0x2F
- 2 bytes write: 0x2B
- 3 bytes write: 0x27
- 4 bytes write: 0x23

For read operations:
- 1 byte read: 0x4F
- 2 bytes read: 0x4B
- 3 bytes read: 0x47
- 4 bytes read: 0x43

The <Data> field is written with the data that are to be written, if applicable; the LSB of the data is entered in byte 4. The data field is reserved/unused for read operations.

### Node ID
- 0x01: Node ID of the FTEX master controller
- 0x02: Node ID if the FTEX IoT module extension
- 0x03: Node ID of the FTEX slave controller (optional)
(This is only used in the case of dual motor, with one controller as master and one controller as slave. Therefore, this is only applicable in case of dual communication. You should only communicate with the master controller)"
- 0x04: Default node ID of the HMI (if present)
- 0x05: Default node ID of the battery/BMS (if present)
- 0x10: Default node ID of the PAS sensor (if present)

For now, the node IDs are not configurable. Contact FTEX otherwise.

### Baud rate
Default baud rate = 500Kbs

Baud rate can be configured with the CO_PARAM_BAUD_RATE parameter.

### Parameters persistence
Parameters are marked with a persistence of either *real-time*, *persistent*, or *both*.
- Real-time: the parameter will be immediately applied to the controller, but it won't persist after a restart
- Persistent: the parameter will be applied after the save command is ran (see "communication specification"), and be persistent even after a reboot. To save the parameter to the memory, the persistent save procedure below must be followed.
- Both: the parameter is immmediately applied to the controller, and it may also be saved to the controller's memory. To save the parameter to the memory, the persistent save procedure below must be followed.

A parameters change is not persistent (ie. saved after reboots) unless you use the following procedure: 
1 - Write in the parameter CO_PARAM_SAVE_PARAMETERS the value 0xD5A3 to let the controller know that save-persistent parameters will be changed.
2 - Change all of the desired parameters, respecting the range value of each one.
3 - Write in the parameter CO_PARAM_SAVE_PARAMETERS the value 0xC2E5.

Executing step 3 will make the controller save the parameters, reset and apply the new values.

### CAN peripherals requirements
The FTEX controller can interact with other peripherals on the CAN bus, such as the IoT, the HMI and the BMS. 
However, the following must be supported by the peripherals on the CAN bus to use all of the FTEX controller features.

#### HMI and BMS
- Node ID: see the node ID section above. 
- Heartbeat: An HMI communicating over CAN bus with the controller must send CAN heartbeats (https://www.can-cia.org/can-knowledge/canopen/error-control-protocols - Heartbeat section)
The controller expects healthy heartbeats from the HMI at least every 50ms.
If no HMI heartbeats are detected within a 500ms window, the controller determines that screen communication is lost, and disables HMI-driven features like throttle and cruise over CAN. Also, an error is raised over CAN if there are missing heartbeats from the HMI or from the BMS.

*Todos:*
- Add protocol communication specification [DONE]
- Add BMS protocol in JSON format [DONE]
- Add autotune JSON protocol [DONE]
- Add internal FTEX protocol for motor configuration [DONE]
- Add internal FTEX protocol specification for DFU [DONE]
- Add (or redo) internal FTEX protocol specification for custom IoT stuff
- Add schema validation in the CI/CD pipeline [DONE]
- Controller firmware should consume the newly minted JSON files [DONE]
- Config and diags tools should consume the newly minted JSON files too
- Add Error codes definition [DONE]
- schema validation of unique CO_ID name, unique param names, unique index, and unique subindex within an index [DONE]
