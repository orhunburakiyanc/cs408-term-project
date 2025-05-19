import socket
import threading
import copy
import json
import time
import tkinter as tk
from tkinter import ttk, scrolledtext
import datetime
import random
from queue import Queue, Full
import ttkbootstrap as ttk
from ttkbootstrap.scrolled import ScrolledText
from ttkbootstrap.constants import *
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg


class EdgeProcessor:
    """Processes data received from sensor nodes"""
    
    def __init__(self, window_size=10, temp_threshold_high=30.0, temp_threshold_low=10.0,
                 humidity_threshold_high=80.0, humidity_threshold_low=20.0):
        self.readings = {}  # Dictionary to store readings by sensor_id
        self.previous_readings = {}  # Dictionary to store previous readings by sensor_id
        self.window_size = window_size  # Number of readings to keep for each sensor
        self.temp_threshold_high = temp_threshold_high
        self.temp_threshold_low = temp_threshold_low
        self.humidity_threshold_high = humidity_threshold_high
        self.humidity_threshold_low = humidity_threshold_low
        self.anomalies = []
        self.lock = threading.Lock()  # Lock for thread safety
    
    def update_readings(self, sensor_data):
        """Update the readings dictionary with new sensor data"""
        with self.lock:
            sensor_id = sensor_data["sensor_id"]
            
            # Create entry for new sensor
            if sensor_id not in self.readings:
                self.readings[sensor_id] = []
            
            # Add new reading
            self.readings[sensor_id].append(sensor_data)
            
            
            
            # Check for anomalies
            self._check_anomalies(sensor_data)

    def _check_anomalies(self, sensor_data):
        """Check for anomalous readings and record them"""
        anomaly = None
        
        # Check temperature
        if sensor_data["temperature"] > self.temp_threshold_high:
            anomaly = {
                "sensor_id": sensor_data["sensor_id"],
                "issue": "temperature_too_high",
                "value": sensor_data["temperature"],
                "timestamp": sensor_data["timestamp"]
            }
        elif sensor_data["temperature"] < self.temp_threshold_low:
            anomaly = {
                "sensor_id": sensor_data["sensor_id"],
                "issue": "temperature_too_low",
                "value": sensor_data["temperature"],
                "timestamp": sensor_data["timestamp"]
            }
        
        # Check humidity
        elif sensor_data["humidity"] > self.humidity_threshold_high:
            anomaly = {
                "sensor_id": sensor_data["sensor_id"],
                "issue": "humidity_too_high",
                "value": sensor_data["humidity"],
                "timestamp": sensor_data["timestamp"]
            }
        elif sensor_data["humidity"] < self.humidity_threshold_low:
            anomaly = {
                "sensor_id": sensor_data["sensor_id"],
                "issue": "humidity_too_low",
                "value": sensor_data["humidity"],
                "timestamp": sensor_data["timestamp"]
            }            
        
        # Add anomaly if found and not already present
        if anomaly:
            # Check if this exact anomaly already exists
            anomaly_exists = False
            for existing_anomaly in self.anomalies:
                if (existing_anomaly["sensor_id"] == anomaly["sensor_id"] and
                    existing_anomaly["issue"] == anomaly["issue"] and
                    existing_anomaly["value"] == anomaly["value"] and
                    existing_anomaly["timestamp"] == anomaly["timestamp"]):
                    anomaly_exists = True
                    break
            
            if not anomaly_exists:
                self.anomalies.append(anomaly)
            
            # Keep only recent anomalies (last 10 for example)
            if len(self.anomalies) > 10:
                self.anomalies = self.anomalies[-10:]        
    
    def compute_averages(self):
        """
        Calculates the average temperature and humidity of new readings added since the previous call.

        Returns:
            tuple: (avg_temp, avg_humidity)
        """
        with self.lock:
            new_temps = []
            new_humidities = []

            
            for sensor_id, current_readings_list in self.readings.items():
                
                previous_readings_list = self.previous_readings.get(sensor_id, [])

                
                start_index_for_new = len(previous_readings_list)

                
                for i in range(start_index_for_new, len(current_readings_list)):
                    new_reading = current_readings_list[i]
                    new_temps.append(new_reading["temperature"])
                    new_humidities.append(new_reading["humidity"])

            
            avg_temp = sum(new_temps) / len(new_temps) if new_temps else 0
            avg_humidity = sum(new_humidities) / len(new_humidities) if new_humidities else 0

            
            self.previous_readings = copy.deepcopy(self.readings)

            return avg_temp, avg_humidity
    
    def get_anomalies(self):
        """Return the list of detected anomalies"""
        with self.lock:
            return self.anomalies.copy()
    
    def get_readings(self):
        """Return a copy of the current readings"""
        with self.lock:
            return {k: v.copy() for k, v in self.readings.items()}


class BatteryManager:
    """Simulates and manages drone battery level"""
    
    def __init__(self, initial_level=100, threshold=20, 
                 consumption_rate=0.1, charging_rate=0.5,
                 time_to_return=10, time_to_charge=30):
        self.level = initial_level
        self.threshold = threshold
        self.consumption_rate = consumption_rate
        self.charging_rate = charging_rate
        self.returning_to_base = False
        self.charging = False
        self.returning_start_time = None
        self.charging_start_time = None
        self.time_to_return = time_to_return  # seconds it takes to return to base
        self.lock = threading.Lock()
        self.charge_start_level = 0

        
        self.charge_start_level = 0

        
    
    def consume(self):
        """Simulate battery consumption"""
        with self.lock:
            if not self.charging and not self.returning_to_base:
                self.level -= self.consumption_rate
                self.level = max(0, self.level)
                self.level = max(0, self.level)
                if self.level < self.threshold:
                    self.returning_to_base = True
                    self.returning_start_time = time.time()
                    return True  # Signal that we're now returning to base
            return False
    
    def charge(self):
        """Simulate battery charging when returned to base"""
        with self.lock:
            current_time = time.time()
            
            # If we're returning to base but haven't arrived yet
            if self.returning_to_base and not self.charging and self.returning_start_time:
                # Check if we've arrived at the base
                time_elapsed = current_time - self.returning_start_time
                if time_elapsed >= self.time_to_return:
                    # We've arrived at the base, start charging
                    self.charging = True
                    self.charging_start_time = current_time
                    # Log arrival for debugging
                    if not hasattr(self, 'last_charge_time'):
                        self.last_charge_time = current_time
                    self.charge_start_level = self.level
                    if not hasattr(self, 'last_charge_time'):
                        self.last_charge_time = current_time
                    self.charge_start_level = self.level
                    print(f"[BATTERY] Arrived at base after {time_elapsed:.1f} seconds, starting to charge")
                    return
            
            # If we're charging
            if self.charging and self.level < 80:
                # Calculate charge increase based on time elapsed since last check
                if not hasattr(self, 'last_charge_time'):
                    self.last_charge_time = current_time
                
                time_elapsed = current_time - self.last_charge_time
                self.last_charge_time = current_time
                
                # Calculate charge based on time elapsed and charging rate
                # Charging rate is percent per second
                charge_increase = time_elapsed * self.charging_rate
                self.level = min(80, self.level + charge_increase)                               
                
                # Once charged enough, allow operations to continue
                if self.charging and self.level >= 80:  # Charge to 80% before resuming operations                
                    total_charge_time = current_time - self.charging_start_time
                    self.returning_to_base = False
                    self.charging = False
                    self.returning_start_time = None
                    self.charging_start_time = None
                    self.charge_start_level = 0 # Reset start level
                    if hasattr(self, 'last_charge_time'):
                        delattr(self, 'last_charge_time')
                    print(f"[BATTERY] Charging complete after {total_charge_time:.1f} seconds. Resuming normal operations.")
    
    def check_status(self):
        """Check battery level and status"""
        with self.lock:
            status = {
                "level": self.level,
                "returning_to_base": self.returning_to_base,
                "charging": self.charging
            }
            
            # Add additional status info if returning or charging
            if self.returning_to_base and self.returning_start_time and not self.charging:
                elapsed = time.time() - self.returning_start_time
                status["return_progress"] = min(100, (elapsed / self.time_to_return) * 100)
                status["return_time_left"] = max(0, self.time_to_return - elapsed)
                status["charge_progress"] = 0
                status["charge_time_left"] = 0

            if self.charging and self.charging_start_time  is not None:
                elapsed = time.time() - self.charging_start_time
                percent_needed_total = 80 - self.charge_start_level
                percent_gained_so_far = self.level - self.charge_start_level
                if percent_needed_total > 0: # Avoid division by zero if started >= 80%
                     status["charge_progress"] = min(100, (percent_gained_so_far / percent_needed_total) * 100)
                     # Calculate time left based on current level to 80%
                     percent_remaining_to_80 = 80 - self.level
                     status["charge_time_left"] = max(0, percent_remaining_to_80 / self.charging_rate)
                else:
                    status["charge_progress"] = 100
                    status["charge_time_left"] = 0
            
            elif self.charging and self.charging_start_time is None:
                 # Charging state entered, but start time not set yet (brief moment)
                 status["charge_progress"] = 0
                 status["charge_time_left"] = 0

            else:
                 # Not returning and not charging
                 status["return_progress"] = 0
                 status["return_time_left"] = 0
                 status["charge_progress"] = 0
                 status["charge_time_left"] = 0


            return status
        
    

    

    def set_threshold(self, new_threshold):
        """Sets a new low battery threshold.
           Performs basic validation (5-50%).
        """
        with self.lock: # Ensure thread safety if called from different threads
            if 5 <= new_threshold <= 50:
                self.threshold = new_threshold
                # No need to print here, the GUI method handles feedback
            else:
                 # This case should ideally be caught by GUI validation first,
                 # but good to have a safeguard.
                 print(f"[BATTERY] Attempted to set invalid threshold: {new_threshold}. Must be between 5 and 50.")



class DroneClient:
    """Client to send processed data to the central server"""
    
    def __init__(self, server_ip, server_port, drone_id):
        self.server_ip = server_ip
        self.server_port = server_port
        self.drone_id = drone_id
        self.sock = None
        self.connected = False
        self.lock = threading.Lock()
    
    def connect(self):
        """Connect to the central server"""
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((self.server_ip, self.server_port))
            self.connected = True
            return True
        except ConnectionRefusedError:
            self.connected = False
            return False
    
    def send_to_server(self, avg_temp, avg_humidity, anomalies, battery_level,status):
        """Send processed data to the central server"""
        with self.lock:
            if not self.connected:
                if not self.connect():
                    return False
            
            data = {
                "drone_id": self.drone_id,
                "timestamp": datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                "average_temperature": avg_temp,
                "average_humidity": avg_humidity,
                "anomalies": anomalies,
                "battery_level": battery_level,
                "status": status
            }
            
            try:
                self.sock.sendall((json.dumps(data) + "\n").encode())
                return True
            except (ConnectionResetError, BrokenPipeError):
                self.connected = False
                return False




class DroneGUI:
    """GUI for the drone to display data and status"""
    
    def __init__(self, root,battery_manager_instance):
        # Initialize with ttkbootstrap style
        self.root = root
        self.root.title("Drone Edge Computing Unit")
        self.root.geometry("1200x840")

        self.count = 0

        self.drone_server = None  # Initialize as None
            
        
        # Create tabbed interface with modified style
        self.tab_control = ttk.Notebook(root)
        
        self.battery_timestamps = []


        self.battery_manager = battery_manager_instance
        
        
        # Create tabs
        self.data_tab = ttk.Frame(self.tab_control)
        self.charts_tab = ttk.Frame(self.tab_control)
        self.anomaly_tab = ttk.Frame(self.tab_control)
        self.battery_tab = ttk.Frame(self.tab_control)
        self.nodes_tab = ttk.Frame(self.tab_control) 
        self.log_tab = ttk.Frame(self.tab_control)
        
        self.tab_control.add(self.data_tab, text="Data Stream")
        self.tab_control.add(self.charts_tab, text="Charts")
        self.tab_control.add(self.anomaly_tab, text="Anomalies")
        self.tab_control.add(self.battery_tab, text="Battery Status")
        self.tab_control.add(self.log_tab, text="Logs")
        self.tab_control.add(self.nodes_tab, text="Nodes Status") 
        self.tab_control.pack(expand=1, fill="both")
        
        # Setting up the tabs
        self._setup_data_tab()
        self._setup_charts_tab()
        self._setup_anomaly_tab()
        self._setup_battery_tab()
        self._setup_log_tab()
        self._setup_nodes_tab()
        
        # Battery info status bar
        self._setup_battery_display()
        
        # Data for plotting
        self.timestamps = []
        self.temps = []
        self.humids = []
        self.battery_levels = []
        self.battery_timestamps = []
        
        # Alert banner for battery status
        self._setup_alert_banner()

    # In your DroneGUI class:

    def set_drone_server(self, drone_server):
        """Set the reference to the DroneServer instance"""
        self.drone_server = drone_server

    def apply_threshold(self):
        """Reads threshold from spinbox, validates, and updates BatteryManager."""
        try:
            new_threshold = int(self.threshold_spinbox.get())

            if 5 <= new_threshold <= 50:
            # Update the BatteryManager instance
                self.battery_manager.set_threshold(new_threshold)

            # Update the current threshold display label
                self.current_threshold_label.config(text=f"Current: {self.battery_manager.threshold}%")

                print(f"[GUI] Battery threshold updated to {new_threshold}%")
            # Optional: Show a success message
            # ttk.dialogs.Messagebox.ok("Success", f"Battery threshold set to {new_threshold}%.")

            # Immediately update the plot to show the new threshold line
                self._update_battery_plot()

            else:
            # Value is outside the allowed range
                print(f"[GUI] Invalid threshold value entered: {new_threshold}. Must be between 5 and 50.")
            # Optional: Show an error message
            # ttk.dialogs.Messagebox.show_error("Error", "Threshold must be between 5% and 50%.")
            # Reset spinbox to the current valid value
                self.threshold_spinbox.set(self.battery_manager.threshold)

        except ValueError:
        # Input is not a valid integer
            print(f"[GUI] Invalid input for threshold. Please enter a number.")
        # Optional: Show an error message
        # ttk.dialogs.Messagebox.show_error("Error", "Invalid input. Please enter a valid number.")
        # Reset spinbox to the current valid value
            self.threshold_spinbox.set(self.battery_manager.threshold)

    def _setup_nodes_tab(self):
        """Setup the nodes status tab in the GUI"""
    # Main container frame
        nodes_frame = ttk.Frame(self.nodes_tab)
        nodes_frame.pack(fill="both", expand=True, padx=10, pady=10)
    
    # Create a left and right panel using paned window
        paned = ttk.PanedWindow(nodes_frame, orient="horizontal")
        paned.pack(fill="both", expand=True)
    
    # Left panel - Nodes list
        left_frame = ttk.LabelFrame(paned, text="Connected Sensor Nodes", bootstyle="info")
    
    # Create treeview for nodes list with bootstyle
        self.nodes_tree = ttk.Treeview(left_frame, columns=("Status", "Last Seen"), 
                                  bootstyle="info")
        self.nodes_tree.heading("#0", text="Sensor ID")
        self.nodes_tree.heading("Status", text="Status")
        self.nodes_tree.heading("Last Seen", text="Last Seen")
    
        self.nodes_tree.column("#0", width=120, stretch=tk.YES)
        self.nodes_tree.column("Status", width=80, stretch=tk.YES)
        self.nodes_tree.column("Last Seen", width=150, stretch=tk.YES)
    
    # Add scrollbar
        scrollbar = ttk.Scrollbar(left_frame, orient="vertical", command=self.nodes_tree.yview)
        self.nodes_tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.nodes_tree.pack(side="left", fill="both", expand=True)
    
    # Add nodes tree to paned window
        paned.add(left_frame, weight=1)
    
    # Right panel - Node details and actions
        right_frame = ttk.Frame(paned)
       
    
    # Node details section
        details_frame = ttk.LabelFrame(right_frame, text="Node Details", bootstyle="primary")
        details_frame.pack(fill="both", expand=True, padx=5, pady=5)
    
    # Details grid
        details_grid = ttk.Frame(details_frame)
        details_grid.pack(fill="both", expand=True, padx=10, pady=10)
    
    # Node ID
        ttk.Label(details_grid, text="Node ID:", font=("Helvetica", 10, "bold")).grid(
            row=0, column=0, sticky="w", padx=5, pady=5)
        self.node_id_value = ttk.Label(details_grid, text="Select a node", font=("Helvetica", 10))
        self.node_id_value.grid(row=0, column=1, sticky="w", padx=5, pady=5)
    
    # Connection status
        ttk.Label(details_grid, text="Connection:", font=("Helvetica", 10, "bold")).grid(
            row=1, column=0, sticky="w", padx=5, pady=5)
        self.node_status_value = ttk.Label(details_grid, text="N/A", font=("Helvetica", 10))
        self.node_status_value.grid(row=1, column=1, sticky="w", padx=5, pady=5)
    
    # Last seen
        ttk.Label(details_grid, text="Last Activity:", font=("Helvetica", 10, "bold")).grid(
        row=2, column=0, sticky="w", padx=5, pady=5)
        self.node_lastseen_value = ttk.Label(details_grid, text="N/A", font=("Helvetica", 10))
        self.node_lastseen_value.grid(row=2, column=1, sticky="w", padx=5, pady=5)
    
    # Data statistics
        ttk.Label(details_grid, text="Data Count:", font=("Helvetica", 10, "bold")).grid(
        row=3, column=0, sticky="w", padx=5, pady=5)
        self.node_datacount_value = ttk.Label(details_grid, text="N/A", font=("Helvetica", 10))
        self.node_datacount_value.grid(row=3, column=1, sticky="w", padx=5, pady=5)
    
    # Temperature range
        ttk.Label(details_grid, text="Temp Range:", font=("Helvetica", 10, "bold")).grid(
        row=4, column=0, sticky="w", padx=5, pady=5)
        self.node_temprange_value = ttk.Label(details_grid, text="N/A", font=("Helvetica", 10))
        self.node_temprange_value.grid(row=4, column=1, sticky="w", padx=5, pady=5)
    
    # Humidity range
        ttk.Label(details_grid, text="Humidity Range:", font=("Helvetica", 10, "bold")).grid(
        row=5, column=0, sticky="w", padx=5, pady=5)
        self.node_humidrange_value = ttk.Label(details_grid, text="N/A", font=("Helvetica", 10))
        self.node_humidrange_value.grid(row=5, column=1, sticky="w", padx=5, pady=5)
    
    # Anomaly count
        tk.Label(details_grid, text="Anomalies:", font=("Helvetica", 10, "bold")).grid(
        row=6, column=0, sticky="w", padx=5, pady=5)
        self.node_anomalies_value = ttk.Label(details_grid, text="N/A", font=("Helvetica", 10))
        self.node_anomalies_value.grid(row=6, column=1, sticky="w", padx=5, pady=5)
    
    # Latest reading section
        latest_frame = ttk.LabelFrame(right_frame, text="Latest Reading", bootstyle="success")
        latest_frame.pack(fill="x", padx=5, pady=5)
    
        latest_grid = ttk.Frame(latest_frame)
        latest_grid.pack(fill="both", expand=True, padx=10, pady=10)
    
    # Temperature
        ttk.Label(latest_grid, text="Temperature:", font=("Helvetica", 10, "bold")).grid(
        row=0, column=0, sticky="w", padx=5, pady=5)
        self.latest_temp_value = ttk.Label(latest_grid, text="N/A", font=("Helvetica", 10))
        self.latest_temp_value.grid(row=0, column=1, sticky="w", padx=5, pady=5)
    
    # Humidity
        ttk.Label(latest_grid, text="Humidity:", font=("Helvetica", 10, "bold")).grid(
        row=1, column=0, sticky="w", padx=5, pady=5)
        self.latest_humid_value = ttk.Label(latest_grid, text="N/A", font=("Helvetica", 10))
        self.latest_humid_value.grid(row=1, column=1, sticky="w", padx=5, pady=5)
    
    # Timestamp
        ttk.Label(latest_grid, text="Timestamp:", font=("Helvetica", 10, "bold")).grid(
        row=2, column=0, sticky="w", padx=5, pady=5)
        self.latest_time_value = ttk.Label(latest_grid, text="N/A", font=("Helvetica", 10))
        self.latest_time_value.grid(row=2, column=1, sticky="w", padx=5, pady=5)



        actions_frame = ttk.LabelFrame(right_frame, text="Node Actions", bootstyle="info")
        actions_frame.pack(fill="x", padx=5, pady=(10,5)) # Add some padding

        self.disconnect_node_button = ttk.Button(actions_frame, text="Disconnect Selected Node",
                                                 command=self._on_disconnect_node_clicked,
                                                 state="disabled", bootstyle="danger")
        self.disconnect_node_button.pack(pady=5, padx=5, fill="x")

        # Add right_frame to paned window (make sure this is done correctly)
        paned.add(right_frame, weight=2) # Should be okay here or after right_frame is fully populated.

        # Bind treeview selection event (your existing code)
        self.nodes_tree.bind("<<TreeviewSelect>>", self.on_node_selected)
        
    
    # Bind treeview selection event
        
    
    # Initialize node data storage
        self.node_data = {}  # Dictionary to store node data and statistics
    
    # Store reference to connection_manager and edge_processor (to be set later)
        self.connection_manager = None
        self.edge_processor = None
    
    def _setup_data_tab(self):
        # Create a frame for the data table
        table_frame = ttk.Frame(self.data_tab)
        table_frame.pack(padx=10, pady=10, fill="both", expand=True)
        
        # Add heading for data table
        header_label = ttk.Label(table_frame, text="Sensor Data Stream", font=("Helvetica", 12, "bold"))
        header_label.pack(anchor="w", pady=(0, 10))
        
        # Create Treeview for sensor data with bootsyle
        self.data_tree = ttk.Treeview(table_frame, columns=("Sensor ID", "Temperature", "Humidity", "Timestamp"), 
                                     bootstyle="info")
        self.data_tree.heading("#0", text="Index")
        self.data_tree.heading("Sensor ID", text="Sensor ID")
        self.data_tree.heading("Temperature", text="Temperature")
        self.data_tree.heading("Humidity", text="Humidity")
        self.data_tree.heading("Timestamp", text="Timestamp")
        
        self.data_tree.column("#0", width=50, stretch=tk.NO)
        self.data_tree.column("Sensor ID", width=100, stretch=tk.YES)
        self.data_tree.column("Temperature", width=100, stretch=tk.YES)
        self.data_tree.column("Humidity", width=100, stretch=tk.YES)
        self.data_tree.column("Timestamp", width=200, stretch=tk.YES)
        
        # Add scrollbar to the treeview
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.data_tree.yview)
        self.data_tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.data_tree.pack(fill="both", expand=True)

        controls_frame = ttk.Frame(table_frame)
        controls_frame.pack(fill="x", pady=(10, 0)) # Add some padding

        self.toggle_stream_button = ttk.Button(controls_frame, text="Pause Data Stream",
                                               command=self._on_toggle_data_stream_clicked,
                                               bootstyle="warning")
        self.toggle_stream_button.pack(side="left", padx=5)
    
    def _setup_charts_tab(self):
        # Create a frame for graphs
        graph_frame = ttk.Frame(self.charts_tab)
        graph_frame.pack(padx=10, pady=10, fill="both", expand=True)
        
        # Create matplotlib figure with improved styling
        plt.style.use('ggplot')  # Use ggplot style for better aesthetics
        
        # Create figures with more compact and readable layout
        self.fig = Figure(figsize=(9, 6), dpi=100, tight_layout=True)
        self.temp_ax = self.fig.add_subplot(2, 1, 1)
        self.humid_ax = self.fig.add_subplot(2, 1, 2)
        
        self.canvas = FigureCanvasTkAgg(self.fig, master=graph_frame)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
        
        # Initialize the plots with better styling
        self.temp_line, = self.temp_ax.plot([], [], 'r-', linewidth=2, label='Temperature')
        self.humid_line, = self.humid_ax.plot([], [], 'b-', linewidth=2, label='Humidity')
        
        # Set title and labels with better font
        self.temp_ax.set_title('Temperature over Time', fontsize=12, pad=10)
        self.temp_ax.set_ylabel('Temperature (°C)', fontsize=10)
        self.temp_ax.grid(True, alpha=0.3)
        self.temp_ax.legend(loc='upper right', frameon=True)
        
        self.humid_ax.set_title('Humidity over Time', fontsize=12, pad=10)
        self.humid_ax.set_xlabel('Time', fontsize=10)
        self.humid_ax.set_ylabel('Humidity (%)', fontsize=10)
        self.humid_ax.grid(True, alpha=0.3)
        self.humid_ax.legend(loc='upper right', frameon=True)
        
        # Add zoom/pan toolbar if needed
        from matplotlib.backends.backend_tkagg import NavigationToolbar2Tk
        toolbar_frame = ttk.Frame(graph_frame)
        toolbar_frame.pack(fill='x')
        toolbar = NavigationToolbar2Tk(self.canvas, toolbar_frame)
        toolbar.update()
    
    def _setup_anomaly_tab(self):
        # Frame for anomalies
        anomaly_frame = ttk.Frame(self.anomaly_tab)
        anomaly_frame.pack(padx=10, pady=10, fill="both", expand=True)
        
        # Add heading for anomalies
        header_label = ttk.Label(anomaly_frame, text="Detected Anomalies", font=("Helvetica", 12, "bold"))
        header_label.pack(anchor="w", pady=(0, 10))
        
        # Create Treeview for anomalies with warning style
        self.anomaly_tree = ttk.Treeview(anomaly_frame, 
                                         columns=("Sensor ID", "Issue", "Value", "Timestamp"),
                                         bootstyle="danger")
        self.anomaly_tree.heading("#0", text="Index")
        self.anomaly_tree.heading("Sensor ID", text="Sensor ID")
        self.anomaly_tree.heading("Issue", text="Issue")
        self.anomaly_tree.heading("Value", text="Value")
        self.anomaly_tree.heading("Timestamp", text="Timestamp")
        
        self.anomaly_tree.column("#0", width=50, stretch=tk.NO)
        self.anomaly_tree.column("Sensor ID", width=100, stretch=tk.YES)
        self.anomaly_tree.column("Issue", width=150, stretch=tk.YES)
        self.anomaly_tree.column("Value", width=100, stretch=tk.YES)
        self.anomaly_tree.column("Timestamp", width=200, stretch=tk.YES)
        
        # Add scrollbar to the treeview
        scrollbar = ttk.Scrollbar(anomaly_frame, orient="vertical", command=self.anomaly_tree.yview)
        self.anomaly_tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.anomaly_tree.pack(fill="both", expand=True)
    
    def _setup_battery_tab(self):
        # Main container with padding
        battery_main_frame = ttk.Frame(self.battery_tab)
        battery_main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Top section - Current Status with improved style
        status_frame = ttk.Labelframe(battery_main_frame, text="Current Battery Status", 
                                     bootstyle="primary")
        status_frame.pack(fill="x", pady=10)
        
        # Battery level indicator - improved visual
        self.battery_canvas = tk.Canvas(status_frame, width=300, height=40, bg="#f8f9fa", 
                                       highlightthickness=0)
        self.battery_canvas.pack(side="top", pady=10)
        self.draw_battery_indicator(100)
        
        # Battery stats display with improved layout
        stats_frame = ttk.Frame(status_frame)
        stats_frame.pack(fill="x", pady=10)
        
        # Use grid with proper padding
        ttk.Label(stats_frame, text="Current Level:", font=("Helvetica", 10)).grid(
            row=0, column=0, sticky="w", padx=10, pady=3)
        self.battery_level_value = ttk.Label(stats_frame, text="100%", font=("Helvetica", 10, "bold"))
        self.battery_level_value.grid(row=0, column=1, sticky="w", pady=3)
        
        ttk.Label(stats_frame, text="Status:", font=("Helvetica", 10)).grid(
            row=1, column=0, sticky="w", padx=10, pady=3)
        self.battery_status_value = ttk.Label(stats_frame, text="Normal Operation", font=("Helvetica", 10, "bold"))
        self.battery_status_value.grid(row=1, column=1, sticky="w", pady=3)
        
        ttk.Label(stats_frame, text="Estimated Runtime:", font=("Helvetica", 10)).grid(
            row=2, column=0, sticky="w", padx=10, pady=3)
        self.runtime_value = ttk.Label(stats_frame, text="N/A", font=("Helvetica", 10, "bold"))
        self.runtime_value.grid(row=2, column=1, sticky="w", pady=3)
        
        # Middle section - Battery History Graph with improved design
        graph_frame = ttk.Labelframe(battery_main_frame, text="Battery Level History", 
                                    bootstyle="info")
        graph_frame.pack(fill="both", expand=True, pady=10)
        
        # Create more compact and cleaner figure
        self.battery_fig = Figure(figsize=(8, 3), dpi=100, tight_layout=True)
        self.battery_ax = self.battery_fig.add_subplot(111)
        self.battery_canvas_plot = FigureCanvasTkAgg(self.battery_fig, master=graph_frame)
        self.battery_canvas_plot.get_tk_widget().pack(fill="both", expand=True, padx=10, pady=10)
        
        # Improved plot styling
        self.battery_line, = self.battery_ax.plot([], [], color='#28a745', linewidth=2.5)
        self.battery_ax.set_title('Battery Level over Time', fontsize=12)
        self.battery_ax.set_ylabel('Battery (%)', fontsize=10)
        self.battery_ax.set_ylim(0, 100)
        self.battery_ax.grid(True, alpha=0.3)
        
        # Bottom section - Return to Base Simulation with improved style
        simulation_frame = ttk.Labelframe(battery_main_frame, text="Return to Base Status", 
                                         bootstyle="warning")
        simulation_frame.pack(fill="x", pady=10)
        
        # Progress bar with bootstyle
        self.return_progress = ttk.Progressbar(simulation_frame, orient="horizontal", 
                                              length=300, mode="determinate", 
                                              bootstyle="success-striped")
        self.return_progress.pack(pady=10)
        
        self.return_status = ttk.Label(simulation_frame, text="Not returning to base", 
                                      font=("Helvetica", 10))
        self.return_status.pack(pady=5)


        # Threshold Setting Section
        threshold_frame = ttk.Frame(self.battery_tab) # Or wherever you want this section
        threshold_frame.pack(pady=10)

        ttk.Label(threshold_frame, text="Set Low Battery Threshold (%):").pack(side="left", padx=5)

        # Using Spinbox for restricted numerical input
        self.threshold_spinbox = ttk.Spinbox(threshold_frame, from_=5, to=50, increment=1, width=5)
        self.threshold_spinbox.set(self.battery_manager.threshold) # Set initial value from BatteryManager
        self.threshold_spinbox.pack(side="left", padx=5)

        ttk.Button(threshold_frame, text="Apply", command=self.apply_threshold, bootstyle="secondary").pack(side="left", padx=5)

# You might also want a label to show the current applied threshold
        self.current_threshold_label = ttk.Label(threshold_frame, text=f"Current: {self.battery_manager.threshold}%")
        self.current_threshold_label.pack(side="left", padx=10)

    def draw_battery_indicator(self, level):
        """Draw a graphical battery indicator with improved design"""
        # Clear previous drawing
        self.battery_canvas.delete("all")
        
        # Create rounded rectangle function
        def create_rounded_rect(canvas, x1, y1, x2, y2, radius=10, **kwargs):
            points = [
                x1+radius, y1,
                x2-radius, y1,
                x2, y1,
                x2, y1+radius,
                x2, y2-radius,
                x2, y2,
                x2-radius, y2,
                x1+radius, y2,
                x1, y2,
                x1, y2-radius,
                x1, y1+radius,
                x1, y1
            ]
            return canvas.create_polygon(points, **kwargs, smooth=True)
        
        # Background rectangle (rounded)
        create_rounded_rect(self.battery_canvas, 10, 5, 280, 35, radius=8, 
                           outline="#dee2e6", fill="#f8f9fa", width=2)
        
        # Draw battery terminal
        self.battery_canvas.create_rectangle(280, 12, 290, 28, outline="#dee2e6", fill="#dee2e6")
        
        # Calculate fill width based on level
        fill_width = max(0, min(level, 100)) * 2.7  # Scale to fit
        
        # Choose color based on level
        if level <= 20:
            color = "#dc3545"  # Bootstrap danger color
        elif level <= 50:
            color = "#ffc107"  # Bootstrap warning color
        else:
            color = "#28a745"  # Bootstrap success color
        
        # Draw battery level with rounded corners if not full
        if fill_width < 270:
            create_rounded_rect(self.battery_canvas, 10, 5, 10 + fill_width, 35, radius=8, 
                              outline="", fill=color)
        else:
            create_rounded_rect(self.battery_canvas, 10, 5, 280, 35, radius=8, 
                              outline="", fill=color)
        
        # Add percentage text
        self.battery_canvas.create_text(150, 20, text=f"{level:.1f}%", 
                                       font=("Helvetica", 12, "bold"), 
                                       fill="#212529")  # Dark text for contrast
    
    def _setup_log_tab(self):
        # Create frame for log section
        log_frame = ttk.Frame(self.log_tab)
        log_frame.pack(padx=10, pady=10, fill="both", expand=True)
        
        # Add heading
        header_label = ttk.Label(log_frame, text="System Logs", font=("Helvetica", 12, "bold"))
        header_label.pack(anchor="w", pady=(0, 10))
        
        # Create scrolled text widget with bootstyle
        self.log_text = ScrolledText(log_frame, bootstyle="dark", autohide=True, wrap="word")
        self.log_text.pack(fill="both", expand=True)
    
    def _setup_battery_display(self):
        # Create status bar at the bottom with improved style
        status_frame = ttk.Frame(self.root, bootstyle="light")
        status_frame.pack(side="bottom", fill="x")
        
        # Add separator for cleaner look
        ttk.Separator(status_frame, orient="horizontal").pack(fill="x", pady=2)
        
        # Status bar content frame
        content_frame = ttk.Frame(status_frame)
        content_frame.pack(fill="x", pady=5)
        
        # Battery label with icon
        battery_frame = ttk.Frame(content_frame)
        battery_frame.pack(side="left", padx=10)
        
        battery_icon = "🔋"  # Simple battery icon
        ttk.Label(battery_frame, text=battery_icon, font=("Helvetica", 12)).pack(side="left")
        
        self.battery_label = ttk.Label(battery_frame, text="100%", font=("Helvetica", 10, "bold"))
        self.battery_label.pack(side="left", padx=5)
        
        # Battery status label
        self.battery_status = ttk.Label(content_frame, text="Status: Normal Operation", 
                                       font=("Helvetica", 10))
        self.battery_status.pack(side="left", padx=10)
        
        # Connection status with icon
        conn_frame = ttk.Frame(content_frame)
        conn_frame.pack(side="right", padx=10)
        
        conn_icon = "🔌"  # Simple plug icon
        ttk.Label(conn_frame, text=conn_icon, font=("Helvetica", 12)).pack(side="left")
        
        self.connection_status = ttk.Label(conn_frame, text="Disconnected", 
                                          font=("Helvetica", 10))
        self.connection_status.pack(side="left", padx=5)
    
    def _setup_alert_banner(self):
        """Create a hidden alert banner for battery warnings with improved style"""
        self.alert_frame = ttk.Frame(self.root, bootstyle="danger")
        self.alert_label = ttk.Label(self.alert_frame, text="", 
                                    bootstyle="inverse-danger",
                                    font=("Helvetica", 12, "bold"))
        self.alert_label.pack(fill="both", expand=True, padx=10, pady=5)
        # Alert is hidden by default
    
    def show_alert(self, message):
        """Show the alert banner with a message"""
        self.alert_label.config(text=message)
        self.alert_frame.pack(fill="x", before=self.tab_control)
    
    def hide_alert(self):
        """Hide the alert banner"""
        self.alert_frame.pack_forget()
    
    def update_table(self, sensor_data):
        """Update the data table with new sensor data"""
        # Get the count of existing items to generate a new index
        self.count += 1
        index = self.count
        
        # Insert new data
        self.data_tree.insert("", "end", text=str(index), 
                              values=(sensor_data["sensor_id"], 
                                     f"{sensor_data['temperature']:.2f}°C",
                                     f"{sensor_data['humidity']:.2f}%",
                                     sensor_data["timestamp"]))
        
        # Keep only the last 100 entries
        if index > 100:
            self.data_tree.delete(self.data_tree.get_children()[0])
        
       
        
        # Update plot data
        current_time = datetime.datetime.strptime(sensor_data["timestamp"], 
                                                 "%Y-%m-%dT%H:%M:%SZ").strftime("%H:%M:%S")
        self.timestamps.append(current_time)
        self.temps.append(sensor_data["temperature"])
        self.humids.append(sensor_data["humidity"])
        
        # Keep only the last 30 data points for cleaner plotting
        if len(self.timestamps) > 30:
            self.timestamps = self.timestamps[-30:]
            self.temps = self.temps[-30:]
            self.humids = self.humids[-30:]
        
        # Update the plot
        self._update_plot()
    
    def _update_plot(self):
        """Update the temperature and humidity plots with improved formatting"""
        if not self.timestamps:
            return
        
        # Update temperature plot
        self.temp_line.set_data(range(len(self.timestamps)), self.temps)
        self.temp_ax.relim()
        self.temp_ax.autoscale_view()
        
        # Improved x-ticks - show fewer labels for cleaner look
        n_ticks = min(5, len(self.timestamps))
        if n_ticks > 0:
            step = max(1, len(self.timestamps) // n_ticks)
            tick_indices = range(0, len(self.timestamps), step)
            self.temp_ax.set_xticks(tick_indices)
            self.temp_ax.set_xticklabels([self.timestamps[i] for i in tick_indices], rotation=30)
        
        # Update humidity plot
        self.humid_line.set_data(range(len(self.timestamps)), self.humids)
        self.humid_ax.relim()
        self.humid_ax.autoscale_view()
        
        # Improved x-ticks for humidity plot
        if n_ticks > 0:
            self.humid_ax.set_xticks(tick_indices)
            self.humid_ax.set_xticklabels([self.timestamps[i] for i in tick_indices], rotation=30)
        
        # Update display
        self.fig.tight_layout()
        self.canvas.draw()
    
    def highlight_anomalies(self, anomalies):
        """Update the anomalies tab with new anomalous data"""
        # Clear existing anomalies
        for item in self.anomaly_tree.get_children():
            self.anomaly_tree.delete(item)
        
        # Add anomalies to the tree
        for i, anomaly in enumerate(anomalies):
            self.anomaly_tree.insert("", "end", text=str(i+1), 
                                    values=(anomaly["sensor_id"],
                                           anomaly["issue"],
                                           f"{anomaly['value']:.2f}",
                                           anomaly["timestamp"]))
            
    
    def display_battery(self, battery_status):
        """Update the battery display"""
        level = battery_status["level"]
        current_time = datetime.datetime.now().strftime("%H:%M:%S")
        
        # Update status bar at bottom
        self.battery_label.config(text=f"{level:.1f}%")
        
        # Update status based on level - use bootstyle constants
        if level < 20:
            self.battery_label.config(bootstyle="danger")
        elif level < 50:
            self.battery_label.config(bootstyle="warning")
        else:
            self.battery_label.config(bootstyle="success")
        
        # Update battery tab - always show the actual battery level
        self.draw_battery_indicator(level)
        self.battery_level_value.config(text=f"{level:.1f}%")
        
        # Update battery history data
        self.battery_levels.append(level)
        self.battery_timestamps.append(current_time)
        
        # Keep only last 30 points for cleaner display
        if len(self.battery_levels) > 30:
            self.battery_levels = self.battery_levels[-30:]
            self.battery_timestamps = self.battery_timestamps[-30:]
        
        # Update battery history plot
        self._update_battery_plot()
        
        # Calculate estimated runtime
        if not battery_status["returning_to_base"] and not battery_status["charging"]:
            if len(self.battery_levels) >= 2:
                # Simple linear projection
                rate_of_change = (self.battery_levels[-1] - self.battery_levels[0]) / len(self.battery_levels)
                if rate_of_change < 0:  # If battery is decreasing
                    time_remaining = abs(level / rate_of_change) if rate_of_change != 0 else float('inf')
                    minutes = int(time_remaining // 60)
                    seconds = int(time_remaining % 60)
                    self.runtime_value.config(text=f"{minutes}m {seconds}s")
                else:
                    self.runtime_value.config(text="N/A")
            else:
                self.runtime_value.config(text="Calculating...")
        else:
            self.runtime_value.config(text="N/A")
        
        # Update status text and return to base progress with better styling
        if battery_status["returning_to_base"]:
            if battery_status["charging"]:
                # Display charging status with time left
                status_text = "Charging at Base"
                self.battery_status.config(text=status_text, bootstyle="warning")
                self.battery_status_value.config(text=status_text, bootstyle="warning")
                
                # Make sure to use the dedicated charging progress field, not battery level
                if "charge_time_left" in battery_status and "charge_progress" in battery_status:
                    time_left = battery_status["charge_time_left"]
                    charge_percent = battery_status["charge_progress"]
                    
                    # Configure progress bar for charging progress display
                    self.return_progress.configure(bootstyle="warning-striped")
                    self.return_progress["value"] = charge_percent
                    
                    # Show charging progress separate from battery level
                    self.return_status.config(
                        text=f"Charging process: {charge_percent:.1f}% complete ({time_left:.1f}s remaining)"
                    )
                else:
                    # Default if we don't have charging progress info
                    self.return_progress.configure(bootstyle="warning-striped")
                    self.return_progress["value"] = 0
                    self.return_status.config(text="Charging in progress... (awaiting data)")
                
                # Show alert for charging
                self.show_alert("⚡ CHARGING AT BASE ⚡")
                self.alert_frame.configure(bootstyle="warning")
                self.alert_label.configure(bootstyle="inverse-warning")
                
            else:
                # Display returning to base status with progress
                status_text = "Returning to Base"
                self.battery_status.config(text=status_text, bootstyle="danger")
                self.battery_status_value.config(text=status_text, bootstyle="danger")
                
                # Use return progress data if available
                if "return_time_left" in battery_status and "return_progress" in battery_status:
                    time_left = battery_status["return_time_left"]
                    return_percent = battery_status["return_progress"]
                    
                    # Configure progress bar for return journey display
                    self.return_progress.configure(bootstyle="danger-striped")
                    self.return_progress["value"] = return_percent
                    
                    self.return_status.config(
                        text=f"Return journey: {return_percent:.1f}% complete ({time_left:.1f}s remaining)"
                    )
                else:
                    # Default if we don't have return progress info
                    self.return_progress.configure(bootstyle="danger-striped")
                    self.return_progress["value"] = 0
                    self.return_status.config(text="Returning to base... (awaiting data)")
                
                # Show alert for returning
                self.show_alert("🔋 LOW BATTERY - RETURNING TO BASE 🔋")
                self.alert_frame.configure(bootstyle="danger")
                self.alert_label.configure(bootstyle="inverse-danger")
            
        else:
            # Normal operation status
            status_text = "Normal Operation"
            self.battery_status.config(text=status_text, bootstyle="success")
            self.battery_status_value.config(text=status_text, bootstyle="success")
            
            # Reset progress bar in normal operation
            self.return_progress.configure(bootstyle="success-striped")
            self.return_progress["value"] = 0
            self.return_status.config(text="Not returning to base")
            
            # Hide alert in normal operation
            self.hide_alert()
    
    def _update_battery_plot(self):
        """Update the battery history plot with improved styling"""
        if not self.battery_levels:
            return

        # --- Step 1: Clear the previous threshold line if it exists ---
        if hasattr(self, 'threshold_line') and self.threshold_line is not None:
             try:
                 self.threshold_line.remove() # Remove the old line from the axes
                 # You can optionally delete the attribute if you want to be tidy,
                 # but removing from the axes is the key part.
                 # del self.threshold_line
             except ValueError:
                 # This can happen if the line was already removed for some reason.
                 # It's generally safe to ignore, but you could log a warning.
                 pass


        # --- Step 2: Update battery history line data (your existing code) ---
        self.battery_line.set_data(range(len(self.battery_levels)), self.battery_levels)
        self.battery_ax.relim()
        self.battery_ax.autoscale_view()

        # Set x-ticks - fewer labels for cleaner appearance
        n_ticks = min(5, len(self.battery_timestamps))
        if n_ticks > 0:
            step = max(1, len(self.battery_timestamps) // n_ticks)
            tick_indices = range(0, len(self.battery_timestamps), step)
            self.battery_ax.set_xticks(tick_indices)
            self.battery_ax.set_xticklabels([self.battery_timestamps[i] for i in tick_indices], rotation=30)
        else:
            self.battery_ax.set_xticks([]) # Clear ticks if no data

        # Set y range from 0 to max of 100 or slightly above current max
        y_max = max(100, max(self.battery_levels) * 1.1 if self.battery_levels else 100)
        self.battery_ax.set_ylim(0, y_max)

        # --- Step 3: Add the new threshold line using the current threshold ---
        # This draws a new line at the correct y-position
        # Ensure self.battery_manager is accessible (which should be fixed now)
        try:
            self.threshold_line = self.battery_ax.axhline(y=self.battery_manager.threshold,
                                                          color='#dc3545', linestyle='--',
                                                          alpha=0.7, linewidth=1.5, label='Threshold') # Added label for legend
            # Optional: Add a legend to show the threshold line
            # self.battery_ax.legend() # You might want a better place for legend setup

        except AttributeError:
            print("[PLOT ERROR] battery_manager or its threshold not available when trying to draw threshold line.")
            self.threshold_line = None # Ensure the attribute exists even on error

        # Update layout and display
        self.battery_fig.tight_layout()
        self.battery_canvas_plot.draw()
    
    def update_connection_status(self, connected):
        """Update the server connection status"""
        if connected:
            self.connection_status.config(text="Connected", bootstyle="success")
        else:
            self.connection_status.config(text="Disconnected", bootstyle="danger")
    
    def log_panel(self, message):
        """Add a message to the log panel"""
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Color-code log messages by type
        if "ERROR" in message:
            tag = "error"
            self.log_text.tag_configure("error", foreground="#dc3545")
        elif "WARNING" in message:
            tag = "warning"
            self.log_text.tag_configure("warning", foreground="#ffc107")
        elif "SUCCESS" in message:
            tag = "success"
            self.log_text.tag_configure("success", foreground="#28a745")
        else:
            tag = None
        
        # Add formatted log entry
        log_entry = f"[{timestamp}] {message}\n"
        self.log_text.insert(tk.END, log_entry, tag)
        

    # Add these helper methods to DroneGUI class

    def set_connection_manager(self, connection_manager, edge_processor):
        """Set the connection manager for node operations"""
        self.connection_manager = connection_manager
        self.edge_processor = edge_processor



    def _on_toggle_data_stream_clicked(self):
        """Handles the Pause/Resume Data Stream button click."""
        if self.drone_server:
            is_active = self.drone_server.toggle_data_stream()
            if is_active:
                self.toggle_stream_button.config(text="Pause Data Stream", bootstyle="warning")
                self.log_panel("INFO: Data stream resumed.")
            else:
                self.toggle_stream_button.config(text="Resume Data Stream", bootstyle="success")
                self.log_panel("INFO: Data stream paused.")
        else:
            self.log_panel("ERROR: Drone server instance not available.")




    def _on_disconnect_node_clicked(self):
        """Handles the Disconnect Node button click."""
        selection = self.nodes_tree.selection()
        if not selection:
            self.log_panel("WARNING: No node selected to disconnect.")
            return

        node_id = self.nodes_tree.item(selection[0], "text") # Get ID from first column

        if self.connection_manager:
            self.log_panel(f"INFO: Attempting to disconnect node: {node_id}")
            success = self.connection_manager.disconnect_node(node_id)
            if success:
                self.log_panel(f"SUCCESS: Disconnection command sent to node {node_id}.")
                # Optionally remove from local data cache if you maintain one that mirrors connections
                if node_id in self.node_data:
                    del self.node_data[node_id]
                self.clear_node_selection() # Clear details panel and disable button
                self.update_nodes()         # Refresh the tree view
            else:
                self.log_panel(f"ERROR: Failed to disconnect node {node_id}. It might be already disconnected or not found.")
        else:
            self.log_panel("ERROR: Connection manager not available for node disconnection.")
        
        # Ensure button is disabled after action attempt
        self.disconnect_node_button.config(state="disabled")

    def on_node_selected(self, event):
        """Handle node selection in the treeview"""
        selection = self.nodes_tree.selection()
        if selection:
            node_id = self.nodes_tree.item(selection[0], "text") # Get ID from first column
            self.update_node_details(node_id)
            # --- MODIFIED: Enable disconnect button ---
            if self.connection_manager: # Only enable if manager is available
                 self.disconnect_node_button.config(state="normal")
            else:
                 self.disconnect_node_button.config(state="disabled")
        else:
            self.clear_node_selection()

    def update_node_details(self, node_id):
        """Update the node details panel for selected node"""
        if node_id not in self.node_data:
            self.node_id_value.config(text=node_id)
            self.node_status_value.config(text="Unknown")
            return
    
    # Get node data
        node_info = self.node_data[node_id]
    
    # Update labels
        self.node_id_value.config(text=node_id)
        self.node_status_value.config(text=node_info.get("status", "Unknown"))
        self.node_lastseen_value.config(text=node_info.get("last_seen", "N/A"))
        self.node_datacount_value.config(text=str(node_info.get("data_count", 0)))
    
    # Calculate temperature range
        if "min_temp" in node_info and "max_temp" in node_info:
            temp_range = f"{node_info['min_temp']:.1f}°C - {node_info['max_temp']:.1f}°C"
            self.node_temprange_value.config(text=temp_range)
    
    # Calculate humidity range
        if "min_humid" in node_info and "max_humid" in node_info:
            humid_range = f"{node_info['min_humid']:.1f}% - {node_info['max_humid']:.1f}%"
            self.node_humidrange_value.config(text=humid_range)
    
    # Count anomalies for this node
        anomaly_count = 0
        for anomaly in self.edge_processor.get_anomalies():
            if anomaly["sensor_id"] == node_id:
                anomaly_count += 1
        self.node_anomalies_value.config(text=str(anomaly_count))
    
    # Latest reading
        if "latest_reading" in node_info:
            latest = node_info["latest_reading"]
            self.latest_temp_value.config(text=f"{latest['temperature']:.1f}°C")
            self.latest_humid_value.config(text=f"{latest['humidity']:.1f}%")
            self.latest_time_value.config(text=latest["timestamp"])
        
        # Set color based on anomaly status
            if latest["temperature"] > self.edge_processor.temp_threshold_high or \
                latest["temperature"] < self.edge_processor.temp_threshold_low:
                self.latest_temp_value.config(bootstyle="danger")
            else:
                self.latest_temp_value.config(bootstyle="success")
            
            if latest["humidity"] > self.edge_processor.humidity_threshold_high or \
                latest["humidity"] < self.edge_processor.humidity_threshold_low:
                self.latest_humid_value.config(bootstyle="danger")
            else:
                self.latest_humid_value.config(bootstyle="success")

    def update_nodes(self):
        """Update the nodes status tab with current data"""
        # Skip if necessary references aren't set yet
        if not hasattr(self, 'edge_processor') or not self.edge_processor:
            return
        
    # Get all readings from edge processor
        readings = self.edge_processor.get_readings()
    
    # Process readings to update node data
        now = datetime.datetime.now()
    
        for sensor_id, sensor_readings in readings.items():
            if not sensor_readings:
                continue
            
        # Create entry for new node
            if sensor_id not in self.node_data:
                self.node_data[sensor_id] = {
                    "status": "Connected",
                    "data_count": 0,
                    "min_temp": float('inf'),
                    "max_temp": float('-inf'),
                    "min_humid": float('inf'),
                    "max_humid": float('-inf')
                }
        
        # Update node data
            latest_reading = sensor_readings[-1]
            self.node_data[sensor_id]["latest_reading"] = latest_reading
            self.node_data[sensor_id]["last_seen"] = latest_reading["timestamp"]
            self.node_data[sensor_id]["data_count"] = len(sensor_readings)
        
        # Update min/max values
            for reading in sensor_readings:
                temp = reading["temperature"]
                humid = reading["humidity"]
            
                self.node_data[sensor_id]["min_temp"] = min(self.node_data[sensor_id]["min_temp"], temp)
                self.node_data[sensor_id]["max_temp"] = max(self.node_data[sensor_id]["max_temp"], temp)
                self.node_data[sensor_id]["min_humid"] = min(self.node_data[sensor_id]["min_humid"], humid)
                self.node_data[sensor_id]["max_humid"] = max(self.node_data[sensor_id]["max_humid"], humid)
    
    # Update treeview
    # First, save current selection
        selected_items = self.nodes_tree.selection()
        selected_ids = [self.nodes_tree.item(item, "text") for item in selected_items]
    
    # Clear treeview
        for item in self.nodes_tree.get_children():
            self.nodes_tree.delete(item)
    
    # Add nodes to treeview
        for node_id, node_info in self.node_data.items():
        # Format last seen time
            last_seen = node_info.get("last_seen", "N/A")
        
        # Check if the node is still connected
            is_connected = False
            if self.connection_manager:
                is_connected = node_id in self.connection_manager.node_to_addr and \
                           self.connection_manager.node_to_addr[node_id] in self.connection_manager.active_connections
        
        # Update status
            status = "Connected" if is_connected else "Disconnected"
            node_info["status"] = status
        
        # Insert into treeview with appropriate status color
            item = self.nodes_tree.insert("", "end", text=node_id, 
                                    values=(status, last_seen),
                                    tags=(status.lower(),))
        
        # Apply color to status
            if status == "Connected":
                self.nodes_tree.tag_configure("connected", foreground="#28a745")
            else:
                self.nodes_tree.tag_configure("disconnected", foreground="#dc3545")
    
    # Restore selection if items still exist
        for node_id in selected_ids:
            for item in self.nodes_tree.get_children():
                if self.nodes_tree.item(item, "text") == node_id:
                    self.nodes_tree.selection_add(item)
                    break
    
    # Update details if a node is selected
        if self.nodes_tree.selection():
            selected_node = self.nodes_tree.item(self.nodes_tree.selection()[0], "text")
            self.update_node_details(selected_node)

    def refresh_nodes(self):
        """Refresh the nodes list"""
        self.update_nodes()
        self.log_panel("SUCCESS: Refreshed nodes list")

    def clear_node_selection(self):
        """Clear the selected node and reset details panel."""
        current_selection = self.nodes_tree.selection()
        if current_selection: # Check if there's a selection to remove
            self.nodes_tree.selection_remove(current_selection)
        
        # Reset detail fields
        self.node_id_value.config(text="Select a node")
        self.node_status_value.config(text="N/A")
        self.node_lastseen_value.config(text="N/A")
        self.node_datacount_value.config(text="N/A")
        self.node_temprange_value.config(text="N/A")
        self.node_humidrange_value.config(text="N/A")
        self.node_anomalies_value.config(text="N/A")
        
        self.latest_temp_value.config(text="N/A", bootstyle="default") # Reset style
        self.latest_humid_value.config(text="N/A", bootstyle="default") # Reset style
        self.latest_time_value.config(text="N/A")

        # --- MODIFIED: Disable disconnect button ---
        if hasattr(self, 'disconnect_node_button'): # Check if button exists
            self.disconnect_node_button.config(state="disabled")
    
    

    
    
class DroneServer:
    """Main drone server class that manages sensor connections, data processing, and server communication"""
    
    def __init__(self, listen_ip="127.0.0.1", listen_port=3400, 
                 server_ip="127.0.0.1", server_port=3500,
                 drone_id="drone_alpha"):
        

        
        
        # Initialize components
        self.root = tk.Tk()
        
        self.data_stream_active = True
        self.edge_processor = EdgeProcessor()
        self.battery_manager = BatteryManager()
        self.gui = DroneGUI(self.root,self.battery_manager)
        self.gui.set_drone_server(self)
        self.drone_client = DroneClient(server_ip, server_port, drone_id)
        
        # Server settings
        self.listen_ip = listen_ip
        self.listen_port = listen_port
        self.drone_id = drone_id
        
        # Thread control
        self.server_running = False
        self.data_queue = Queue(maxsize=100)  # Buffer for incoming sensor data
        self.active_connections = {}  # Track active sensor connections
        self.connection_lock = threading.Lock()

        self.connection_manager = ConnectionManager(
        self.active_connections, 
        self.connection_lock,
        logger=self.log
        )

         # After initializing connection_manager
        self.gui.set_connection_manager(self.connection_manager, self.edge_processor)

        
        
        # Start the server
        self.log("Drone server initializing...")
        self.server_thread = threading.Thread(target=self._start_server)
        self.processor_thread = threading.Thread(target=self._process_data)
        self.battery_thread = threading.Thread(target=self._manage_battery)
        self.server_comm_thread = threading.Thread(target=self._communicate_with_server)
        self.nodes_update_thread = threading.Thread(target=self._update_nodes_status)


    def toggle_data_stream(self):
        """Toggles the data stream processing on or off."""
        self.data_stream_active = not self.data_stream_active
        status = "resumed" if self.data_stream_active else "paused"
        self.log(f"Data stream has been {status} by GUI request.")
        return self.data_stream_active

    def _update_nodes_status(self):
        """Thread to periodically update node status information"""
        while self.server_running:
            try:
            # Update nodes tab (only if not returning to base)
                battery_status = self.battery_manager.check_status()
                if not battery_status["returning_to_base"]:
                # Use after method to safely update UI from another thread
                    self.root.after(0, self.gui.update_nodes)
            
            # Refresh nodes list periodically
                if hasattr(self, 'refresh_counter'):
                    self.refresh_counter += 1
                # Refresh every 10 iterations (10 seconds if sleep is 1s)
                    if self.refresh_counter >= 10:
                        self.root.after(0, self.gui.refresh_nodes)
                        self.refresh_counter = 0
                else:
                    self.refresh_counter = 0
                
            except Exception as e:
                self.log(f"Error updating nodes status: {e}")
        
            time.sleep(1)  # Update every second
    
    def start(self):
        """Start all threads and the main GUI loop"""
        self.server_running = True
        
        self.server_thread.daemon = True
        self.server_thread.start()
        
        self.processor_thread.daemon = True
        self.processor_thread.start()
        
        self.battery_thread.daemon = True
        self.battery_thread.start()
        
        self.server_comm_thread.daemon = True
        self.server_comm_thread.start()

        # Start the nodes update thread
        self.nodes_update_thread.daemon = True
        self.nodes_update_thread.start()
        
        self.log("Drone server started and ready for sensor connections")
        self.root.protocol("WM_DELETE_WINDOW", self.stop)  # Handle window close
        self.root.mainloop()
    
    def stop(self):
        """Stop all threads and close the server"""
        self.server_running = False
        
        # Close all active connections
        with self.connection_lock:
            for conn in self.active_connections.values():
                if conn:
                    try:
                        conn.close()
                    except:
                        pass
            self.active_connections.clear()
        
        # Close server socket if exists
        if hasattr(self, 'server_socket') and self.server_socket:
            self.server_socket.close()
        
        self.log("Server shutting down")
        self.root.destroy()
    
    def log(self, message):
        """Log a message to GUI and console"""
        print(f"[DRONE] {message}")
        if hasattr(self, 'gui'):
            self.gui.log_panel(message)
    
    def _start_server(self):
        """Start the TCP server to listen for sensor connections"""
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.listen_ip, self.listen_port))
            self.server_socket.listen(5)
            self.log(f"Server listening on {self.listen_ip}:{self.listen_port}")
            
            while self.server_running:
                # Set a timeout so we can check server_running periodically
                self.server_socket.settimeout(1.0)
                
                try:
                    client_socket, addr = self.server_socket.accept()
                    # Check if we're returning to base before accepting new connections
                    battery_status = self.battery_manager.check_status()
                    if battery_status["returning_to_base"]:
                        self.log(f"Connection from {addr} rejected - drone returning to base")
                        client_socket.close()
                        continue
                    
                    # Accept the connection and start a new thread to handle it
                    self.log(f"New connection from {addr}")
                    client_thread = threading.Thread(target=self._handle_client, 
                                                    args=(client_socket, addr))
                    client_thread.daemon = True
                    client_thread.start()
                
                except socket.timeout:
                    # This is expected, just continue the loop
                    continue
                except Exception as e:
                    if self.server_running:  # Only log if we're not shutting down
                        self.log(f"Error accepting connection: {e}")
        
        except Exception as e:
            self.log(f"Server error: {e}")
        finally:
            if hasattr(self, 'server_socket'):
                self.server_socket.close()
    
    def _handle_client(self, client_socket, addr):
        """Handle communication with a connected sensor node"""
        sensor_id = None
        try:
            # Add to active connections
            with self.connection_lock:
                self.active_connections[addr] = client_socket
            
            self.log(f"Handling client {addr}")
            client_socket.settimeout(60)  # 60 second timeout
            
            # Receive data from the client
            buffer = ""
            while self.server_running:
                # Check if we should disconnect due to battery
                battery_status = self.battery_manager.check_status()
                if battery_status["returning_to_base"]:
                    self.log(f"Disconnecting {addr} - drone returning to base")
                    break
                
                data = client_socket.recv(4096).decode('utf-8')
                if not data:
                    self.log(f"Client {addr} disconnected")
                    break
                
                buffer += data
                
                # Process complete JSON objects
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    try:
                        sensor_data = json.loads(line)
                        current_sensor_id = sensor_data.get('sensor_id')

                        if current_sensor_id and (not sensor_id or sensor_id != current_sensor_id):
                            sensor_id = current_sensor_id
                            self.connection_manager.register_node(sensor_id, addr)


                        if not self.data_stream_active:
                        # Optional: Uncomment if you want verbose logging of skipped data
                            self.log(f"Data stream paused. Ignoring data from sensor {sensor_id or 'Unknown'}")
                            continue  # S
                    
                        self.log(f"Received data from sensor {sensor_id}")

                        
                        
                        # Add to processing queue
                        try:
                            self.data_queue.put(sensor_data, block=False)
                        except Full:
                            self.log("Warning: Data queue full, dropping sensor data")
                    except json.JSONDecodeError:
                        self.log(f"Error: Invalid JSON from {addr}")
                        continue
        
        except socket.timeout:
            self.log(f"Connection to {addr} timed out")
        except ConnectionResetError:
            self.log(f"Connection to {addr} reset by peer")
        except Exception as e:
            self.log(f"Error handling client {addr}: {e}")
        finally:
            # Clean up the connection
            client_socket.close()
            with self.connection_lock:
                if addr in self.active_connections:
                    del self.active_connections[addr]
            self.log(f"Connection to {addr} closed")
    
    def _process_data(self):
        """Process sensor data from the queue"""
        while self.server_running:
            try:
                # Check if we should be processing data
                battery_status = self.battery_manager.check_status()
                if battery_status["returning_to_base"]:
                    time.sleep(1)
                    continue
                
                # Get data from queue with timeout to allow checking server_running
                try:
                    sensor_data = self.data_queue.get(timeout=1)
                except:
                    continue
                
                # Update GUI with new data
                self.root.after(0, self.gui.update_table, sensor_data)
                
                # Process data
                self.edge_processor.update_readings(sensor_data)
                
                # Update anomalies display
                anomalies = self.edge_processor.get_anomalies()
                self.root.after(0, self.gui.highlight_anomalies, anomalies)
                
                # Mark task as done
                self.data_queue.task_done()
            
            except Exception as e:
                self.log(f"Error processing data: {e}")
                time.sleep(1)
    
    def _manage_battery(self):
        """Manage battery simulation"""
        last_state = {"returning_to_base": False, "charging": False}
        
        while self.server_running:
            # Simulate battery drain or charging
            if last_state["returning_to_base"]:
                self.battery_manager.charge()
            else:
                #print(f"[DEBUG _manage_battery] Battery level: {self.battery_manager.level:.1f}%, CONSUME threshold: {self.battery_manager.threshold:.1f}%")
                returning = self.battery_manager.consume()
                if returning:
                    self.log("Battery low! Drone returning to base.")
            
            # Get current battery status
            battery_status = self.battery_manager.check_status()
            
            # Update GUI with battery status
            self.root.after(0, self.gui.display_battery, battery_status)
            
            # Handle connection management based on battery status
            if battery_status["returning_to_base"] and not last_state["returning_to_base"]:
                # Just started returning to base
                self.log(f"Drone is returning to base. Estimated time: {battery_status.get('return_time_left', '?')} seconds")
                
                # Close all connections when returning to base
                with self.connection_lock:
                    for addr, conn in list(self.active_connections.items()):
                        if conn:
                            try:
                                conn.close()
                                self.log(f"Closed connection to {addr} due to low battery")
                            except:
                                pass
                    self.active_connections.clear()
            
            # Log state transitions
            if battery_status["charging"] and not last_state["charging"]:
                self.log("Drone has reached the base and started charging")
            
            if not battery_status["returning_to_base"] and last_state["returning_to_base"]:
                self.log("Battery charged to sufficient level. Resuming normal operations.")
            
            # Update last state
            last_state = {
                "returning_to_base": battery_status["returning_to_base"],
                "charging": battery_status["charging"]
            }
            
            time.sleep(0.1)  # Update more frequently for smoother simulation
    
    def _communicate_with_server(self):
        """Periodically send data to the central server"""
        while self.server_running:
            try:
                # Get battery status
                battery_status = self.battery_manager.check_status()
                
                # Determine drone status
                drone_status = "normal"
                if battery_status["charging"]:
                    drone_status = "charging"
                elif battery_status["returning_to_base"]:
                    drone_status = "returning_to_base"
                else:
                    drone_status = "normal"

                # Always compute averages and get anomalies, even when returning to base
                avg_temp, avg_humidity = self.edge_processor.compute_averages()
                anomalies = self.edge_processor.get_anomalies()                
                
                # Send data to server
                success = self.drone_client.send_to_server(
                    avg_temp, avg_humidity, anomalies, battery_status["level"], status=drone_status
                )
                
                # Update connection status in GUI
                self.root.after(0, self.gui.update_connection_status, success)
                
                if success:
                    self.log(f"Data sent to central server successfully (Status: {drone_status})")
                else:
                    self.log("Failed to send data to central server")
                
                time.sleep(5)  # Send data every 5 seconds
                drone_status = "normal"  # Reset status after sending
            
            except Exception as e:
                self.log(f"Error communicating with server: {e}")
                time.sleep(5)

class ConnectionManager:
    """Manages connections to sensor nodes with ability to disconnect specific nodes"""
    
    def __init__(self, active_connections, connection_lock, logger=None):
        """Initialize the connection manager
        
        Args:
            active_connections: Dictionary of active connections {addr: socket}
            connection_lock: Threading lock for safe access to connections
            logger: Optional function for logging
        """
        self.active_connections = active_connections
        self.connection_lock = connection_lock
        self.logger = logger or print
        self.node_to_addr = {}  # Map sensor_id to address
    
    def register_node(self, sensor_id, addr):
        """Register a node ID with its connection address"""
        with self.connection_lock:
            self.node_to_addr[sensor_id] = addr
            self.logger(f"Registered node {sensor_id} at {addr}")
    
    def disconnect_node(self, sensor_id):
        """Disconnect a specific node by sensor ID
        
        Returns:
            bool: True if successfully disconnected, False otherwise
        """
        with self.connection_lock:
            # Find the address for this sensor ID
            addr = self.node_to_addr.get(sensor_id)
            if not addr:
                self.logger(f"Cannot disconnect node {sensor_id}: address not found")
                return False
            
            # Check if the connection is still active
            if addr not in self.active_connections:
                self.logger(f"Cannot disconnect node {sensor_id}: connection not active")
                return False
            
            # Get the socket
            conn = self.active_connections.get(addr)
            if not conn:
                self.logger(f"Cannot disconnect node {sensor_id}: socket not found")
                return False
            
            # Close the connection
            try:
                conn.close()
                del self.active_connections[addr]
                self.logger(f"Disconnected node {sensor_id} at {addr}")
                return True
            except Exception as e:
                self.logger(f"Error disconnecting node {sensor_id}: {e}")
                return False
            
if __name__ == "__main__":
    # Example usage:
    drone_server = DroneServer(
        listen_ip="127.0.0.1",
        listen_port=3400,
        server_ip="127.0.0.1",
        server_port=3500,
        drone_id="drone_alpha"
    )
    drone_server.start()