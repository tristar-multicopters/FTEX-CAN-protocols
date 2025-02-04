# BMS Automated Tester

## Introduction
The BMS Automated Tester is designed to facilitate the testing of Battery Management Systems (BMS) using the FTEX CANOpen protocol. This tool automates various test scenarios to ensure the reliability and performance of the BMS.

## Features
- Simulates BMS communication protocol, from the controller
- Configurable parameters for testing time, and for query frequency
- Real-time data monitoring and logging

## Installation
1. You need to install python for windows first: https://www.python.org/downloads/ 
2. You need to install dependencies. Run this from the windows command line: pip install -p requirements.txt
3. BMS tester can now run from the command line.
4. You need a serial-CAN device connecting the BMS to the PC over USB.

## Usage
1. Ensure the BMS is connected to the PC with a serial-CAN USB device. Ensure the BMS is turned on and ready to go.
2. You can start the tester from the windows command line by running: python bms_automated_tester.py
3. Select a unique COM port (ie. not used by something else at the same time) 
4. Select the polling frequency, which is how often the controller would grab values from the BMS. When sending a report to FTEX, the value should be 1000ms.
5. Select the test duration, which is for how long the validation should run. When sending a report to FTEX, the duration should be 10 minutes.
6. Check for any test failure in the output, which indicates a protocol failure on the BMS.

When sharing results with FTEX, the generated log file should be shared. A CAN bus capture as well, if possible.