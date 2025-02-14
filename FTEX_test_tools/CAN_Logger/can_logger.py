import re
import can
import time
import os
import json
from datetime import datetime
from utils.list_channels import list_available_channels

CONFIG_FILE = 'can_config.json'

def load_config():
    default_config = {
        "channel": "",
        "bitrate": 500,  # in kbps
        "baudrate": 2000000,  # in bps
        "common_bitrates": [125, 250, 500, 1000],  # in kbps
        "common_baudrates": [115200, 921600, 2000000]  # in bps
    }
    
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except:
            return default_config
    return default_config

def save_config(config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)

def setup_initial_config():
    config = load_config()
    
    print("\n=== CAN Monitor Setup ===")
    print("\nCurrent configuration:")
    print(f"Channel: {config['channel']}")
    print(f"Bitrate: {config['bitrate']} kbps")
    print(f"Baudrate: {config['baudrate']} bps")
    
    edit = input("\nDo you want to edit the configuration? (y/n): ").lower()
    if edit == 'y':
        # Channel selection
        available_channels = list_available_channels()
        if available_channels:
            print("\nAvailable COM ports:")
            for i, channel in enumerate(available_channels, start=1):
                print(f"{i}: {channel['device']} - {channel['description']}")
            
            while True:
                try:
                    choice = int(input("Select COM port (number): "))
                    if 1 <= choice <= len(available_channels):
                        config['channel'] = available_channels[choice - 1]['device']
                        break
                    print("Invalid choice. Please try again.")
                except ValueError:
                    print("Please enter a number.")
        else:
            print("No COM ports found!")
            return None

        # Bitrate selection
        print("\nCommon bitrates:")
        for i, rate in enumerate(config['common_bitrates'], 1):
            print(f"{i}: {rate} kbps")
        print(f"{len(config['common_bitrates'])+1}: Custom")

        while True:
            try:
                choice = int(input("Select bitrate (number): "))
                if 1 <= choice <= len(config['common_bitrates']):
                    config['bitrate'] = config['common_bitrates'][choice-1]
                    break
                elif choice == len(config['common_bitrates'])+1:
                    custom_rate = int(input("Enter custom bitrate (kbps): "))
                    config['bitrate'] = custom_rate
                    break
                print("Invalid choice. Please try again.")
            except ValueError:
                print("Please enter a number.")

        # Baudrate selection
        print("\nCommon baudrates:")
        for i, rate in enumerate(config['common_baudrates'], 1):
            print(f"{i}: {rate} bps")
        print(f"{len(config['common_baudrates'])+1}: Custom")

        while True:
            try:
                choice = int(input("Select baudrate (number): "))
                if 1 <= choice <= len(config['common_baudrates']):
                    config['baudrate'] = config['common_baudrates'][choice-1]
                    break
                elif choice == len(config['common_baudrates'])+1:
                    custom_rate = int(input("Enter custom baudrate (bps): "))
                    config['baudrate'] = custom_rate
                    break
                print("Invalid choice. Please try again.")
            except ValueError:
                print("Please enter a number.")

        save_config(config)
        print("\nConfiguration saved!")
    
    return config

def setup_bus(channel: str, bitrate: int, baudrate: int) -> can.Bus:
    try:
        print("Initializing CAN Bus...")
        
        can_bus = can.interface.Bus(
            interface='seeedstudio',
            channel=channel,
            bitrate=bitrate * 1000,  # Convert kbps to bps
            baudrate=baudrate,
            timeout=0.1,
            operation_mode='normal'
        )
        return can_bus
    except Exception as e:
        print(f"Error initializing CAN network: {e}")
        raise

def format_can_data(data: bytes) -> str:
    """Format CAN data bytes with spaces between each byte."""
    return ' '.join(f"{b:02X}" for b in data)

def format_timestamp_ms(timestamp: float) -> str:
    """Convert Unix timestamp to readable time with milliseconds."""
    dt = datetime.fromtimestamp(timestamp)
    return dt.strftime('%H:%M:%S.%f')[:-3]  # Show only milliseconds, not microseconds

def listen_CAN_bus(bus):
    try:
        print("Listening to CAN messages. Press Ctrl+C to stop.")
        print("Time          ID      Data")
        print("-" * 50)
        for msg in bus:  # Continuously listen for messages
            timestamp = format_timestamp_ms(msg.timestamp)
            data = format_can_data(msg.data)
            print(f"{timestamp}  {msg.arbitration_id:#04x}    {data}")
    except KeyboardInterrupt:
        print("\nListener stopped by user.")
    finally:
        bus.shutdown()

def main():
    try:
        # Load or create configuration
        config = setup_initial_config()
        if not config:
            print("Setup failed. Exiting.")
            return

        if not config['channel']:
            print("No valid COM port selected. Exiting.")
            return

        print(f"Using configuration:")
        print(f"Channel: {config['channel']}")
        print(f"Bitrate: {config['bitrate']} kbps")
        print(f"Baudrate: {config['baudrate']} bps")

        canBus = setup_bus(config['channel'], config['bitrate'], config['baudrate'])
        time.sleep(1)
        
        listen_CAN_bus(canBus)
    except Exception as e:
        print(type(e), e.args, e)

if __name__ == "__main__":
    main()