import re
import can
import time
import os
import json
from utils.list_channels import list_available_channels

# Configuration variables
BITRATE = 500000  # CAN bitrate
BAUDRATE = 2000000  # CAN baudrate

# Network setup function
def setup_bus(channel: str, bitrate: int, baudrate: int) -> can.Bus:
    try:
        print("Initializing CAN Bus...")
        
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
        print(f"Error initializing CAN network: {e}")
        raise


def listen_CAN_bus(bus):
    try:
        print("Listening to CAN messages. Press Ctrl+C to stop.")
        for msg in bus:  # Continuously listen for messages
            print(f"Timestamp: {msg.timestamp:.6f}, ID: {msg.arbitration_id:#04x}, Data: {msg.data.hex()}")
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
