import re
import can
import time
import os
import json
from datetime import datetime
from utils.list_channels import list_available_channels

# Configuration variables
BITRATE = 500000  # CAN bitrate
BAUDRATE = 2000000  # CAN baudrate

def setup_bus(channel: str, bitrate: int, baudrate: int) -> can.Bus:
    try:
        print("Initializing CAN Bus...")
        
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

def select_channel():
    available_channels = list_available_channels()
    if available_channels:
        print("Available COM ports:")
        for i, channel in enumerate(available_channels, start=1):
            print(f"{i}: {channel['device']} - {channel['description']}")
    else:
        print("No COM ports found.")
        return None

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
        channel = select_channel()
        if not channel:
            print("No valid COM port selected. Exiting.")
            return

        print(f"User selected channel: {channel}")

        canBus = setup_bus(channel, BITRATE, BAUDRATE)
        time.sleep(1)
        
        listen_CAN_bus(canBus)
    except Exception as e:
        print(type(e), e.args, e)

if __name__ == "__main__":
    main()