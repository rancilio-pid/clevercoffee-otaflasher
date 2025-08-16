import datetime
import os
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import tempfile
from pathlib import Path
import queue

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    import urllib.request
    from urllib.error import URLError
    HAS_REQUESTS = False


def get_espota_path() -> str:
    if hasattr(sys, '_MEIPASS'):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))

    return os.path.join(base_path, 'espota.py')


def get_download_directory():
    """Get a user-friendly download directory"""
    # Try to use the user's Downloads folder first
    home = Path.home()

    # Common download folder locations by OS
    download_locations = [
        home / "Downloads",         # Most common
        home / "Desktop",           # Fallback
        home / "Documents",         # Another fallback
        Path(tempfile.gettempdir()) # System temp as last resort
    ]

    # Find the first location that exists and is writable
    for location in download_locations:
        if location.exists() and location.is_dir():
            try:
                # Test if we can write to this directory
                test_file = location / "test_write.tmp"
                test_file.touch()
                test_file.unlink()
                return location / "CleverCoffee_Binaries"
            except (PermissionError, OSError):
                continue

    # If all else fails, use temp directory
    return Path(tempfile.mkdtemp(prefix="clevercoffee_"))

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
        self.download_button = None
        self.open_folder_button = None
        self.download_path_var = None
        self.root = root
        self.root.title("CleverCoffee OTA Flasher")
        self.root.geometry("800x850")
        self.center_window()
        self.root.resizable(True, True)

        # Variables for storing user inputs
        self.firmware_path = tk.StringVar()
        self.filesystem_path = tk.StringVar()
        self.esp_ip = tk.StringVar(value="silvia.local")    # Default IP
        self.esp_port = tk.StringVar(value="3232")          # Default OTA port
        self.esp_password = tk.StringVar(value="otapass")   # Default CleverCoffee OTA password
        self.download_path_var = tk.StringVar()

        # Upload options
        self.upload_firmware = tk.BooleanVar(value=True)
        self.upload_filesystem = tk.BooleanVar(value=True)

        # Control variables
        self.upload_in_progress = False
        self.current_process = None
        self.last_download_dir = None

        # GitHub release info
        # TODO hardcoded for pre-release
        self.github_release_tag = "v4.0.0-beta3"
        self.github_repo = "rancilio-pid/clevercoffee"
        self.binary_urls = {
            "firmware.bin": f"https://github.com/{self.github_repo}/releases/download/{self.github_release_tag}/firmware.bin",
            "littlefs.bin": f"https://github.com/{self.github_repo}/releases/download/{self.github_release_tag}/littlefs.bin"
        }

        self.setup_ui()

    def center_window(self):
        """Center the window on the screen"""
        self.root.update_idletasks()

        # Get screen dimensions
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()

        # Get window dimensions
        window_width = self.root.winfo_width()
        window_height = self.root.winfo_height()

        # Calculate center position
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2

        # Set window position
        self.root.geometry(f"{window_width}x{window_height}+{x}+{y}")

    def setup_ui(self):
        """Create and arrange all GUI elements"""
        # Main container with padding
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky="nsew")

        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)

        # Download from GitHub section
        download_frame = ttk.LabelFrame(main_frame, text="Download from GitHub", padding="5")
        download_frame.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 10))
        download_frame.columnconfigure(0, weight=1)

        info_frame = ttk.Frame(download_frame)
        info_frame.grid(row=0, column=0, columnspan=3, sticky="ew", pady=5)
        info_frame.columnconfigure(0, weight=1)

        ttk.Label(info_frame, text=f"Release: {self.github_release_tag}",
                  font=("TkDefaultFont", 9, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(info_frame, text="Repository: rancilio-pid/clevercoffee",
                  font=("TkDefaultFont", 8)).grid(row=1, column=0, sticky="w")

        # Download path display
        path_frame = ttk.Frame(download_frame)
        path_frame.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(5, 0))
        path_frame.columnconfigure(1, weight=1)

        ttk.Label(path_frame, text="Download to:", font=("TkDefaultFont", 8)).grid(row=0, column=0, sticky="w")
        download_path_entry = ttk.Entry(path_frame, textvariable=self.download_path_var,
                                        state='readonly', font=("TkDefaultFont", 8))
        download_path_entry.grid(row=0, column=1, sticky="ew", padx=(5, 5))

        # Buttons frame
        button_frame = ttk.Frame(download_frame)
        button_frame.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(5, 0))

        self.download_button = ttk.Button(button_frame, text="Download Latest Binaries",
                                          command=self.download_binaries)
        self.download_button.pack(side=tk.LEFT)

        self.open_folder_button = ttk.Button(button_frame, text="Open Download Folder",
                                             command=self.open_download_folder, state='disabled')
        self.open_folder_button.pack(side=tk.LEFT, padx=(10, 0))

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
        conn_frame = ttk.LabelFrame(main_frame, text="ESP32 OTA Connection", padding="5")
        conn_frame.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(0, 10))

        # ESP32 host/IP address
        ttk.Label(conn_frame, text="IP Address:").grid(row=0, column=0, sticky="w", pady=5)
        ttk.Entry(conn_frame, textvariable=self.esp_ip, width=20).grid(row=0, column=1, sticky="w", pady=5, padx=(5, 0))

        # ESP32 port
        ttk.Label(conn_frame, text="Port:").grid(row=1, column=0, sticky="w", pady=5)
        ttk.Entry(conn_frame, textvariable=self.esp_port, width=10).grid(row=1, column=1, sticky="w", pady=5,
                                                                         padx=(5, 0))

        # Password
        ttk.Label(conn_frame, text="Password:").grid(row=2, column=0, sticky="w", pady=5)
        password_entry = ttk.Entry(conn_frame, textvariable=self.esp_password, show="*", width=20)
        password_entry.grid(row=2, column=1, sticky="w", pady=5, padx=(5, 0))

        ttk.Label(conn_frame, text="(Default: otapass)",
                  font=("TkDefaultFont", 8), foreground="gray").grid(row=2, column=2, sticky="w", pady=5, padx=(5, 0))

        # Progress bar
        self.progress = ttk.Progressbar(main_frame, mode='indeterminate')
        self.progress.grid(row=3, column=0, columnspan=3, sticky="ew", pady=(20, 10))

        # Control buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=4, column=0, columnspan=3, pady=10)

        self.upload_button = ttk.Button(button_frame, text="Start OTA Upload", command=self.start_upload)
        self.upload_button.pack(side=tk.LEFT, padx=(0, 10))

        self.cancel_button = ttk.Button(button_frame, text="Cancel", command=self.cancel_upload, state='disabled')
        self.cancel_button.pack(side=tk.LEFT)

        # Status log
        log_label = ttk.Label(main_frame, text="Status Log:")
        log_label.grid(row=7, column=0, columnspan=3, sticky="w", padx=5, pady=(10, 0))

        self.log_text = scrolledtext.ScrolledText(main_frame, height=20, width=85)
        self.log_text.grid(row=8, column=0, columnspan=3, sticky="nsew", padx=5, pady=5)

        main_frame.rowconfigure(6, weight=1)

        # Set initial download path
        self._update_download_path_display()

        # Add initial message
        self.log_message("CleverCoffee OTA Flasher ready. Download binaries from GitHub or select files manually.")

    def _update_download_path_display(self):
        """Update the download path display"""
        download_dir = get_download_directory()
        self.download_path_var.set(str(download_dir))

    def open_download_folder(self):
        """Open the download folder in the system file manager"""
        if self.last_download_dir and self.last_download_dir.exists():
            try:
                if sys.platform.startswith('darwin'):  # macOS
                    subprocess.run(['open', str(self.last_download_dir)])
                elif sys.platform.startswith('win'):  # Windows
                    subprocess.run(['explorer', str(self.last_download_dir)])
                else:  # Linux and others
                    subprocess.run(['xdg-open', str(self.last_download_dir)])
                self.log_message(f"📂 Opened download folder: {self.last_download_dir}")
            except Exception as e:
                self.log_message(f"❌ Could not open folder: {str(e)}")
        else:
            messagebox.showwarning("Warning", "No download folder available. Please download files first.")

    def download_binaries(self):
        """Download binary files from GitHub release"""
        if self.upload_in_progress:
            return

        self.upload_in_progress = True
        self.download_button.config(state='disabled')
        self.upload_button.config(state='disabled')
        self.progress.start()
        self.log_message("🌐 Starting download from GitHub...")

        # Run download in a separate thread
        download_thread = threading.Thread(target=self._download_binaries_thread)
        download_thread.daemon = True
        download_thread.start()

    def _download_binaries_thread(self):
        """Download binaries in a separate thread"""
        try:
            # Get download directory
            download_dir = get_download_directory()

            # Create directory if it doesn't exist
            download_dir.mkdir(parents=True, exist_ok=True)
            self.last_download_dir = download_dir

            self.log_message(f"📁 Download directory: {download_dir}")

            success_count = 0
            total_files = len(self.binary_urls)

            for filename, url in self.binary_urls.items():
                try:
                    self.log_message(f"⬇️ Downloading {filename}...")
                    local_path = download_dir / filename

                    if HAS_REQUESTS:
                        # Use requests for better SSL handling
                        response = requests.get(url, stream=True, timeout=30)
                        response.raise_for_status()

                        total_size = int(response.headers.get('content-length', 0))

                        with open(local_path, 'wb') as f:
                            downloaded = 0
                            for chunk in response.iter_content(chunk_size=8192):
                                if chunk:
                                    f.write(chunk)
                                    downloaded += len(chunk)
                                    if total_size > 0:
                                        percent = (downloaded * 100) // total_size
                                        if percent % 20 == 0 and percent > 0:
                                            self.log_message(f"   Progress: {percent}%")
                    else:
                        # Fallback to urllib with SSL context workaround
                        import ssl

                        # Create unverified SSL context (less secure but works)
                        ssl_context = ssl.create_default_context()
                        ssl_context.check_hostname = False
                        ssl_context.verify_mode = ssl.CERT_NONE

                        def progress_hook(block_num, block_size, total_size):
                            if total_size > 0:
                                percent = min(100, (block_num * block_size * 100) // total_size)
                                if percent % 20 == 0 and percent > 0:
                                    self.log_message(f"   Progress: {percent}%")

                        # Use the SSL context with urllib
                        opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ssl_context))
                        urllib.request.install_opener(opener)
                        urllib.request.urlretrieve(url, str(local_path), progress_hook)

                    # Verify file was downloaded and has content
                    if local_path.exists() and local_path.stat().st_size > 0:
                        file_size = local_path.stat().st_size
                        self.log_message(f"✅ Downloaded {filename} ({file_size:,} bytes)")

                        # Set the appropriate path variable and enable checkbox
                        if filename == "firmware.bin":
                            self.firmware_path.set(str(local_path))
                            self.upload_firmware.set(True)
                        elif filename == "littlefs.bin":
                            self.filesystem_path.set(str(local_path))
                            self.upload_filesystem.set(True)

                        success_count += 1
                    else:
                        self.log_message(f"❌ Downloaded {filename} but file is empty or missing")

                except Exception as e:
                    self.log_message(f"❌ Failed to download {filename}: {str(e)}")
                    # Additional SSL-specific error info
                    if "SSL" in str(e) or "certificate" in str(e).lower():
                        self.log_message(f"💡 SSL certificate issue detected. This is common with bundled apps.")
                        self.log_message(
                            f"   Try downloading files manually from: https://github.com/{self.github_repo}/releases/tag/{self.github_release_tag}")

            if success_count == total_files:
                self.log_message(f"✅ Successfully downloaded all {total_files} files!")
                self.log_message(f"📂 Files saved to: {download_dir}")
                self.log_message(
                    f"💡 Files are ready for OTA upload. Check desired options and click 'Start OTA Upload'.")
            elif success_count > 0:
                self.log_message(f"⚠️ Downloaded {success_count}/{total_files} files")
                self.log_message(f"📂 Files saved to: {download_dir}")
            else:
                self.log_message("❌ Failed to download any files. Please check your internet connection.")
                self.log_message(
                    f"💡 Manual download: https://github.com/{self.github_repo}/releases/tag/{self.github_release_tag}")

        except Exception as e:
            self.log_message(f"❌ Download error: {str(e)}")
        finally:
            # Update UI state on main thread
            self.root.after(0, self._update_ui_after_download)

    def _update_ui_after_download(self):
        """Update UI elements after download completion"""
        self.upload_in_progress = False
        self.download_button.config(state='normal')
        self.upload_button.config(state='normal')
        self.progress.stop()

        # Enable "Open Folder" button if we have a download directory
        if self.last_download_dir:
            self.open_folder_button.config(state='normal')

        # Update checkbox states based on downloaded files
        self.on_firmware_check_changed()
        self.on_filesystem_check_changed()

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
        self.log_text.see(tk.END)       # Auto-scroll to bottom
        self.root.update_idletasks()    # Force GUI update

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

        # Validate password is provided
        if not self.esp_password.get().strip():
            messagebox.showerror("Error", "Password is required for CleverCoffee OTA uploads.\nDefault password is 'otapass'")
            return False

        return True

    def test_connectivity(self):
        """Test basic network connectivity to the ESP32"""
        try:
            import socket

            self.log_message(f"🔍 Testing basic connectivity to {self.esp_ip.get()}...")

            # Try to resolve the hostname/IP first
            try:
                ip_address = socket.gethostbyname(self.esp_ip.get())
                self.log_message(f"✅ Host resolution successful: {self.esp_ip.get()} -> {ip_address}")
            except socket.gaierror:
                self.log_message(f"❌ Cannot resolve hostname: {self.esp_ip.get()}")
                return False

            common_ports = [80, 443, 22, 23, 3232]  # Include the OTA port

            reachable = False
            for port in common_ports:
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(2)  # Short timeout
                    result = sock.connect_ex((ip_address, port))
                    sock.close()

                    if result == 0:
                        self.log_message(f"✅ Host is reachable (responded on port {port})")
                        reachable = True
                        break
                except:
                    continue

            if not reachable:
                self.log_message(f"⚠️ Host may not be reachable on common ports")
                self.log_message(f"This is normal for OTA-only devices - proceeding with upload")

            return True

        except Exception as e:
            self.log_message(f"⚠️ Network test inconclusive: {str(e)}")
            self.log_message(f"Proceeding with OTA upload anyway")
            return True

    def start_upload(self):
        """Start the OTA upload process"""
        if not self.validate_inputs():
            return

        if self.upload_in_progress:
            return

        self.test_connectivity()

        # Start upload in a separate thread to prevent GUI freezing
        self.upload_in_progress = True
        self.upload_button.config(state='disabled')
        self.download_button.config(state='disabled')
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
                self.log_message("Uploading firmware...")
                if not self.run_single_upload(self.firmware_path.get(), "app"):
                    upload_success = False

            # Upload filesystem if selected and firmware succeeded (or not selected)
            if self.upload_filesystem.get() and upload_success:
                self.log_message("Uploading filesystem...")
                if not self.run_single_upload(self.filesystem_path.get(), "spiffs"):
                    upload_success = False

            if upload_success:
                self.log_message("✅ All uploads completed successfully!")
                self.log_message("🔄 ESP32 should restart automatically with the new firmware.")
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
                "-f", file_path,
                "-d",  # Enable debug mode for more verbose output
                "-r"  # Enable progress reporting
            ]

            # Add partition parameter for filesystem uploads
            if partition_type == "spiffs":
                cmd.append("-s")  # This tells espota to upload to SPIFFS partition

            # Add password if provided
            if self.esp_password.get().strip():
                cmd.extend(["-a", self.esp_password.get()])

            file_name = os.path.basename(file_path)
            file_size = os.path.getsize(file_path)
            self.log_message(f"Uploading {file_name} ({file_size:,} bytes)")
            self.log_message(f"Command: espota.py -i {self.esp_ip.get()} -p {self.esp_port.get()} -f {file_name}" +
                             (" -s" if partition_type == "spiffs" else "") + " -d -r")

            # Add troubleshooting info
            self.log_message(f"🔍 Upload info:")
            self.log_message(f"   File size: {file_size:,} bytes ({file_size / 1024 / 1024:.1f} MB)")
            self.log_message(f"   Target: {self.esp_ip.get()}:{self.esp_port.get()}")
            self.log_message(f"   Partition: {partition_type}")

            # Create a queue for real-time output
            output_queue = queue.Queue()

            # Start the process
            env = os.environ.copy()
            env['PYTHONUNBUFFERED'] = '1'  # Force Python to be unbuffered

            self.current_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=0,
                universal_newlines=True,
                env=env
            )

            # Start threads to read stdout and stderr
            def read_output(pipe, queue_obj, stream_name):
                try:
                    for line in iter(pipe.readline, ''):
                        if line:
                            queue_obj.put((stream_name, line))
                    pipe.close()
                except:
                    pass

            stdout_thread = threading.Thread(target=read_output,
                                             args=(self.current_process.stdout, output_queue, 'stdout'))
            stderr_thread = threading.Thread(target=read_output,
                                             args=(self.current_process.stderr, output_queue, 'stderr'))

            stdout_thread.daemon = True
            stderr_thread.daemon = True
            stdout_thread.start()
            stderr_thread.start()

            # Process output in real-time
            last_progress_line = ""
            while self.current_process.poll() is None:
                if not self.upload_in_progress:  # Check if cancelled
                    self.current_process.terminate()
                    return False

                try:
                    # Get output with a short timeout to allow checking for cancellation
                    stream_name, line = output_queue.get(timeout=0.1)

                    clean_line = line.strip()
                    if not clean_line:
                        continue

                    # Handle progress updates (they come on stderr and contain progress bars)
                    if "Uploading: [" in clean_line and "%" in clean_line:
                        # This is a progress update, show it and overwrite previous progress
                        self.update_progress_line(f"   {clean_line}")
                        last_progress_line = clean_line
                    else:
                        # Regular output line
                        if clean_line != last_progress_line:  # Avoid duplicate lines
                            self.log_message(f"   {clean_line}")

                            # Check for specific status messages
                            if "Authentication OK" in clean_line:
                                self.log_message("✅ Authentication successful, starting file transfer...")
                            elif any(error in clean_line.upper() for error in ["ERROR:", "FAILED", "EXCEPTION"]):
                                self.log_message(f"⚠️ Error detected: {clean_line}")
                            elif "No response" in clean_line:
                                self.log_message("No response from ESP32 - check if device is still connected")

                except queue.Empty:
                    continue  # No output available, continue checking
                except:
                    break

            # Process any remaining output
            while not output_queue.empty():
                try:
                    stream_name, line = output_queue.get_nowait()
                    clean_line = line.strip()
                    if clean_line and "Uploading: [" not in clean_line:
                        self.log_message(f"   {clean_line}")
                except queue.Empty:
                    break

            # Wait for threads to finish
            stdout_thread.join(timeout=1)
            stderr_thread.join(timeout=1)

            # Get the final return code
            return_code = self.current_process.wait()

            if return_code == 0:
                self.log_message(f"✅ {partition_type.title()} upload completed successfully!")
                return True
            else:
                self.log_message(f"❌ {partition_type.title()} upload failed with return code: {return_code}")
                self.log_message("💡 Troubleshooting suggestions:")
                self.log_message("   • Try restarting the ESP32 device")
                self.log_message("   • Check if the ESP32 has enough free memory")
                self.log_message("   • Verify the IP address is correct and reachable")
                self.log_message("   • Try uploading a smaller file first")
                return False

        except FileNotFoundError:
            self.log_message("❌ Error: espota.py not found. Please ensure it's in the same directory.")
            return False
        except Exception as e:
            self.log_message(f"❌ Error during {partition_type} upload: {str(e)}")
            return False

    def update_progress_line(self, message: str):
        """Update the last line in the log with progress information"""

        def update_ui():
            # Get current content
            current_content = self.log_text.get("1.0", tk.END).rstrip('\n')
            lines = current_content.split('\n') if current_content else []

            # If the last line was a progress line, replace it
            if lines and "   Uploading: [" in lines[-1]:
                lines[-1] = message
            else:
                lines.append(message)

            # Update the text widget
            self.log_text.delete("1.0", tk.END)
            self.log_text.insert("1.0", '\n'.join(lines) + '\n')
            self.log_text.see(tk.END)
            self.root.update_idletasks()

        # Schedule the UI update on the main thread
        self.root.after(0, update_ui)

    def cancel_upload(self):
        """Cancel the ongoing upload"""
        if self.current_process:
            self.current_process.terminate()
            self.log_message("⏹️ Upload cancelled by user")
        self.upload_in_progress = False
        self.reset_ui()

    def reset_ui(self):
        """Reset UI elements after upload completion or cancellation"""
        self.upload_button.config(state='normal')
        self.download_button.config(state='normal')
        self.cancel_button.config(state='disabled')
        self.progress.stop()


def main():
    root = tk.Tk()
    CleverCoffeeOtaFlasher(root)
    root.mainloop()


if __name__ == "__main__":
    main()