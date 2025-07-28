# CleverCoffee OTA Flasher

A simple GUI application for uploading the CleverCoffee firmware to ESP32 microcontrollers using Over-The-Air (OTA) updates.

## Features

- GUI wrapper for espota.py built with Tkinter
- File browser for selecting firmware binaries
- Real-time upload progress and logging
- Support for password-protected OTA updates
- Cross-platform compatibility

## Requirements

- Python 3.6 or higher
- espota.py (included)
- ESP32 DevKitC v4 running CleverCoffee 4.0.X

__Note__: If you're running macOS and have installed python via homebrew there is no out-of-the-box support for Tkinter.
You can either use the system python executable or install the package python-tk.

## Usage

1. Run the application:
   ```bash
   python clevercoffee_ota_flasher.py
   ```

2. Select your firmware.bin and/or littlefs.bin
3. Enter your ESP32's IP address or hostname that you can reach on your LAN
4. Set port (default: 3232) and password (default in the firmware: "otapass")
5. Click "Start Upload"

