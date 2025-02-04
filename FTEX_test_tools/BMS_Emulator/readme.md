# BMS Emulator

## Overview
The BMS Emulator is a tool designed to emulate the behavior of a Battery Management System (BMS) on the CAN, for testing purposes.

## Features
- Simulates BMS communication protocols
- Configurable parameters for various test scenarios
- Real-time data monitoring and logging

## Installation
1. You need python first, then
2. Run this from the command line: pip install -p requirements.txt

## Usage
1. Configure the emulator settings as needed (using bms.eds and bms_values.json).
2. Start the emulator from the windows command line, by running: python bms_emulator.py
3. Select a unique COM port (ie. not used by something else at the same time) 
3. You can now interact with a BMS over CAN.

### Notes
If you need to change the values returned from the BMS, you need to start and stop the emulator (it pulls values from the values.json file only once, it is not dynamic)
