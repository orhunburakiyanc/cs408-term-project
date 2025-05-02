#!/usr/bin/env python3
"""Central server for the environmental monitoring system.
Receives data from drones, displays it in real-time, and stores it for analysis."""
import socket
import json
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading
import datetime
import time
import argparse

# Check if ttkbootstrap is available
try:
    import ttkbootstrap as ttk
    from ttkbootstrap import Style
    USING_BOOTSTRAP = True
except ImportError:
    import tkinter.ttk as ttk
    USING_BOOTSTRAP = False

class ServerGUI:
    """
    GUI for the central server in the environmental monitoring system.
    Displays data received from drones including sensor readings, anomalies,
    and system logs.
    """

    def __init__(self, root):
        """
        Initialize the GUI components.
        
        Args:
            root: The tkinter root window
        """
        self.root = root
        
        # Apply ttkbootstrap theme if available
        if USING_BOOTSTRAP:
            if not isinstance(root, ttk.Window):
                self.style = Style(theme="darkly")
                self.style.configure('TLabelframe', borderwidth=1)
                self.style.configure('TLabelframe.Label', font=('Helvetica', 10, 'bold'))
        
        self.root.title("Environmental Monitoring System - Central Server")
        self.root.geometry("1200x800")
        self.server_instance = None  # Will be set by CentralServer
        
        # Data storage
        self.drone_statuses = {}  # Store latest status for each drone
        self.drone_data = []  # Store all data entries
        self.anomalies = []  # Store all anomalies
        
        # Thread safety
        self.update_lock = threading.Lock()
        
        # Set up the UI
        self.setup_ui()
        
        # Register window close handler
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def setup_ui(self):
        """Set up the main UI components and layout"""
        # Configure grid weights for responsive resizing
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(0, weight=1)
        
        # Create main container with padding
        main_frame = ttk.Frame(self.root)
        main_frame.grid(row=0, column=0, sticky="nsew", padx=15, pady=15)
        
        # Create notebook for tabbed interface
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.grid(row=0, column=0, sticky="nsew")
        
        # Configure grid weights
        main_frame.grid_columnconfigure(0, weight=1)
        main_frame.grid_rowconfigure(0, weight=1)
        main_frame.grid_rowconfigure(1, weight=0)  # Status bar
        
        # Create tab frames
        main_tab = ttk.Frame(self.notebook)
        data_logs_tab = ttk.Frame(self.notebook)
        
        # Add tabs to notebook
        self.notebook.add(main_tab, text="Main Dashboard")
        self.notebook.add(data_logs_tab, text="Data Logs")
        
        # Configure main tab grid weights
        main_tab.grid_columnconfigure(0, weight=2)  # Left column (tables)
        main_tab.grid_columnconfigure(1, weight=1)  # Right column (log)
        main_tab.grid_rowconfigure(0, weight=3)  # Drone status table
        main_tab.grid_rowconfigure(1, weight=4)  # Anomaly table
        
        # Configure data logs tab grid weights
        data_logs_tab.grid_columnconfigure(0, weight=1)
        data_logs_tab.grid_rowconfigure(0, weight=1)
        
        # Create panels in main tab
        self.setup_drone_status_panel(main_tab)
        self.setup_anomaly_panel(main_tab)
        self.setup_log_panel(main_tab)
        
        # Create data logs panel in data logs tab
        self.setup_data_logs_panel(data_logs_tab)
        
        # Setup status bar in main frame
        self.setup_status_bar(main_frame)

    def setup_drone_status_panel(self, parent):
        """
        Create the drone status summary panel
        
        Args:
            parent: Parent frame
        """
        # Create frame with label and padding
        if USING_BOOTSTRAP:
            status_frame = ttk.Labelframe(parent, text="Drone Status Dashboard", padding=10, bootstyle="primary")
        else:
            status_frame = ttk.LabelFrame(parent, text="Drone Status Dashboard", padding=10)
        
        status_frame.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")
        
        # Create Treeview for drone status table
        columns = ("drone_id", "timestamp", "temperature", "humidity", "battery", "status")
        self.drone_table = ttk.Treeview(status_frame, columns=columns, show="headings", height=6)
        
        # Configure columns
        self.drone_table.heading("drone_id", text="Drone ID")
        self.drone_table.heading("timestamp", text="Last Update")
        self.drone_table.heading("temperature", text="Temp (°C)")
        self.drone_table.heading("humidity", text="Humidity (%)")
        self.drone_table.heading("battery", text="Battery (%)")
        self.drone_table.heading("status", text="Status")
        
        # Set column widths and anchors for better alignment
        self.drone_table.column("drone_id", width=100, anchor="center")
        self.drone_table.column("timestamp", width=150, anchor="center")
        self.drone_table.column("temperature", width=80, anchor="center")
        self.drone_table.column("humidity", width=80, anchor="center")
        self.drone_table.column("battery", width=80, anchor="center")
        self.drone_table.column("status", width=150, anchor="center")
        
        # Add scrollbars for better navigation
        y_scrollbar = ttk.Scrollbar(status_frame, orient="vertical", command=self.drone_table.yview)
        self.drone_table.configure(yscrollcommand=y_scrollbar.set)
        
        x_scrollbar = ttk.Scrollbar(status_frame, orient="horizontal", command=self.drone_table.xview)
        self.drone_table.configure(xscrollcommand=x_scrollbar.set)
        
        # Use grid for responsive layout
        status_frame.grid_columnconfigure(0, weight=1)
        status_frame.grid_rowconfigure(0, weight=1)
        status_frame.grid_rowconfigure(1, weight=0)
        
        self.drone_table.grid(row=0, column=0, sticky="nsew")
        y_scrollbar.grid(row=0, column=1, sticky="ns")
        x_scrollbar.grid(row=1, column=0, sticky="ew")
        
        # Create tags for different status conditions
        if USING_BOOTSTRAP:
            self.drone_table.tag_configure("low_battery", background="#dc3545", foreground="white")  # Bootstrap danger
            self.drone_table.tag_configure("returning", background="#fd7e14", foreground="white")  # Bootstrap orange
            self.drone_table.tag_configure("charging", background="#198754", foreground="white")  # Bootstrap success
            self.drone_table.tag_configure("normal", background="")  # Default background
            self.drone_table.tag_configure("anomaly", background="#ffc107", foreground="black")  # Bootstrap warning
        else:
            self.drone_table.tag_configure("low_battery", background="#ffcccc")
            self.drone_table.tag_configure("returning", background="#ffcc99")
            self.drone_table.tag_configure("charging", background="#ccffcc")
            self.drone_table.tag_configure("normal", background="#ffffff")
            self.drone_table.tag_configure("anomaly", background="#ffffcc")

    def setup_anomaly_panel(self, parent):
        """
        Create the anomaly display panel
        
        Args:
            parent: Parent frame
        """
        # Create frame with label and padding
        if USING_BOOTSTRAP:
            anomaly_frame = ttk.Labelframe(parent, text="Anomaly Alerts", padding=10, bootstyle="danger")
        else:
            anomaly_frame = ttk.LabelFrame(parent, text="Anomaly Alerts", padding=10)
            
        anomaly_frame.grid(row=1, column=0, padx=5, pady=5, sticky="nsew")
        
        # Create Treeview for anomaly table
        columns = ("drone_id", "sensor_id", "issue", "value", "timestamp")
        self.anomaly_table = ttk.Treeview(anomaly_frame, columns=columns, show="headings", height=8)
        
        # Configure columns
        self.anomaly_table.heading("drone_id", text="Drone")
        self.anomaly_table.heading("sensor_id", text="Sensor")
        self.anomaly_table.heading("issue", text="Issue")
        self.anomaly_table.heading("value", text="Value")
        self.anomaly_table.heading("timestamp", text="Timestamp")
        
        # Set column widths and anchors
        self.anomaly_table.column("drone_id", width=100, anchor="center")
        self.anomaly_table.column("sensor_id", width=100, anchor="center")
        self.anomaly_table.column("issue", width=150, anchor="w")  # Left-align text
        self.anomaly_table.column("value", width=80, anchor="center")
        self.anomaly_table.column("timestamp", width=150, anchor="center")
        
        # Add scrollbars
        y_scrollbar = ttk.Scrollbar(anomaly_frame, orient="vertical", command=self.anomaly_table.yview)
        self.anomaly_table.configure(yscrollcommand=y_scrollbar.set)
        
        x_scrollbar = ttk.Scrollbar(anomaly_frame, orient="horizontal", command=self.anomaly_table.xview)
        self.anomaly_table.configure(xscrollcommand=x_scrollbar.set)
        
        # Use grid for responsive layout
        anomaly_frame.grid_columnconfigure(0, weight=1)
        anomaly_frame.grid_rowconfigure(0, weight=1)
        anomaly_frame.grid_rowconfigure(1, weight=0)
        
        self.anomaly_table.grid(row=0, column=0, sticky="nsew")
        y_scrollbar.grid(row=0, column=1, sticky="ns")
        x_scrollbar.grid(row=1, column=0, sticky="ew")
        
        # Configure tags for different anomaly types with more vibrant and consistent colors
        if USING_BOOTSTRAP:
            self.anomaly_table.tag_configure("temperature", background="#f8d7da", foreground="#721c24")  # Bootstrap danger light
            self.anomaly_table.tag_configure("humidity", background="#d1ecf1", foreground="#0c5460")  # Bootstrap info light
            self.anomaly_table.tag_configure("battery", background="#fff3cd", foreground="#856404")  # Bootstrap warning light
            self.anomaly_table.tag_configure("connection", background="#d6d8d9", foreground="#1b1e21")  # Bootstrap secondary light
        else:
            self.anomaly_table.tag_configure("temperature", background="#ffcccc")
            self.anomaly_table.tag_configure("humidity", background="#ccffff")
            self.anomaly_table.tag_configure("battery", background="#ffffcc")
            self.anomaly_table.tag_configure("connection", background="#dddddd")

    def setup_data_logs_panel(self, parent):
        """
        Create the data logs panel to display all received data
        
        Args:
            parent: Parent frame
        """
        # Create frame with label and padding
        if USING_BOOTSTRAP:
            data_logs_frame = ttk.Labelframe(parent, text="Data Logs", padding=10, bootstyle="primary")
        else:
            data_logs_frame = ttk.LabelFrame(parent, text="Data Logs", padding=10)
            
        data_logs_frame.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")
        
        # Configure grid weights
        data_logs_frame.grid_columnconfigure(0, weight=1)
        data_logs_frame.grid_rowconfigure(0, weight=1)
        data_logs_frame.grid_rowconfigure(1, weight=0)
        
        # Create Treeview for data logs table
        columns = ("timestamp", "drone_id", "temperature", "humidity", "battery", "status", "has_anomalies")
        self.data_logs_table = ttk.Treeview(data_logs_frame, columns=columns, show="headings", height=15)
        
        # Configure columns
        self.data_logs_table.heading("timestamp", text="Timestamp")
        self.data_logs_table.heading("drone_id", text="Drone ID")
        self.data_logs_table.heading("temperature", text="Temperature (°C)")
        self.data_logs_table.heading("humidity", text="Humidity (%)")
        self.data_logs_table.heading("battery", text="Battery (%)")
        self.data_logs_table.heading("status", text="Status")
        self.data_logs_table.heading("has_anomalies", text="Anomalies")
        
        # Set column widths and anchors
        self.data_logs_table.column("timestamp", width=150, anchor="center")
        self.data_logs_table.column("drone_id", width=100, anchor="center")
        self.data_logs_table.column("temperature", width=100, anchor="center")
        self.data_logs_table.column("humidity", width=100, anchor="center")
        self.data_logs_table.column("battery", width=80, anchor="center")
        self.data_logs_table.column("status", width=150, anchor="center")
        self.data_logs_table.column("has_anomalies", width=80, anchor="center")
        
        # Add scrollbars
        y_scrollbar = ttk.Scrollbar(data_logs_frame, orient="vertical", command=self.data_logs_table.yview)
        self.data_logs_table.configure(yscrollcommand=y_scrollbar.set)
        
        x_scrollbar = ttk.Scrollbar(data_logs_frame, orient="horizontal", command=self.data_logs_table.xview)
        self.data_logs_table.configure(xscrollcommand=x_scrollbar.set)
        
        # Place elements in grid
        self.data_logs_table.grid(row=0, column=0, sticky="nsew")
        y_scrollbar.grid(row=0, column=1, sticky="ns")
        x_scrollbar.grid(row=1, column=0, sticky="ew")
        
        # Configure tags for different data entries
        if USING_BOOTSTRAP:
            self.data_logs_table.tag_configure("normal", background="")
            self.data_logs_table.tag_configure("anomaly", background="#fff3cd", foreground="#856404")
            self.data_logs_table.tag_configure("low_battery", background="#f8d7da", foreground="#721c24")
            self.data_logs_table.tag_configure("returning", background="#fd7e14", foreground="white")
            self.data_logs_table.tag_configure("charging", background="#d1e7dd", foreground="#0f5132")
        else:
            self.data_logs_table.tag_configure("normal", background="#ffffff")
            self.data_logs_table.tag_configure("anomaly", background="#ffffcc")
            self.data_logs_table.tag_configure("low_battery", background="#ffcccc")
            self.data_logs_table.tag_configure("returning", background="#ffcc99")
            self.data_logs_table.tag_configure("charging", background="#ccffcc")

    def setup_log_panel(self, parent):
        """
        Create the log display panel
        
        Args:
            parent: Parent frame
        """
        # Create frame with label and padding
        if USING_BOOTSTRAP:
            log_frame = ttk.Labelframe(parent, text="System Log", padding=10, bootstyle="info")
        else:
            log_frame = ttk.LabelFrame(parent, text="System Log", padding=10)
            
        log_frame.grid(row=0, column=1, rowspan=2, padx=5, pady=5, sticky="nsew")
        
        # Configure grid weights
        log_frame.grid_columnconfigure(0, weight=1)
        log_frame.grid_rowconfigure(0, weight=1)
        
        # Create custom-styled Text widget for log
        if USING_BOOTSTRAP:
            # For bootstrap, use the built-in styling
            self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, width=40, height=20, 
                                                    bg="#343a40", fg="#f8f9fa")
        else:
            # For standard ttk, use custom colors
            self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, width=40, height=20, 
                                                    bg="#f0f0f0", fg="#000000")
        
        self.log_text.grid(row=0, column=0, sticky="nsew")
        self.log_text.config(state=tk.DISABLED)  # Make it read-only
        
        # Configure tags for different log levels with consistent colors
        self.log_text.tag_configure("info", foreground="#0dcaf0")  # Light blue for info
        self.log_text.tag_configure("warning", foreground="#ffc107")  # Yellow for warnings
        self.log_text.tag_configure("error", foreground="#dc3545")  # Red for errors
        self.log_text.tag_configure("success", foreground="#20c997")  # Green for success
        self.log_text.tag_configure("timestamp", foreground="#6c757d")  # Gray for timestamps

    def setup_status_bar(self, parent):
        """
        Create the status bar at the bottom
        
        Args:
            parent: Parent frame
        """
        # Create frame with padding and border
        if USING_BOOTSTRAP:
            status_bar = ttk.Frame(parent, padding=5, bootstyle="secondary")
        else:
            status_bar = ttk.Frame(parent, padding=5)
            
        status_bar.grid(row=1, column=0, pady=(5, 0), sticky="ew")
        
        # Server status indicator with proper spacing
        ttk.Label(status_bar, text="Server Status:").pack(side=tk.LEFT, padx=(5, 5))
        
        # Create status label with appropriate styling
        if USING_BOOTSTRAP:
            self.status_label = ttk.Label(status_bar, text="Initializing...", width=15, 
                                       bootstyle="info", padding=5)
        else:
            self.status_label = ttk.Label(status_bar, text="Initializing...", width=15, padding=5)
            
        self.status_label.pack(side=tk.LEFT, padx=5)
        
        # Connection counter
        ttk.Label(status_bar, text="Active Connections:").pack(side=tk.LEFT, padx=(20, 5))
        
        # Create connection count label with appropriate styling
        if USING_BOOTSTRAP:
            self.connection_count = ttk.Label(status_bar, text="0", width=5, 
                                          bootstyle="info", padding=5)
        else:
            self.connection_count = ttk.Label(status_bar, text="0", width=5, padding=5)
            
        self.connection_count.pack(side=tk.LEFT, padx=5)
        
        # Add exit button with improved styling
        if USING_BOOTSTRAP:
            exit_btn = ttk.Button(status_bar, text="Exit Server", bootstyle="danger-outline", 
                                command=self.on_closing)
        else:
            exit_btn = ttk.Button(status_bar, text="Exit Server", command=self.on_closing)
            
        exit_btn.pack(side=tk.RIGHT, padx=10)

    def log(self, message, level='info'):
        """
        Add a message to the log panel
        
        Args:
            message: Message text
            level: Log level (info, warning, error, success)
        """
        # Schedule GUI update to be thread-safe
        self.root.after(0, self._update_log, message, level)

    def _update_log(self, message, level):
        """
        Update log in the GUI thread
        
        Args:
            message: Message text
            level: Log level
        """
        # Get current time for timestamp
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        
        # Enable editing
        self.log_text.config(state=tk.NORMAL)
        
        # Insert timestamp and message
        self.log_text.insert(tk.END, f"[{timestamp}] ", "timestamp")
        self.log_text.insert(tk.END, f"{message}\n", level)
        
        # Auto-scroll to end
        self.log_text.see(tk.END)
        
        # Disable editing
        self.log_text.config(state=tk.DISABLED)

    def update_server_status(self, status, active_connection_count):
        """
        Update the server status indicators
        
        Args:
            status: Server status text
            active_connection_count: Number of active connections
        """
        # Schedule GUI update to be thread-safe
        self.root.after(0, self._update_status_display, status, active_connection_count)

    def _update_status_display(self, status, active_connection_count):
        """
        Update status display in the GUI thread
        
        Args:
            status: Server status text
            active_connection_count: Number of active connections
        """
        # Update status label text
        self.status_label.config(text=status)
        
        # Update style based on status
        if USING_BOOTSTRAP:
            if status == "Running":
                self.status_label.configure(bootstyle="success")
            elif status == "Stopped":
                self.status_label.configure(bootstyle="danger")
            elif status == "Error":
                self.status_label.configure(bootstyle="warning")
            else:
                self.status_label.configure(bootstyle="info")
        
        # Update connection count
        self.connection_count.config(text=str(active_connection_count))

    def add_data_entry(self, drone_data):
        """
        Process a new data entry from a drone
        
        Args:
            drone_data: Dictionary containing drone telemetry data
        """
        # Store data and update UI in a thread-safe way
        with self.update_lock:
            # Store data (up to 1000 entries)
            self.drone_data.append(drone_data)
            if len(self.drone_data) > 1000:
                self.drone_data.pop(0)
        
        # Extract drone identification
        drone_id = drone_data.get("drone_id", "unknown")
        
        # Always log data reception
        self.log(f"Received data from {drone_id}", "info")
        
        # Extract relevant data
        battery = drone_data.get("battery_level", 0)
        temperature = drone_data.get("average_temperature", 0)
        humidity = drone_data.get("average_humidity", 0)
        
        # Get raw status from data
        raw_status = drone_data.get("status", "Connected")
        
        # Standardize status format (convert snake_case to Title Case)
        if "_" in raw_status:
            status = " ".join(word.capitalize() for word in raw_status.split("_"))
        else:
            status = raw_status
        
        # Check for special status values
        if status.lower() == "returning to base" or status.lower() == "returning_to_base":
            status = "Returning To Base"
        elif status.lower() == "charging":
            status = "Charging"
        
        # Check for anomalies
        anomalies = drone_data.get("anomalies", [])
        has_anomalies = len(anomalies) > 0
        
        # Process anomalies if present
        if has_anomalies and status not in ["Returning To Base", "Charging"]:
            status = "Anomalies Detected"
            self.add_anomalies(drone_id, anomalies)
        
        # Handle low battery status (unless already in a special status)
        if battery < 20 and status not in ["Returning To Base", "Charging", "Anomalies Detected"]:
            status = "Returning To Base"
            self.log(f"Drone {drone_id} is low on battery ({battery:.1f}%) - Returning to Base", "warning")
        
        # Check for status change and log appropriately
        old_status = None
        if drone_id in self.drone_statuses:
            old_status = self.drone_statuses[drone_id].get("status")
        
        # Now that we have the final status determination, update the drone status in memory
        self.update_drone_status(drone_id, status, battery, temperature, humidity)
        
        # Only log status changes, not repeats
        if old_status is not None and old_status != status:
            self.log(f"Drone {drone_id} status changed: {old_status} → {status}", 
                    "warning" if status in ["Returning To Base", "Anomalies Detected"] else 
                    "success" if status == "Charging" else "info")
        
        # Update data logs table
        self.root.after(0, self._update_data_logs, drone_data, status, has_anomalies)
        
        # Update drone status display
        self.root.after(0, self._update_drone_display, drone_data, status)

    def _update_data_logs(self, drone_data, status, has_anomalies):
        """
        Update the data logs table with new data
        
        Args:
            drone_data: Dictionary containing drone telemetry data
            status: Current drone status
            has_anomalies: Boolean indicating if anomalies are present
        """
        # Extract data
        drone_id = drone_data.get("drone_id", "unknown")
        timestamp = drone_data.get("timestamp", datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"))
        temperature = drone_data.get("average_temperature", 0)
        humidity = drone_data.get("average_humidity", 0)
        battery = drone_data.get("battery_level", 0)
        
        # Format display values
        display_timestamp = timestamp.replace("T", " ").replace("Z", "")
        display_temp = f"{temperature:.1f}"
        display_humidity = f"{humidity:.1f}"
        display_battery = f"{battery:.1f}"
        display_anomalies = "Yes" if has_anomalies else "No"
        
        # Determine row tag based on status and conditions
        tag = "normal"
        if status == "Anomalies Detected":
            tag = "anomaly"
        elif status == "Returning To Base":
            tag = "returning"
        elif status == "Charging":
            tag = "charging"
        elif battery < 20:
            tag = "low_battery"
        
        # Insert into data logs table (newest at the top)
        values = (display_timestamp, drone_id, display_temp, display_humidity, 
                  display_battery, status, display_anomalies)
        self.data_logs_table.insert("", 0, values=values, tags=(tag,))
        
        # Limit visible logs (delete old ones if over 1000)
        children = self.data_logs_table.get_children()
        if len(children) > 1000:
            self.data_logs_table.delete(children[-1])

    def _update_drone_display(self, drone_data, status=None):
        """
        Update the drone display table with new data
        
        Args:
            drone_data: Dictionary containing drone telemetry data
            status: Override status if provided
        """
        # Extract data from the drone_data
        drone_id = drone_data.get("drone_id", "unknown")
        timestamp = drone_data.get("timestamp", datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"))
        temperature = drone_data.get("average_temperature", 0)
        humidity = drone_data.get("average_humidity", 0)
        battery = drone_data.get("battery_level", 0)
        
        # Use provided status or get from data
        if status is None:
            status = drone_data.get("status", "Connected")
            # Convert snake_case to Title Case if needed
            if "_" in status:
                status = " ".join(word.capitalize() for word in status.split("_"))
        
        # Format display values
        display_timestamp = timestamp.replace("T", " ").replace("Z", "")
        display_temp = f"{temperature:.1f}"
        display_humidity = f"{humidity:.1f}"
        display_battery = f"{battery:.1f}"
        
        # Check if this drone is already in the table
        existing_items = self.drone_table.get_children()
        item_id = None
        
        for item in existing_items:
            if self.drone_table.item(item, "values")[0] == drone_id:
                item_id = item
                break
        
        # Determine row tag based on status
        tag = "normal"
        if battery < 20:
            tag = "low_battery"
        elif status == "Charging":
            tag = "charging"
        elif status == "Returning To Base":
            tag = "returning"
        elif status == "Anomalies Detected":
            tag = "anomaly"
        
        # Update or insert into table
        values = (drone_id, display_timestamp, display_temp, display_humidity, display_battery, status)
        if item_id:
            self.drone_table.item(item_id, values=values, tags=(tag,))
        else:
            self.drone_table.insert("", tk.END, values=values, tags=(tag,))

    def add_anomalies(self, drone_id, anomalies):
        """
        Add anomaly entries to the anomaly panel
        
        Args:
            drone_id: ID of the drone reporting anomalies
            anomalies: List of anomaly dictionaries
        """
        if not anomalies:
            return
        
        # Store anomalies
        with self.update_lock:
            for anomaly in anomalies:
                anomaly_entry = anomaly.copy()
                anomaly_entry["drone_id"] = drone_id
                self.anomalies.append(anomaly_entry)
                
                # Limit to 1000 entries
                if len(self.anomalies) > 1000:
                    self.anomalies.pop(0)
        
        # Schedule UI update
        self.root.after(0, self._update_anomaly_display, drone_id, anomalies)
        
        # Log anomalies
        for anomaly in anomalies:
            issue = anomaly.get("issue", "unknown")
            sensor_id = anomaly.get("sensor_id", "unknown")
            value = anomaly.get("value", 0)
            self.log(f"Anomaly detected on {drone_id}, sensor {sensor_id}: {issue} ({value})", "warning")

    def _update_anomaly_display(self, drone_id, anomalies):
        """
        Update the anomaly display with new anomalies
        
        Args:
            drone_id: ID of the drone reporting anomalies
            anomalies: List of anomaly dictionaries
        """
        # Process each anomaly
        for anomaly in anomalies:
            # Extract data
            sensor_id = anomaly.get("sensor_id", "unknown")
            issue = anomaly.get("issue", "unknown")
            value = anomaly.get("value", 0)
            timestamp = anomaly.get("timestamp", datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"))
            
            # Format display values
            display_timestamp = timestamp.replace("T", " ").replace("Z", "")
            display_value = f"{value:.1f}" if isinstance(value, (float, int)) else str(value)
            
            # Format issue text (convert snake_case to readable text)
            if "_" in issue:
                display_issue = " ".join(word.capitalize() for word in issue.split("_"))
            else:
                display_issue = issue.capitalize()
            
            # Determine row tag based on issue type
            tag = "temperature" if "temp" in issue.lower() else \
                "humidity" if "humid" in issue.lower() else \
                "battery" if "battery" in issue.lower() else \
                "connection"
            
            # Insert into anomaly table (newest at the top)
            values = (drone_id, sensor_id, display_issue, display_value, display_timestamp)
            self.anomaly_table.insert("", 0, values=values, tags=(tag,))
            
            # Limit visible anomalies (delete old ones if over 100)
            children = self.anomaly_table.get_children()
            if len(children) > 100:
                self.anomaly_table.delete(children[-1])

    def update_drone_status(self, drone_id, status, battery, temperature, humidity):
        """
        Update the stored status for a drone
        
        Args:
            drone_id: ID of the drone
            status: Current status text
            battery: Battery level percentage
            temperature: Average temperature
            humidity: Average humidity
        """
        # Get current timestamp
        timestamp = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
        
        # Create or update status entry without triggering additional logs
        self.drone_statuses[drone_id] = {
            "status": status,
            "timestamp": timestamp,
            "battery": battery,
            "temperature": temperature,
            "humidity": humidity
        }

    def on_closing(self):
        """
        Handle window closing event
        """
        # Show confirmation dialog
        if messagebox.askokcancel("Quit", "Do you want to close the server?"):
            # Log that we're shutting down
            self.log("Server shutting down...", "warning")
            
            # Tell the server to stop if it exists
            if self.server_instance is not None:
                try:
                    # Assume the server has a stop method
                    self.server_instance.stop()
                except Exception as e:
                    self.log(f"Error stopping server: {e}", "error")
            
            # Destroy the window after a short delay
            self.root.after(500, self.root.destroy)

class CentralServer:
    """Central server that receives data from drones and displays it"""

    def __init__(self, listen_ip="127.0.0.1", listen_port=3500):
        # Initialize GUI
        try:            
            self.root = ttk.Window(themename="superhero")
        except ImportError:
            self.root = tk.Tk()  # Fallback to standard tkinter
        
        self.gui = ServerGUI(self.root)
        self.gui.server_instance = self

        # Server settings
        self.listen_ip = listen_ip
        self.listen_port = listen_port

        # Thread control
        self.server_running = False
        # Store active connections with associated info (socket, last_active time, drone_id)
        self.active_connections = {}
        self.connection_lock = threading.Lock() # Lock for accessing active_connections

        # Start the server
        self.gui.log("Central server initializing...")

        # Set the window closing protocol
        self.root.protocol("WM_DELETE_WINDOW", self.gui.on_closing)


    def start(self):
        """Start the server and GUI"""
        self.server_running = True

        # Start server thread
        self.server_thread = threading.Thread(target=self._start_server)
        self.server_thread.daemon = True # Allow main thread to exit even if this is running
        self.server_thread.start()

        # Start connection monitor thread
        self.monitor_thread = threading.Thread(target=self._monitor_connections)
        self.monitor_thread.daemon = True # Allow main thread to exit
        self.monitor_thread.start()

        self.gui.log(f"Central server started and listening on {self.listen_ip}:{self.listen_port}")
        self.gui.update_server_status("Running", len(self.active_connections))

        # Start the Tkinter main loop
        self.root.mainloop()


    def stop(self):
        """Stop the server and close all connections"""
        self.gui.log("Server shutting down...")
        self.server_running = False

        # Close all active connections
        with self.connection_lock:
            # Iterate over a copy of keys because the dict will be modified
            for addr in list(self.active_connections.keys()):
                client_info = self.active_connections.get(addr)
                if client_info and client_info.get("connection"):
                    try:
                        client_info["connection"].shutdown(socket.SHUT_RDWR) # Attempt graceful shutdown
                        client_info["connection"].close()
                        self.gui.log(f"Closed connection to {addr}")
                    except Exception as e:
                        self.gui.log(f"Error closing connection to {addr}: {e}", level='error')
                # Remove from active connections
                if addr in self.active_connections:
                    del self.active_connections[addr]

        # Close server socket if it exists
        if hasattr(self, 'server_socket') and self.server_socket:
            try:
                self.server_socket.close()
                self.gui.log("Server socket closed.")
            except Exception as e:
                self.gui.log(f"Error closing server socket: {e}", level='error')

        self.gui.update_server_status("Stopped", 0)

        # Stop the GUI main loop
        self.root.quit()
        self.root.destroy()


    def _start_server(self):
        """Start the TCP server to listen for drone connections"""
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # Allow the socket to reuse an address quickly after closing
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.listen_ip, self.listen_port))
            self.server_socket.listen(5) # Max 5 pending connections
            self.gui.log(f"Server socket bound to {self.listen_ip}:{self.listen_port}")

            while self.server_running:
                # Set a timeout so the accept call doesn't block indefinitely,
                # allowing the loop to check `self.server_running`
                self.server_socket.settimeout(1.0)

                try:
                    client_socket, addr = self.server_socket.accept()

                    # Accept the connection and start a new thread to handle it
                    self.gui.log(f"New connection attempt from {addr}")

                    # Add to active connections with timestamp
                    with self.connection_lock:
                        self.active_connections[addr] = {
                            "connection": client_socket,
                            "last_active": time.time(),
                            "drone_id": None  # Will be set when first data is received
                        }

                    # Update connection count in GUI
                    self.gui.update_server_status("Running", len(self.active_connections))
                    self.gui.log(f"Connection accepted from {addr}")

                    # Start client handler thread
                    client_thread = threading.Thread(target=self._handle_client,
                                                   args=(client_socket, addr))
                    client_thread.daemon = True # Thread exits when main program exits
                    client_thread.start()

                except socket.timeout:
                    # This is expected, just continue the loop to check server_running
                    continue
                except Exception as e:
                    if self.server_running: # Only log errors if the server is supposed to be running
                        self.gui.log(f"Error accepting connection: {e}", level='error')
                        # Small delay before trying to accept again after an error
                        time.sleep(0.1)

        except Exception as e:
            self.gui.log(f"Fatal server error: {e}", level='error')
            self.gui.update_server_status("Error", len(self.active_connections))
            self.server_running = False # Stop the server loop on fatal error
        finally:
            # Ensure server socket is closed if the loop exits
            if hasattr(self, 'server_socket') and self.server_socket:
                 try:
                     self.server_socket.close()
                     self.gui.log("Server socket closed in finally block.")
                 except Exception as e:
                     self.gui.log(f"Error closing server socket in finally block: {e}", level='error')


    def _handle_client(self, client_socket, addr):
        """Handle communication with a connected drone"""
        buffer = ""
        drone_id = None # Store drone_id once identified

        try:
            self.gui.log(f"Handler started for client {addr}")
            client_socket.settimeout(60)  # Timeout for receiving data

            while self.server_running:
                try:
                    # Receive data in chunks
                    data = client_socket.recv(4096).decode('utf-8')
                    if not data:
                        # Client disconnected gracefully
                        self.gui.log(f"Client {addr} disconnected gracefully")
                        break # Exit the handler loop

                    # Update last active timestamp for this connection
                    with self.connection_lock:
                        if addr in self.active_connections:
                            self.active_connections[addr]["last_active"] = time.time()

                    buffer += data

                    # Process complete JSON objects separated by newline
                    while '\n' in buffer:
                        line, buffer = buffer.split('\n', 1)
                        if not line.strip(): # Skip empty lines
                            continue

                        try:
                            drone_data = json.loads(line)

                            # Identify drone ID if not already known
                            if drone_id is None and "drone_id" in drone_data:
                                drone_id = drone_data["drone_id"]
                                with self.connection_lock:
                                     if addr in self.active_connections:
                                          self.active_connections[addr]["drone_id"] = drone_id
                                self.gui.log(f"Identified drone {drone_id} at {addr}")

                            # Process the received data (temperature, humidity, battery, anomalies)
                            self._process_drone_data(drone_data)

                        except json.JSONDecodeError:
                            self.gui.log(f"Error: Invalid JSON from {addr}. Data: '{line[:100]}...'", level='error')
                            # Optionally, skip the rest of the buffer if JSON is consistently bad
                            # buffer = "" # Uncomment to clear buffer on JSON error
                            continue # Continue processing the rest of the buffer


                except socket.timeout:
                    # No data received within the timeout period.
                    # The monitor thread will handle marking as disconnected if it persists.
                    # Just continue the loop to check server_running and try recv again.
                    continue
                except ConnectionResetError:
                    self.gui.log(f"Connection reset by peer: {addr}", level='warning')
                    break # Exit the handler loop on connection reset
                except Exception as e:
                    # Catch other potential errors during recv or processing
                    self.gui.log(f"Error handling data from {addr}: {e}", level='error')
                    break # Exit the handler loop on other errors

        except Exception as e:
            # Catch exceptions that might occur outside the inner loop (less common)
            self.gui.log(f"Unexpected error in client handler for {addr}: {e}", level='error')

        finally:
            # This block executes when the client handler thread is exiting
            self.gui.log(f"Handler exiting for client {addr}")

            # Clean up the connection in the active_connections dictionary
            with self.connection_lock:
                if addr in self.active_connections:
                     # Remove the connection entry
                     del self.active_connections[addr]
                     self.gui.log(f"Removed connection {addr} from active list.")

            # Update connection count in GUI
            active_count = len(self.active_connections)
            self.gui.update_server_status("Running", active_count)

            # Mark the drone as disconnected in the GUI if its ID was known
            if drone_id:
                 # Check if this drone ID is still associated with any active connection
                 # This handles cases where a drone might reconnect quickly
                 is_drone_still_connected = any(info.get("drone_id") == drone_id and info.get("connection") is not None
                                                 for info in self.active_connections.values())
                 if not is_drone_still_connected:
                      # If no other active connection has this drone_id, mark it as disconnected in GUI
                      # The monitor thread will eventually mark it if this handler didn't run due to an error
                      # But doing it here ensures a faster GUI update on clean disconnects
                      current_status = self.gui.drone_statuses.get(drone_id, {}).get("status")
                      if current_status != "Disconnected":
                           self.gui.log(f"Drone {drone_id} appears disconnected.", level='warning')
                           # The monitor thread will add the anomaly, just update status here
                           self.gui.update_drone_status(drone_id, "Disconnected",
                                                        self.gui.drone_statuses.get(drone_id, {}).get("battery", 0),
                                                        self.gui.drone_statuses.get(drone_id, {}).get("temp", 0),
                                                        self.gui.drone_statuses.get(drone_id, {}).get("humidity", 0))

            # Ensure the socket is closed
            try:
                client_socket.close()
                self.gui.log(f"Socket closed for {addr}")
            except Exception as e:
                self.gui.log(f"Error closing socket for {addr}: {e}", level='error')


    def _process_drone_data(self, drone_data):
        """Process data received from a drone and update the GUI"""
        drone_id = drone_data.get("drone_id")
        if not drone_id:
            self.gui.log("Received data without drone_id. Cannot process.", level='warning')
            return

        # Log reception of data
        self.gui.log(f"Processing data from drone {drone_id}")

        # Add the raw data entry to the internal storage and data table
        self.gui.add_data_entry(drone_data)

        # Process anomalies if present
        anomalies = drone_data.get("anomalies")
        if anomalies and isinstance(anomalies, list):
            self.gui.add_anomalies(drone_id, anomalies)

        # Update drone status in the GUI (this is also done in add_data_entry, but calling here ensures status is updated even if data entry fails)
        status = "Connected" # Default status if data is received
        if anomalies:
             status = "Anomalies Detected" # Indicate anomalies in status

        self.gui.update_drone_status(
            drone_id,
            status,
            drone_data.get("battery_level", 0), # Default to 0 if missing
            drone_data.get("average_temperature", 0), # Default to 0 if missing
            drone_data.get("average_humidity", 0) # Default to 0 if missing
        )


    def _monitor_connections(self):
        """Periodically check active connections and remove inactive ones"""
        timeout_seconds = 45 # Mark as disconnected if no data for 45 seconds
        cleanup_interval = 15 # Check every 15 seconds

        self.gui.log(f"Connection monitor started with timeout {timeout_seconds}s and interval {cleanup_interval}s.")

        while self.server_running:
            time.sleep(cleanup_interval)

            if not self.server_running:
                break # Exit loop if server is stopping

            now = time.time()
            disconnected_addrs = []

            with self.connection_lock:
                # Find connections that have timed out
                for addr, client_info in self.active_connections.items():
                    if (now - client_info["last_active"]) > timeout_seconds:
                        disconnected_addrs.append(addr)

                # Process timed-out connections
                for addr in disconnected_addrs:
                    client_info = self.active_connections.get(addr)
                    if client_info:
                         drone_id = client_info.get("drone_id", addr) # Use addr if drone_id not known
                         self.gui.log(f"Connection to {drone_id} at {addr} timed out.", level='warning')

                         # Close the socket if it's still open
                         conn = client_info.get("connection")
                         if conn:
                             try:
                                 conn.shutdown(socket.SHUT_RDWR) # Attempt graceful shutdown
                                 conn.close()
                                 self.gui.log(f"Closed timed-out socket for {addr}")
                             except Exception as e:
                                 self.gui.log(f"Error closing timed-out socket for {addr}: {e}", level='error')

                         # Remove from active connections
                         if addr in self.active_connections:
                              del self.active_connections[addr]

                         # Update GUI status for the drone
                         # Check if this drone ID is still associated with any *other* active connection
                         is_drone_still_connected = any(info.get("drone_id") == drone_id and info.get("connection") is not None
                                                         for info in self.active_connections.values())

                         if not is_drone_still_connected:
                              # If no other active connection has this drone_id, mark it as disconnected in GUI
                              current_status = self.gui.drone_statuses.get(drone_id, {}).get("status")
                              if current_status != "Disconnected":
                                   self.gui.log(f"Marking drone {drone_id} as disconnected in GUI.")
                                   self.gui.update_drone_status(drone_id, "Disconnected",
                                                                 self.gui.drone_statuses.get(drone_id, {}).get("battery", 0),
                                                                 self.gui.drone_statuses.get(drone_id, {}).get("temp", 0),
                                                                 self.gui.drone_statuses.get(drone_id, {}).get("humidity", 0))
                                   # Add a 'connection_lost' anomaly
                                   self.gui.add_anomalies(drone_id, [{
                                       "issue": "connection_lost",
                                       "value": timeout_seconds, # Value could be the timeout duration
                                       "threshold": timeout_seconds,
                                       "timestamp": datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                                       "sensor_id": "N/A"
                                   }])


            # Update connection count in GUI
            active_count = len(self.active_connections)
            self.gui.update_server_status("Running", active_count)


# --- Main Execution Block ---
if __name__ == "__main__":
    # Setup command line arguments
    parser = argparse.ArgumentParser(description="Environmental Monitoring Central Server")
    parser.add_argument("--ip", type=str, default="127.0.0.1",
                        help="IP address to listen on (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=3500,
                        help="Port to listen on (default: 3500)")

    args = parser.parse_args()

    # Create and start the server
    server = CentralServer(listen_ip=args.ip, listen_port=args.port)
    server.start() # This call blocks until the GUI is closed

