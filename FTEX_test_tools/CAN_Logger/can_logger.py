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
STATIC_LINES_IN_TERMINAL = 7  # Maximum number of messages to store in history

def load_config():
    default_config = {
        "channel": "",
        "bitrate": 500,  # in kbps
        "baudrate": 2000000,  # in bps
        "common_bitrates": [125, 250, 500, 1000],  # in kbps
        "common_baudrates": [115200, 921600, 2000000],  # in bps
        "can_id_filter": "",
        "obj_dir_filter": ""
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
    print(f"CANOpen ID Filter: {[hex(id_) for id_ in config['can_id_filter']]}")
    print(f"Object Directory Address Filter: {[hex(addr) for addr in config['obj_dir_filter']]}")


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

        can_id_filter = input("\nEnter CANOpen ID filter(s) (comma-separated, leave empty for all messages): ")
        config['can_id_filter'] = [int(x.strip(), 16) for x in can_id_filter.split(',') if x.strip()] if can_id_filter else []

        obj_dir_filter = input("Enter Object Directory Address filter(s) (comma-separated, leave empty for all messages): ")
        config['obj_dir_filter'] = [int(x.strip(), 16) for x in obj_dir_filter.split(',') if x.strip()] if obj_dir_filter else []


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
        writer.writerow(['Time', 'ID', 'Data', 'DLC'])
    
    return log_file

class CANMonitorUI:
    def __init__(self, stdscr, config):
        self.stdscr = stdscr
        self.config = config
        self.max_display_messages = curses.LINES - STATIC_LINES_IN_TERMINAL  # Leave space for headers and footer
        self.messages = deque(maxlen=max(STATIC_LINES_IN_TERMINAL, self.max_display_messages))  # Ensure at least 10 messages
        self.running = True
        self.setup_colors()
        self.log_file = create_log_file()
        # Statistics
        self.msg_count = 0
        self.start_time = time.time()
        self.last_msg_time = None
        self.max_gap = 0
        self.min_gap = float('inf')  # Initialize min_gap to infinity
        self.msg_per_id = {}
        
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
        
        # Show statistics
        runtime = time.time() - self.start_time
        msg_rate = self.msg_count / runtime if runtime > 0 else 0
        stats = f"Messages: {self.msg_count} | Rate: {msg_rate:.1f} msg/s | Gap min/max: {self.min_gap*1000:.1f}/{self.max_gap*1000:.1f}ms"
        self.stdscr.addstr(2, 0, stats, curses.color_pair(4))
        
        # Show top IDs
        if self.msg_per_id:
            top_ids = sorted(self.msg_per_id.items(), key=lambda x: x[1], reverse=True)[:3]
            top_ids_str = "Top IDs: " + " | ".join(f"{id_}: {count}" for id_, count in top_ids)
            self.stdscr.addstr(3, 0, top_ids_str, curses.color_pair(4))
        
        # Column headers
        self.stdscr.addstr(4, 0, "Time          ID      Data", curses.color_pair(1))
        self.stdscr.addstr(5, 0, "-" * curses.COLS, curses.color_pair(1))

    def draw_messages(self):
        start_row = 6
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
                         # Apply filters
                        can_id_filter = self.config['can_id_filter']
                        obj_dir_filter = self.config['obj_dir_filter']
                        msg_id = msg.arbitration_id
                        if can_id_filter:
                            if can_id_filter and msg_id not in can_id_filter:
                                continue
                        
                        if obj_dir_filter:
                            obj_dir = int.from_bytes(msg.data[1:4], byteorder='little') if len(msg.data) > 3 else None
                            if obj_dir is None or obj_dir not in obj_dir_filter:
                                continue
                        
                        # Update statistics
                        self.msg_count += 1
                        current_time = time.time()
                        
                        # Update message gap tracking
                        if self.last_msg_time is not None:
                            gap = current_time - self.last_msg_time
                            if gap > self.max_gap:
                                self.max_gap = gap
                            if gap < self.min_gap:
                                self.min_gap = gap
                        self.last_msg_time = current_time
                        
                        # Update ID counting
                        msg_id = f"{msg.arbitration_id:#04x}"
                        self.msg_per_id[msg_id] = self.msg_per_id.get(msg_id, 0) + 1
                        
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