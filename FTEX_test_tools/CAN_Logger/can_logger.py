import curses
import re
import can
import time
import os
import json
from datetime import datetime
from curses import wrapper
from utils.list_channels import list_available_channels
from collections import deque
from pathlib import Path
import csv

CONFIG_FILE = 'can_config.json'
MAX_MESSAGES = 100  # Maximum number of messages to store in history

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

def create_log_file():
    # Create logs directory if it doesn't exist
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # Create a new log file with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"can_log_{timestamp}.csv"
    
    # Initialize CSV file with headers
    with open(log_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Time', 'ID', 'Data', 'DLC (Data Length Code)'])
    
    return log_file

class CANMonitorUI:
    def __init__(self, stdscr, config):
        self.stdscr = stdscr
        self.config = config
        self.messages = deque(maxlen=MAX_MESSAGES)
        self.running = True
        self.setup_colors()
        self.log_file = create_log_file()
        
    def setup_colors(self):
        curses.start_color()
        curses.init_pair(1, curses.COLOR_GREEN, curses.COLOR_BLACK)  # Headers
        curses.init_pair(2, curses.COLOR_YELLOW, curses.COLOR_BLACK)  # Messages
        curses.init_pair(3, curses.COLOR_RED, curses.COLOR_BLACK)    # Errors
        curses.init_pair(4, curses.COLOR_CYAN, curses.COLOR_BLACK)   # Status

    def draw_header(self):
        header = "=== CAN Bus Monitor ==="
        self.stdscr.addstr(0, 0, "=" * curses.COLS, curses.color_pair(1))
        self.stdscr.addstr(0, (curses.COLS - len(header)) // 2, header, curses.color_pair(1))
        
        # Show current configuration
        config_str = f"Channel: {self.config['channel']} | Bitrate: {self.config['bitrate']} kbps | Baudrate: {self.config['baudrate']} bps"
        self.stdscr.addstr(1, 0, config_str, curses.color_pair(4))
        
        # Column headers
        self.stdscr.addstr(3, 0, "Time          ID      Data", curses.color_pair(1))
        self.stdscr.addstr(4, 0, "-" * curses.COLS, curses.color_pair(1))

    def draw_messages(self):
        start_row = 5
        for i, msg in enumerate(self.messages):
            if start_row + i >= curses.LINES - 1:  # Leave room for status line
                break
            self.stdscr.addstr(start_row + i, 0, msg, curses.color_pair(2))

    def draw_status(self):
        log_name = Path(self.log_file).name
        status = f"Logging to: {log_name} | Press 'q' to quit | 'p' to pause/resume"
        self.stdscr.addstr(curses.LINES - 1, 0, status, curses.color_pair(4))

    def format_can_message(self, msg):
        timestamp = self.format_timestamp_ms(msg.timestamp)
        data = self.format_can_data(msg.data)
        return f"{timestamp}  {msg.arbitration_id:#04x}    {data}"

    @staticmethod
    def format_can_data(data: bytes) -> str:
        return ' '.join(f"{b:02X}" for b in data)

    @staticmethod
    def format_timestamp_ms(timestamp: float) -> str:
        dt = datetime.fromtimestamp(timestamp)
        return dt.strftime('%H:%M:%S.%f')[:-3]

    def run(self):
        try:
            bus = can.interface.Bus(
                interface='seeedstudio',
                channel=self.config['channel'],
                bitrate=self.config['bitrate'] * 1000,
                baudrate=self.config['baudrate'],
                timeout=0.1
            )
            
            paused = False
            while self.running:
                self.stdscr.clear()
                self.draw_header()
                self.draw_messages()
                self.draw_status()
                self.stdscr.refresh()

                # Check for user input (non-blocking)
                self.stdscr.nodelay(1)
                try:
                    key = self.stdscr.getch()
                    if key == ord('q'):
                        self.running = False
                    elif key == ord('p'):
                        paused = not paused
                except curses.error:
                    pass

                if not paused:
                    # Check for CAN messages (non-blocking due to timeout)
                    msg = bus.recv()
                    if msg:
                        formatted_msg = self.format_can_message(msg)
                        self.messages.append(formatted_msg)
                        
                        # Log message to CSV
                        with open(self.log_file, 'a', newline='') as f:
                            writer = csv.writer(f)
                            writer.writerow([
                                self.format_timestamp_ms(msg.timestamp),
                                f"{msg.arbitration_id:#04x}",
                                self.format_can_data(msg.data),
                                len(msg.data)
                            ])

                time.sleep(0.01)  # Small delay to prevent high CPU usage

        except Exception as e:
            self.stdscr.addstr(curses.LINES - 2, 0, f"Error: {str(e)}", curses.color_pair(3))
            self.stdscr.refresh()
            time.sleep(2)
        finally:
            if 'bus' in locals():
                bus.shutdown()

def main():
    # First do the regular config setup
    config = setup_initial_config()
    if not config:
        print("Setup failed. Exiting.")
        return

    if not config['channel']:
        print("No valid COM port selected. Exiting.")
        return

    # Then start the curses interface
    def start_ui(stdscr):
        curses.curs_set(0)  # Hide cursor
        ui = CANMonitorUI(stdscr, config)
        ui.run()

    wrapper(start_ui)

if __name__ == "__main__":
    main()