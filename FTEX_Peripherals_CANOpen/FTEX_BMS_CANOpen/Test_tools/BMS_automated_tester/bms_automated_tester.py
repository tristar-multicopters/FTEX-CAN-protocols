import canopen
import canopen.network
import os
import time
from datetime import datetime
from utils.list_channels import list_available_channels

# Configuration variables
BITRATE = 500000  # CAN bitrate
BAUDRATE = 2000000  # CAN baudrate
NODE_ID = 5  # BMS node ID

BMS_DICTIONARY_PATH = "./bms.eds"

# Global variables for CAN interface and network

BMS_ERROR_CODES = [
    {"value": 0, "description": "External_BMS_No_error: No error."},
    {"value": 1, "description": "External_BMS_Overtemperature_Error: The BMS detects that the temperature is above the safe operating range."},
    {"value": 2, "description": "External_BMS_Undertemperature_Error: The BMS detects that the temperature is below the safe operating range."},
    {"value": 4, "description": "External_BMS_Cell_Imbalance_Warning: The BMS detects an imbalance between individual cells in the battery pack."},
    {"value": 8, "description": "External_BMS_Overvoltage_Error: The BMS detects that the voltage exceeds the safe operating range."},
    {"value": 16, "description": "External_BMS_Undervoltage_Error: The BMS detects that the voltage is below the safe operating range."},
    {"value": 32, "description": "External_BMS_Charge_Overcurrent_Error: The BMS detects an overcurrent condition during charging."},
    {"value": 64, "description": "External_BMS_Discharge_Overcurrent_Error: The BMS detects an overcurrent condition during discharge."},
    {"value": 128, "description": "External_BMS_Shortcircuit_Error: The BMS detects a short circuit condition."},
    {"value": 2147483648, "description": "External_BMS_Internal_Error: The BMS detects an unmapped or undefined error."}
]

BMS_STATE = [
    {"value": 0, "description": "Undefined (should not happen)"},
    {"value": 1, "description": "Charging"},
    {"value": 2, "description": "Discharging"},
    {"value": 3, "description": "Fully charged"},
    {"value": 4, "description": "Fully discharged"},
    {"value": 5, "description": "Error (in that case, the error state index 0x20 subindex 0x00 must be set to non-zero)"}
]

# Network setup function
def setup_network(channel: str, bitrate: int, baudrate: int) -> canopen.Network:
    """
    Initializes a CANopen network and returns the network object.
    
    Parameters:
        channel (str): The CAN interface channel, e.g., 'COM9'.
        bitrate (int): The bitrate of the CAN bus in bits per second.
        baudrate (int): The baudrate of the CAN bus.

    Returns:
        canopen.Network: The initialized CANopen network.

    Raises:
        Exception: If the network setup fails.
    """
    try:
        print("Initializing CANopen network...")
        # Verify the EDS/DCF file path
        if os.path.isfile(BMS_DICTIONARY_PATH):
            print(f"Verified: EDS file found at '{BMS_DICTIONARY_PATH}'")
        else:
            print(f"Error: EDS file not found at '{BMS_DICTIONARY_PATH}'")
            raise FileNotFoundError(f"EDS file not found: {BMS_DICTIONARY_PATH}")
        # Create a new CANopen Network
        network = canopen.Network()
        
        # Connect the network
        network.connect(channel=channel, 
                        interface='seeedstudio', 
                        bitrate=bitrate, 
                        baudrate=baudrate)
        
        # Add a CANopen node to the network
        node = canopen.RemoteNode(NODE_ID, BMS_DICTIONARY_PATH)
        network.add_node(node)
        
        print(network)
        print("Network connected and node added.")
        return network

    except Exception as e:
        # Log the error and re-raise it
        print(f"Error initializing CANopen network: {e}")
        raise

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

def logger(message, log_file):
    # Get the current time with milliseconds
    current_time = datetime.now()

    # Format time to include milliseconds
    formatted_time = current_time.strftime('%H:%M:%S') + f":{current_time.microsecond // 1000:03d}"

    message = formatted_time + ": " + message
    with open(log_file, "a") as file:
            file.write(f"{message}\n")
    
    if "fail" in message.lower():
        print(f"\033[31m{message}\033[0m")
    elif "warning" in message.lower():
        print(f"\033[33m{message}\033[0m") 
    else:
        print(message)

def perform_test(node, log_file_name):
    def read_value(node, index, subindex):
        """Helper function to safely get an SDO value."""
        try:
            value = node.sdo[index][subindex].raw
            return value
        except KeyError as e:
            logger(f"Parameter {subindex} not found: {e}", log_file_name)
            return None
        except Exception as e:
            logger(f"Error reading parameter {subindex}: {e}", log_file_name)
            return None

    logger(f"Test made at {time.strftime('%H:%M:%S')}", log_file_name)
    result = True 
    
    # Reading error state
    logger("Reading BMS error state", log_file_name)
    error_state = read_value(node, "CO_ID_EXTERNAL_BMS_ERROR_STATE", "CO_PARAM_EXTERNAL_BMS_ERROR_STATE")
    if error_state is not None:
        found = False
        if error_state == 0:
            logger("No error state", log_file_name)
            found = True
        else:
            for error in BMS_ERROR_CODES:
                if error_state & error["value"]:
                    found = True
                    result = False
                    logger(f"Warning Error Code={error['value']}, {error['description']}", log_file_name)
        if not found:
            result = False
            logger(f"TEST FAIL: BMS error state UNKNOWN: {error_state}", log_file_name)
    else:
        result = False
    
    
    # Reading BMS temperature
    logger("Reading BMS temperature", log_file_name)
    temperature = read_value(node, "CO_ID_EXTERNAL_BMS_ERROR_STATE", "CO_PARAM_EXTERNAL_BMS_TEMPERATURE")
    if temperature is not None:
        if temperature < -50 or temperature > 250:
            result = False
            logger(f"TEST FAIL: BMS temperature out of range. Value: {temperature}", log_file_name)
        else:
            logger(f"BMS temperature={temperature}", log_file_name)
    else:
        result = False
    
    # Reading BMS State of Charge (SOC)
    logger("Reading BMS SOC", log_file_name)
    soc = read_value(node, "CO_ID_EXTERNAL_BMS_REALTIME_INFO", "CO_PARAM_EXTERNAL_BMS_SOC")
    if soc is not None:
        if soc < 0 or soc > 100:
            result = False
            logger(f"TEST FAIL: BMS SOC out of range={soc}", log_file_name)
        else:
            logger(f"BMS SOC={soc}", log_file_name)
    else:
        result = False

    # Reading BMS current
    logger("Reading BMS current", log_file_name)
    current = read_value(node, "CO_ID_EXTERNAL_BMS_REALTIME_INFO", "CO_PARAM_EXTERNAL_BMS_CURRENT")
    if current is not None:
        if current < -100000 or current > 100000:
            result = False
            logger(f"TEST FAIL: BMS current out of range. Value: {current}", log_file_name)
        else:
            logger(f"BMS current={current}", log_file_name)
    else:
        result = False

    # Reading BMS state
    logger("Reading BMS state", log_file_name)
    bms_state = read_value(node, "CO_ID_EXTERNAL_BMS_REALTIME_INFO", "CO_PARAM_EXTERNAL_BMS_STATE")
    found = False
    if bms_state is not None:
        for state in BMS_STATE:
            if state["value"] == bms_state:
                found = True
                logger(f"State = {bms_state}, {state['description']}", log_file_name)
                break
        if not found:
            result = False
            logger(f"TEST FAIL: BMS state not found. State: {bms_state}", log_file_name)
    else:
        result = False

    # Reading BMS serial number (MSB)
    logger("Reading BMS serial number MSB", log_file_name)
    serial_number_msb = read_value(node, "CO_ID_EXTERNAL_BMS_SERIAL_NUMBER", "CO_PARAM_EXTERNAL_BMS_SERIAL_NUMBER_MSB")
    if serial_number_msb is not None:
        logger(f"BMS serial number MSB={serial_number_msb}", log_file_name)
    else:
        result = False
        logger(f"TEST FAIL: Serial number MSB is missing", log_file_name)

    # Reading BMS serial number (LSB)
    logger("Reading BMS serial number LSB", log_file_name)
    serial_number_lsb = read_value(node, "CO_ID_EXTERNAL_BMS_SERIAL_NUMBER", "CO_PARAM_EXTERNAL_BMS_SERIAL_NUMBER_LSB")
    if serial_number_lsb is not None:
        logger(f"BMS serial number LSB={serial_number_lsb}", log_file_name)
    else:
        result = False
        logger(f"TEST FAIL: Serial number LSB is missing", log_file_name)

    # Reading BMS cycle count
    logger("Reading BMS cycle count", log_file_name)
    cycle_count = read_value(node, "CO_ID_EXTERNAL_BMS_SERIAL_NUMBER", "CO_PARAM_EXTERNAL_BMS_CYCLE_COUNT")
    if cycle_count is not None:
        logger(f"BMS cycle count={cycle_count}", log_file_name)
    else:
        result = False
        logger(f"TEST FAIL: BMS cycle count is missing", log_file_name)

    # Reading BMS model number
    logger("Reading BMS model number", log_file_name)
    model_number = read_value(node, "CO_ID_EXTERNAL_BMS_SERIAL_NUMBER", "CO_PARAM_EXTERNAL_BMS_MODEL_NUMBER")
    if model_number is not None:
        logger(f"BMS model number={model_number}", log_file_name)
    else:
        result = False
        logger(f"TEST FAIL: BMS model number is missing", log_file_name)

    # Reading BMS firmware version
    logger("Reading BMS firmware version", log_file_name)
    firmware_version = read_value(node, "CO_ID_EXTERNAL_BMS_SERIAL_NUMBER", "CO_PARAM_EXTERNAL_BMS_FW_VERSION")
    if firmware_version is not None:
        logger(f"BMS firmware version={firmware_version}", log_file_name)
    else:
        result = False
        logger(f"TEST FAIL: BMS firmware version is missing", log_file_name)

    # Reading BMS maximum charge current
    logger("Reading BMS maximum charge current", log_file_name)
    max_charge_current = read_value(node, "CO_ID_EXTERNAL_BMS_DISCHARGE_CURRENT", "CO_PARAM_EXTERNAL_BMS_MAX_CHARGE_CURRENT")
    if max_charge_current is not None:
        if max_charge_current < 1 or max_charge_current > 100000:
            result = False
            logger(f"TEST FAIL: BMS max charge current out of range. Value: {max_charge_current}", log_file_name)
        else:
            logger(f"BMS max charge current={max_charge_current}", log_file_name)
    else:
        result = False
    

    # Reading BMS max discharge time
    logger("Reading BMS max discharge time", log_file_name)
    max_discharge_time = read_value(node, "CO_ID_EXTERNAL_BMS_DISCHARGE_CURRENT", "CO_PARAM_EXTERNAL_BMS_MAX_DISCHARGE_TIME")
    if max_discharge_time is not None:
        if max_discharge_time < 1 or max_discharge_time > 300000:
            result = False
            logger(f"TEST FAIL: BMS max discharge time out of range. Value: {max_discharge_time}", log_file_name)
        else:
            logger(f"BMS max discharge time={max_discharge_time}", log_file_name)
    else:
        result = False

    # Reading BMS continuous current
    logger("Reading BMS continuous current", log_file_name)
    continuous_current = read_value(node, "CO_ID_EXTERNAL_BMS_DISCHARGE_CURRENT", "CO_PARAM_EXTERNAL_BMS_CONTINUOUS_CURRENT")
    if continuous_current is not None:
        if continuous_current < 1 or continuous_current > 100000:
            logger(f"TEST FAIL: BMS continuous current out of range. Value: {continuous_current}", log_file_name)
            result = False
        else:
            logger(f"BMS continuous current={continuous_current}", log_file_name)
    else:
        result = False

    # Reading BMS maximum discharge current
    logger("Reading BMS maximum discharge current", log_file_name)
    max_discharge_current = read_value(node, "CO_ID_EXTERNAL_BMS_DISCHARGE_CURRENT", "CO_PARAM_EXTERNAL_BMS_MAX_DISCHARGE_CURRENT")
    if max_discharge_current is not None:
        if max_discharge_current < 1 or max_discharge_current > 100000:
            result = False
            logger(f"TEST FAIL: BMS max discharge current out of range. Value: {max_discharge_current}", log_file_name)
        else:
            logger(f"BMS max discharge current={max_discharge_current}", log_file_name)
            if(max_discharge_current < continuous_current):
                result = False
                logger(f"TEST FAIL: BMS max discharge current ({max_discharge_current}) must be greather or equal to BMS continuous current ({continuous_current})", log_file_name)
    else:
        result = False

    

    # Reading BMS empty voltage
    logger("Reading BMS empty voltage", log_file_name)
    empty_voltage = read_value(node, "CO_ID_EXTERNAL_BMS_DISCHARGE_CURRENT", "CO_PARAM_EXTERNAL_BMS_EMPTY_VOLTAGE")
    if empty_voltage is not None:
        if empty_voltage < 2000 or empty_voltage > 10000:
            result = False
            logger(f"TEST FAIL: BMS empty voltage out of range. Value: {empty_voltage}", log_file_name)
        else:
            logger(f"BMS empty voltage={empty_voltage}", log_file_name)
    else:
        result = False

    # Reading BMS full voltage
    logger("Reading BMS full voltage", log_file_name)
    full_voltage = read_value(node, "CO_ID_EXTERNAL_BMS_DISCHARGE_CURRENT", "CO_PARAM_EXTERNAL_BMS_FULL_VOLTAGE")
    if full_voltage is not None:
        if full_voltage < 2000 or full_voltage > 10000:
            result = False
            logger(f"TEST FAIL: BMS full voltage out of range. Value: {full_voltage}", log_file_name)
        else:
            logger(f"BMS full voltage={full_voltage}", log_file_name)
            if(full_voltage <= empty_voltage):
                result = False
                logger(f"TEST FAIL: BMS full voltage ({full_voltage}) must be greather than BMS empty voltage ({empty_voltage})", log_file_name)
    else:
        result = False


    # Reading BMS undervoltage limit
    logger("Reading BMS undervoltage limit", log_file_name)
    undervoltage_limit = read_value(node, "CO_ID_EXTERNAL_BMS_DISCHARGE_CURRENT", "CO_PARAM_EXTERNAL_BMS_UNDERVOLTAGE_LIMIT")
    if undervoltage_limit is not None:
        if undervoltage_limit < 2000 or undervoltage_limit > 10000:
            result = False
            logger(f"TEST FAIL: BMS undervoltage limit out of range. Value: {undervoltage_limit}", log_file_name)
        else:
            logger(f"BMS undervoltage limit={undervoltage_limit}", log_file_name)
            if(undervoltage_limit>=empty_voltage):
                result = False
                logger(f"TEST FAIL: BMS under voltage limit ({undervoltage_limit}) must be smaller than BMS empty voltage ({empty_voltage})", log_file_name)
    else:
        result = False

    # Reading BMS voltage
    logger("Reading BMS voltage", log_file_name)
    voltage = read_value(node, "CO_ID_EXTERNAL_BMS_REALTIME_INFO", "CO_PARAM_EXTERNAL_BMS_VOLTAGE")
    if voltage is not None:
        if voltage < 2000 or voltage > 10000:
            result = False
            logger(f"TEST FAIL: BMS voltage out of range={voltage}", log_file_name)
        else:
            logger(f"BMS voltage={voltage}", log_file_name)
            if voltage > full_voltage:
                result = False
                logger(f"TEST FAIL: Bms voltage ({voltage}) must be smaller or equal than Bms full voltage ({full_voltage})", log_file_name)
            if voltage <= undervoltage_limit:
                result = False
                logger(f"TEST FAIL: Bms voltage ({voltage}) must be greater than Bms undervoltage limit ({undervoltage_limit})", log_file_name)
    else:
        result = False
                       

    # Reading BMS overvoltage limit
    logger("Reading BMS overvoltage limit", log_file_name)
    overvoltage_limit = read_value(node, "CO_ID_EXTERNAL_BMS_DISCHARGE_CURRENT", "CO_PARAM_EXTERNAL_BMS_OVERVOLTAGE_LIMIT")
    if overvoltage_limit is not None:
        if overvoltage_limit < 2000 or overvoltage_limit > 10000:
            result = False
            logger(f"TEST FAIL: BMS overvoltage limit out of range. Value: {overvoltage_limit}", log_file_name)
        else:
            logger(f"BMS overvoltage limit={overvoltage_limit}", log_file_name)
            if(overvoltage_limit<=full_voltage):
                result = False
                logger(f"TEST FAIL: BMS overvoltage limit ({overvoltage_limit}) must be greater than BMS full voltage ({full_voltage})", log_file_name)
    else:
        result = False

    # Reading BMS maximum capacity
    logger("Reading BMS maximum capacity", log_file_name)
    max_capacity = read_value(node, "CO_ID_EXTERNAL_BMS_DISCHARGE_CURRENT", "CO_PARAM_EXTERNAL_BMS_MAXIMUM_CAPACITY")
    if max_capacity is not None:
        if max_capacity < 100 or max_capacity > 5000:
            result = False
            logger(f"TEST FAIL: BMS max capacity out of range. Value: {max_capacity}", log_file_name)
        else:
            logger(f"BMS max capacity={max_capacity}", log_file_name)
    else:
        result = False
    
    # Reading BMS remaining capacity
    logger("Reading BMS remaining capacity", log_file_name)
    remaining_capacity = read_value(node, "CO_ID_EXTERNAL_BMS_DISCHARGE_CURRENT", "CO_PARAM_EXTERNAL_BMS_REMAINING_CAPACITY")
    if remaining_capacity is not None:
        if remaining_capacity < 100 or remaining_capacity > 5000:
            result = False
            logger(f"TEST FAIL: BMS remaining capacity {remaining_capacity} is out of range", log_file_name)
        else:
            logger(f"BMS remaining capacity={remaining_capacity}", log_file_name)
            if(remaining_capacity>max_capacity):
                result = False
                logger(f"TEST FAIL: BMS remaining capacity ({remaining_capacity}) must be lower or equal to BMS max capacity ({max_capacity})", log_file_name)
    else:
        result = False

    if result == True:
        logger("All test verifications passed!\n\n", log_file_name)
    else:
        logger("Failed to validate the BMS device.\n\n", log_file_name)


import time

def periodic_runner(frequency_ms, total_time, node, log_file_name):
    """
    Runs a periodic task at a specified interval in milliseconds.

    :param frequency_ms: The frequency in milliseconds between each execution.
    :param total_time: The total runtime in minutes.
    :param node: Node for the perform_test function.
    :param log_file_name: Log file name for the perform_test function.
    """
    frequency = frequency_ms / 1000.0  # Convert milliseconds to seconds
    end_time = time.time() + total_time * 60  # Calculate the end time in seconds

    while time.time() < end_time:
        perform_test(node, log_file_name)  # Replace with your actual task function
        time.sleep(frequency)  # Sleep for the given frequency in seconds



# Generate a filename with the current timestamp
def generate_file_name():
    current_time = datetime.now()
    formatted_time = current_time.strftime("%Y-%m-%d_%H-%M-%S")
    file_name = f"log_{formatted_time}.txt"
    return file_name


def main():
    try:
        # Select COM port channel
        channel = select_channel()
        if not channel:
            print("No valid COM port selected. Exiting.")
            return

        print(f"User selected channel: {channel}")

        # Get user input
        while True:
            try:
                frequency = int(input("Enter the polling frequency (in ms): "))
                if frequency < 100:
                    print("\033[31mFrequency must be at least 100 ms. Please try again.\033[0m")
                    continue
                break
            except ValueError:
                print("\033[31mPlease enter a valid numeric value for frequency.\033[0m")

        while True:
            try:
                total_time = int(input("Enter the total duration (in minutes) to run the test: "))
                break
            except ValueError:
                print("\033[31mPlease enter a valid numeric value for total time.\033[0m")

        # Setup CAN network
        can_network = setup_network(channel, BITRATE, BAUDRATE)
        node = can_network.nodes[NODE_ID]

        if can_network:
            print("CANopen network setup successful.")
        else:
            raise ValueError("Failed to set up CANopen network.")

        # Allow network stabilization
        time.sleep(1)

        # Log and run the periodic test
        log_file_name = generate_file_name()
        logger(f"Starting BMS test every {frequency} milliseconds for a total of {total_time} minutes.", log_file_name)
        periodic_runner(frequency, total_time, node, log_file_name)
        logger("Test completed.\n\n", log_file_name)

    except KeyboardInterrupt:
        print("\n\033[31mTest interrupted by user.\033[0m")
        if 'can_network' in locals() and can_network:
            can_network.disconnect()

    except Exception as e:
        print(type(e), e.args, e)

    finally:
        if 'can_network' in locals() and can_network:
            can_network.disconnect()
            
    
if __name__ == "__main__":
    main()