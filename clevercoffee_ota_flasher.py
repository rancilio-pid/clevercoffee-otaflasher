import datetime
import os
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext


def get_espota_path() -> str:
    if hasattr(sys, '_MEIPASS'):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))

    return os.path.join(base_path, 'espota.py')

class CleverCoffeeOtaFlasher:
    def __init__(self, root):
        self.firmware_check = None
        self.firmware_entry = None
        self.firmware_browse_btn = None
        self.filesystem_check = None
        self.filesystem_entry = None
        self.filesystem_browse_btn = None
        self.progress = None
        self.upload_button = None
        self.cancel_button = None
        self.log_text = None
        self.root = root
        self.root.title("CleverCoffee OTA Flasher")
        self.root.geometry("700x600")
        self.root.resizable(True, True)

        # Variables for storing user inputs
        self.firmware_path = tk.StringVar()
        self.filesystem_path = tk.StringVar()
        self.esp_ip = tk.StringVar(value="192.168.1.100")   # Default IP
        self.esp_port = tk.StringVar(value="3232")          # Default OTA port
        self.esp_password = tk.StringVar()

        # Upload options
        self.upload_firmware = tk.BooleanVar(value=True)
        self.upload_filesystem = tk.BooleanVar(value=False)

        # Control variables
        self.upload_in_progress = False
        self.current_process = None

        self.setup_ui()

    def setup_ui(self):
        """Create and arrange all GUI elements"""
        # Main container with padding
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky="nsew")

        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)

        # File selection
        files_frame = ttk.LabelFrame(main_frame, text="File Selection", padding="5")
        files_frame.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(0, 10))
        files_frame.columnconfigure(1, weight=1)

        # Firmware file
        self.firmware_check = ttk.Checkbutton(files_frame, text="Firmware (.bin):",
                                              variable=self.upload_firmware,
                                              command=self.on_firmware_check_changed)
        self.firmware_check.grid(row=0, column=0, sticky="w", pady=5)

        self.firmware_entry = ttk.Entry(files_frame, textvariable=self.firmware_path, width=40)
        self.firmware_entry.grid(row=0, column=1, sticky="ew", pady=5, padx=(5, 5))

        self.firmware_browse_btn = ttk.Button(files_frame, text="Browse",
                                              command=self.browse_firmware)
        self.firmware_browse_btn.grid(row=0, column=2, pady=5)

        # Filesystem file
        self.filesystem_check = ttk.Checkbutton(files_frame, text="Filesystem (.bin):",
                                                variable=self.upload_filesystem,
                                                command=self.on_filesystem_check_changed)
        self.filesystem_check.grid(row=1, column=0, sticky="w", pady=5)

        self.filesystem_entry = ttk.Entry(files_frame, textvariable=self.filesystem_path,
                                          width=40, state='disabled')
        self.filesystem_entry.grid(row=1, column=1, sticky="ew", pady=5, padx=(5, 5))

        self.filesystem_browse_btn = ttk.Button(files_frame, text="Browse",
                                                command=self.browse_filesystem, state='disabled')
        self.filesystem_browse_btn.grid(row=1, column=2, pady=5)

        # Connection settings
        conn_frame = ttk.LabelFrame(main_frame, text="ESP32 Connection", padding="5")
        conn_frame.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(0, 10))

        # ESP32 host/IP address
        ttk.Label(conn_frame, text="IP Address:").grid(row=0, column=0, sticky="w", pady=5)
        ttk.Entry(conn_frame, textvariable=self.esp_ip, width=20).grid(row=0, column=1, sticky="w", pady=5, padx=(5, 0))

        # ESP32 port
        ttk.Label(conn_frame, text="Port:").grid(row=1, column=0, sticky="w", pady=5)
        ttk.Entry(conn_frame, textvariable=self.esp_port, width=10).grid(row=1, column=1, sticky="w", pady=5,
                                                                         padx=(5, 0))

        # Password
        ttk.Label(conn_frame, text="Password (optional):").grid(row=2, column=0, sticky="w", pady=5)
        ttk.Entry(conn_frame, textvariable=self.esp_password, show="*", width=20).grid(row=2, column=1, sticky="w",
                                                                                       pady=5, padx=(5, 0))

        # Progress bar
        self.progress = ttk.Progressbar(main_frame, mode='indeterminate')
        self.progress.grid(row=3, column=0, columnspan=3, sticky="ew", pady=(20, 10))

        # Control buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=4, column=0, columnspan=3, pady=10)

        self.upload_button = ttk.Button(button_frame, text="Start Upload", command=self.start_upload)
        self.upload_button.pack(side=tk.LEFT, padx=(0, 10))

        self.cancel_button = ttk.Button(button_frame, text="Cancel", command=self.cancel_upload, state='disabled')
        self.cancel_button.pack(side=tk.LEFT)

        # Log/Status area
        ttk.Label(main_frame, text="Status Log:").grid(row=5, column=0, sticky="w", pady=(20, 5))

        # Create scrolled text widget for logs
        self.log_text = scrolledtext.ScrolledText(main_frame, height=12, width=80)
        self.log_text.grid(row=6, column=0, columnspan=3, sticky="nsew", pady=(0, 10))

        main_frame.rowconfigure(6, weight=1)

        # Add initial message
        self.log_message("CleverCoffee OTA Flasher ready. Select files and enter ESP32 details.")

    def on_firmware_check_changed(self):
        """Handle firmware checkbox state change"""
        if self.upload_firmware.get():
            self.firmware_entry.config(state='normal')
            self.firmware_browse_btn.config(state='normal')
        else:
            self.firmware_entry.config(state='disabled')
            self.firmware_browse_btn.config(state='disabled')

    def on_filesystem_check_changed(self):
        """Handle filesystem checkbox state change"""
        if self.upload_filesystem.get():
            self.filesystem_entry.config(state='normal')
            self.filesystem_browse_btn.config(state='normal')
        else:
            self.filesystem_entry.config(state='disabled')
            self.filesystem_browse_btn.config(state='disabled')

    def browse_firmware(self):
        """Open file dialog to select firmware binary"""
        file_path = filedialog.askopenfilename(
            title="Select Firmware Binary",
            filetypes=[
                ("Binary files", "*.bin"),
                ("All files", "*.*")
            ]
        )
        if file_path:
            self.firmware_path.set(file_path)
            self.log_message(f"Selected firmware: {os.path.basename(file_path)}")

    def browse_filesystem(self):
        """Open file dialog to select filesystem image"""
        file_path = filedialog.askopenfilename(
            title="Select Filesystem Image",
            filetypes=[
                ("Binary files", "*.bin"),
                ("Image files", "*.img"),
                ("LittleFS files", "*.littlefs"),
                ("All files", "*.*")
            ]
        )
        if file_path:
            self.filesystem_path.set(file_path)
            self.log_message(f"Selected filesystem: {os.path.basename(file_path)}")

    def log_message(self, message: str):
        """Add a message to the log area with timestamp"""
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)  # Auto-scroll to bottom
        self.root.update_idletasks()  # Force GUI update

    def validate_inputs(self) -> bool:
        """Validate user inputs before starting upload"""
        # Check if at least one upload type is selected
        if not self.upload_firmware.get() and not self.upload_filesystem.get():
            messagebox.showerror("Error", "Please select at least one file type to upload")
            return False

        # Validate firmware if selected
        if self.upload_firmware.get():
            if not self.firmware_path.get():
                messagebox.showerror("Error", "Please select a firmware file")
                return False
            if not os.path.exists(self.firmware_path.get()):
                messagebox.showerror("Error", "Selected firmware file does not exist")
                return False

        # Validate filesystem if selected
        if self.upload_filesystem.get():
            if not self.filesystem_path.get():
                messagebox.showerror("Error", "Please select a filesystem file")
                return False
            if not os.path.exists(self.filesystem_path.get()):
                messagebox.showerror("Error", "Selected filesystem file does not exist")
                return False

        # Validate connection settings
        if not self.esp_ip.get().strip():
            messagebox.showerror("Error", "Please enter ESP32 IP address")
            return False

        if not self.esp_port.get().strip():
            messagebox.showerror("Error", "Please enter port number")
            return False

        try:
            int(self.esp_port.get())
        except ValueError:
            messagebox.showerror("Error", "Port must be a number")
            return False

        return True

    def start_upload(self):
        """Start the OTA upload process"""
        if not self.validate_inputs():
            return

        if self.upload_in_progress:
            return

        # Start upload in a separate thread to prevent GUI freezing
        self.upload_in_progress = True
        self.upload_button.config(state='disabled')
        self.cancel_button.config(state='normal')
        self.progress.start()

        self.log_message("Starting OTA upload...")

        # Run espota in a separate thread
        upload_thread = threading.Thread(target=self.run_uploads)
        upload_thread.daemon = True
        upload_thread.start()

    def run_uploads(self):
        """Run the upload(s) in sequence"""
        try:
            upload_success = True

            # Upload firmware first if selected
            if self.upload_firmware.get():
                self.log_message("📱 Uploading firmware...")
                if not self.run_single_upload(self.firmware_path.get(), "app"):
                    upload_success = False

            # Upload filesystem if selected and firmware succeeded (or not selected)
            if self.upload_filesystem.get() and upload_success:
                self.log_message("💾 Uploading filesystem...")
                if not self.run_single_upload(self.filesystem_path.get(), "spiffs"):
                    upload_success = False

            if upload_success:
                self.log_message("✅ All uploads completed successfully!")
            else:
                self.log_message("❌ One or more uploads failed")

        except Exception as e:
            self.log_message(f"❌ Error: {str(e)}")
        finally:
            # Reset UI state
            self.upload_in_progress = False
            self.current_process = None
            self.root.after(0, self.reset_ui)  # Schedule UI reset on main thread

    def run_single_upload(self, file_path: str, partition_type: str) -> bool:
        """Run a single espota upload"""
        try:
            # Build the espota command
            espota_path = get_espota_path()
            cmd = [
                sys.executable,  # Python executable
                espota_path,
                "-i", self.esp_ip.get(),
                "-p", self.esp_port.get(),
                "-f", file_path
            ]

            # Add partition parameter for filesystem uploads
            if partition_type == "spiffs":
                cmd.append("-s")  # This tells espota to upload to SPIFFS partition

            # Add password if provided
            if self.esp_password.get().strip():
                cmd.extend(["-a", self.esp_password.get()])

            file_name = os.path.basename(file_path)
            self.log_message(f"Running: espota.py -i {self.esp_ip.get()} -p {self.esp_port.get()} -f {file_name}" +
                             (" -s" if partition_type == "spiffs" else ""))

            # Run the process
            self.current_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )

            # Read output line by line
            if self.current_process.stdout:
                for line in self.current_process.stdout:
                    if not self.upload_in_progress:  # Check if cancelled
                        return False
                    self.log_message(line.strip())

            # Wait for process to complete
            return_code = self.current_process.wait()

            if return_code == 0:
                self.log_message(f"✅ {partition_type.title()} upload completed successfully!")
                return True
            else:
                self.log_message(f"❌ {partition_type.title()} upload failed with return code: {return_code}")
                return False

        except FileNotFoundError:
            self.log_message("❌ Error: espota.py not found. Please ensure it's in the same directory.")
            return False
        except Exception as e:
            self.log_message(f"❌ Error during {partition_type} upload: {str(e)}")
            return False

    def cancel_upload(self):
        """Cancel the ongoing upload"""
        if self.current_process:
            self.current_process.terminate()
            self.log_message("Upload cancelled by user")
        self.upload_in_progress = False
        self.reset_ui()

    def reset_ui(self):
        """Reset UI elements after upload completion or cancellation"""
        self.upload_button.config(state='normal')
        self.cancel_button.config(state='disabled')
        self.progress.stop()


def main():
    root = tk.Tk()
    CleverCoffeeOtaFlasher(root)
    root.mainloop()


if __name__ == "__main__":
    main()
