import serial.tools.list_ports

def list_available_channels():
    ports = serial.tools.list_ports.comports()
    available_channels = [{"device": port.device, "description": port.description, "name": port.name} for port in ports]
    return available_channels

def main():
    available_channels = list_available_channels()
    if available_channels:
        print("Available COM ports:")
        for channel in available_channels:
            print(f"- {channel}")
    else:
        print("No COM ports found.")

if __name__ == "__main__":
    main()