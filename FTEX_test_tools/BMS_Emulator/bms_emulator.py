import re
import can
import time
import os
import json
from utils.list_channels import list_available_channels
# Configuration variables
BITRATE = 500000  # CAN bitrate
BAUDRATE = 2000000  # CAN baudrate
NODE_ID = 5  # BMS node ID
SEND_INTERVAL = 100  # Time in seconds between messages
# Path to the EDS file
EDS_BMS_PATH = "bms.eds"  

BMS_JSON_VALUES_PATH = "bms_values.json"

# Simulated parameter values
bms_values_dict = {}

# Network setup function
def setup_bus(channel: str, bitrate: int, baudrate: int) -> can.Bus:
  
    try:
        print("Initializing CAN Bus...")
        # Verify the EDS/DCF file path
       
        # Create a new CANopen Network
        can_bus = can.interface.Bus(
        interface='seeedstudio',
        channel=channel,
        bitrate=bitrate,
        baudrate=baudrate,
        timeout=0.1,
        operation_mode='normal'
        )
        return can_bus

    except Exception as e:
        # Log the error and re-raise it
        print(f"Error initializing CAN network: {e}")
        raise

def parse_eds_to_dic(eds_file_path): 
    if os.path.isfile(eds_file_path):
        print(f"EDS file converted to dictionary")
    else:
        print(f"Error: EDS file not found at '{eds_file_path}'")
        raise FileNotFoundError(f"EDS file not found: {eds_file_path}")

    object_dict = {}
    current_object = None
    current_subindex = None
    
    # These sections are to be ignored in the parsing process
    ignored_sections = ['FileInfo', 'DeviceInfo', 'Communication']
    in_ignored_section = False

    with open(eds_file_path, 'r') as eds_file:
        for line in eds_file:
            line = line.strip()

            # Remove comments after the semicolon
            line = re.sub(r"\s*;.*$", "", line)

            # Skip empty lines and comments (after cleaning)
            if not line:
                continue

            # Check if the line is a section header
            section_match = re.match(r"\[(\w+)\]", line)
            if section_match:
                section_name = section_match.group(1)

                # Check if the section is in the ignored list
                if section_name in ignored_sections:
                    in_ignored_section = True
                else:
                    in_ignored_section = False

            # Skip lines if we are in an ignored section
            if in_ignored_section:
                continue

            # Match object headers like [20], [30], etc.
            object_match = re.match(r"\[(\d+)(sub(\d+))?\]", line)
            if object_match:
                index = int(object_match.group(1), 16)  # Main index
                subindex = object_match.group(3)
                if subindex is not None:
                    # Subindex case
                    current_subindex = int(subindex)
                else:
                    # New main object
                    current_object = index
                    current_subindex = None
                    object_dict[current_object] = {"subindices": {}}
                continue

            # Match parameter definitions (e.g., ParameterName=...)
            param_match = re.match(r"(\w+)=(.+)", line)
            if param_match:
                key, value = param_match.groups()
                key = key.strip()
                value = value.strip()

                # If in a subindex, add to the subindices dictionary
                if current_subindex is not None:
                    object_dict[current_object]["subindices"][current_subindex] = object_dict[current_object]["subindices"].get(current_subindex, {})
                    object_dict[current_object]["subindices"][current_subindex][key] = value
                else:
                    # Add to the main object
                    object_dict[current_object][key] = value
    
    return object_dict

def parse_sdo_request(bus, msg, target_node_id, object_dict, bms_values_dict):

    # Check if the message is an SDO request (0x600 - 0x67F range)
    if (msg.arbitration_id & 0x780) == 0x600:
        node_id = msg.arbitration_id & 0x7F  # Extract Node ID

        # Filter messages for the specified node_id
        if node_id != target_node_id:
            return  # Ignore messages from other nodes

        command_byte = msg.data[0]
        index = int.from_bytes(msg.data[1:3], byteorder="little")  # Index (2 bytes)
        subindex = msg.data[3]  # Subindex (1 byte)

        # Process the request based on the command
        # BMS is read-only
        if command_byte == 0x40:  # SDO Read Request
            print(f"SDO Read Request for Index {hex(index)}, Subindex {hex(subindex)}")
            # Get parameter name from object dictionary
            parameter_name = get_parameter_name(object_dict, index, subindex)

            if parameter_name:
                # Get parameter value from parameter_values
                print(f"Requested: {parameter_name}")
                parameter_value = get_parameter_value(bms_values_dict, parameter_name)
                send_sdo_response(bus, target_node_id, index, subindex, parameter_value, object_dict)

            else:
                print("Parameter not found in the object dictionary.")
                send_sdo_error_response(bus, target_node_id, index, subindex, 0x05)  # Error: Parameter not found

        elif command_byte in {0x23, 0x2F}:  # SDO Write Request
            # 0x23: Expedited Write Request with 4 bytes
            # 0x2F: Expedited Write Request with 1 byte
            print(f"SDO Write Request for Index {hex(index)}, Subindex {hex(subindex)}")
            data = msg.data[4:]  # Extract the write data
            print(f"Write Data: {data.hex()}")

            # Add logic for handling SDO write requests here
            # For now, we will just acknowledge the write with a response
            # Todo: send_sdo_write_acknowledgment(bus, target_node_id, index, subindex)

        else:
            print(f"Unknown SDO Command: {hex(command_byte)}")
            send_sdo_error_response(bus, target_node_id, index, subindex, 0x02)  # Error: Unknown command

def send_sdo_error_response(bus, target_node_id, index, subindex, error_code):

    # Format the error response as per the CANopen SDO protocol (error response starts with 0x80)
    # Ensure the response is 8 bytes by padding with zeros if necessary
    response_data = [
        0x80,  # Error command byte (indicates error response)
        *index.to_bytes(2, byteorder="little"),  # Index (2 bytes)
        subindex,  # Subindex (1 byte)
        error_code,  # Error code (1 byte)
        0,  # Padding byte (to make the message 8 bytes)
        0,  # Padding byte (to make the message 8 bytes)
        0  # Padding byte (to make the message 8 bytes)
    ]
    response_msg = can.Message(arbitration_id=(target_node_id | 0x600), data=response_data, is_extended_id=False)
    bus.send(response_msg)
    print(f"Sent SDO Error Response to Node {target_node_id}: Error Code {hex(error_code)}")

def send_sdo_write_acknowledgment(bus, target_node_id, index, subindex):
    # Format the acknowledgment response as per the CANopen SDO protocol (write acknowledgment)
    # Ensure the response is 8 bytes by padding with zeros if necessary
    response_data = [
        0x60,  # Write acknowledgment command byte
        *index.to_bytes(2, byteorder="little"),  # Index (2 bytes)
        subindex,  # Subindex (1 byte)
        0,  # Padding byte (to make the message 8 bytes)
        0,  # Padding byte (to make the message 8 bytes)
        0,  # Padding byte (to make the message 8 bytes)
        0  # Padding byte (to make the message 8 bytes)
    ]
    response_msg = can.Message(arbitration_id=(target_node_id | 0x600), data=response_data, is_extended_id=False)
    bus.send(response_msg)
    print(f"Sent SDO Write Acknowledgment to Node {target_node_id} for Index {hex(index)}, Subindex {hex(subindex)}")

def listen_and_respond_to_sdo(bus, node_id, object_dict, bms_values_dict):
    try:
        print("Listening to BMS CAN messages. Press Ctrl+C to stop.")
        for msg in bus:  # Continuously listen for messages
            parse_sdo_request(bus, msg, node_id, object_dict, bms_values_dict)

    except KeyboardInterrupt:
        print("\nListener stopped by user.")
    finally:
        bus.shutdown()  # Cleanup resources when done

def get_parameter_name(object_dictionary, index, subindex):
      # Lookup index in the object dictionary
    if index in object_dictionary:
        subindices = object_dictionary[index].get('subindices', {})
        if subindex in subindices:
            return subindices[subindex].get('ParameterName')
    return None

def get_parameter_value(parameter_values, parameter_name):
    if not isinstance(parameter_values, dict):
        raise TypeError(f"Expected 'parameter_values' to be a dict, got {type(parameter_values).__name__}")
    return parameter_values.get(parameter_name)

import struct

def send_sdo_response(bus, node_id, index, subindex, data, object_dictionary):
    response_id = 0x580 + node_id
    
    # Get the data type for the parameter from the object dictionary
    data_type_str = object_dictionary.get(index, {}).get('subindices', {}).get(subindex, {}).get('DataType')

    if data_type_str is None:
        print(f"Error: DataType not found for index {index} and subindex {subindex}")
        return
    
    data_type = int(data_type_str, 16)
    
    # Define a mapping for the data type to command byte and data size
    data_type_mapping = {
        0x0003: (0x4B, 2),  # Signed16 (Int16)
        0x0004: (0x43, 4),  # Signed32 (Int32)
        0x0005: (0x4F, 1),  # Unsigned8 (8 bits)
        0x0006: (0x4B, 2),  # Unsigned16 (16 bits)
        0x0007: (0x43, 4),  # Unsigned32 (32 bits)
    }

    # Check if the data type is valid and get the command byte and data size
    if data_type not in data_type_mapping:
        print(f"Error: Unsupported data type {data_type} for parameter.")
        return
    
    command_byte, data_size = data_type_mapping[data_type]
    
    # Initialize response_data with 8 bytes, since the total response is 8 bytes
    response_data = bytearray(8)  # 8 bytes for the response
    
    # Set up the response data bytes
    response_data[0] = command_byte  # Command byte (0x4F, 0x4B, 0x47, 0x43, 0x45)
    response_data[1:3] = index.to_bytes(2, byteorder='little')  # Index
    response_data[3] = subindex  # Subindex
    
    # Pack the data based on its type
    if data_type == 0x0005:  # Unsigned8 (8 bits)
        response_data[4] = data & 0xFF
    elif data_type == 0x0006:  # Unsigned16 (16 bits)
        response_data[4:6] = data.to_bytes(2, byteorder='little')
    elif data_type == 0x0007:  # Unsigned32 (32 bits)
        response_data[4:8] = data.to_bytes(4, byteorder='little')
    elif data_type == 0x0003:  # Signed16 (Int16)
        response_data[4:6] = data.to_bytes(2, byteorder='little', signed=True)
    elif data_type == 0x0004:  # Signed32 (Int32)
        response_data[4:8] = data.to_bytes(4, byteorder='little', signed=True)
    
    # Send the message
    msg = can.Message(arbitration_id=response_id, data=response_data, is_extended_id=False)
    bus.send(msg)
    print(f"Sent SDO Response: {msg}\nValue = {data}\n")
    print("Listening to BMS CAN messages. Press Ctrl+C to stop.")



def select_channel():
    # List available channels
    available_channels = list_available_channels()
    if available_channels:
        print("Available COM ports:")
        for i, channel in enumerate(available_channels, start=1):
            print(f"{i}: {channel['device']} - {channel['description']}")
    else:
        print("No COM ports found.")
        return None

    # Prompt the user to choose a channel
    while True:
        try:
            choice = int(input("Enter the number of the COM port you want to use: "))
            if 1 <= choice <= len(available_channels):
                return available_channels[choice - 1]['device']
            else:
                print("Invalid choice. Please choose a valid number.")
        except ValueError:
            print("Invalid input. Please enter a number.")


def main():
    try:

        # Check if the file exists
        if os.path.exists(BMS_JSON_VALUES_PATH):
        # Load the JSON file
            with open(BMS_JSON_VALUES_PATH, "r") as file:
                bms_values_dict = json.load(file)
        else:
            print(f"Error: The file {BMS_JSON_VALUES_PATH} does not exist.")
            return

        #Select COM port channel
        channel = select_channel()
        if not channel:
            print("No valid COM port selected. Exiting.")
            return

        print(f"User selected channel: {channel}")

        # Parse the EDS file to get the object dictionary
        object_dict = parse_eds_to_dic(EDS_BMS_PATH)
        # print(object_dict)
        usb_to_can = setup_bus(channel, BITRATE, BAUDRATE)
        time.sleep(1)
        
        listen_and_respond_to_sdo(usb_to_can, NODE_ID, object_dict, bms_values_dict)
    except Exception as e:
        print(type(e), e.args, e)
            

    
if __name__ == "__main__":
    main()