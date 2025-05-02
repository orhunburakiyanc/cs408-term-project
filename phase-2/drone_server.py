import socket
import threading
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
            
            # Keep only the last window_size readings
            if len(self.readings[sensor_id]) > self.window_size:
                self.readings[sensor_id] = self.readings[sensor_id][-self.window_size:]
            
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
        
        # Add anomaly if found
        if anomaly:
            self.anomalies.append(anomaly)
            # Keep only recent anomalies (last 50)
            if len(self.anomalies) > 50:
                self.anomalies = self.anomalies[-50:]
    
    def compute_averages(self):
        """Compute average temperature and humidity across all sensors"""
        with self.lock:
            all_temps = []
            all_humidities = []
            
            for sensor_id, readings in self.readings.items():
                for reading in readings:
                    all_temps.append(reading["temperature"])
                    all_humidities.append(reading["humidity"])
            
            avg_temp = sum(all_temps) / len(all_temps) if all_temps else 0
            avg_humidity = sum(all_humidities) / len(all_humidities) if all_humidities else 0
            
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
        self.time_to_charge = time_to_charge  # estimated seconds for full charge
        self.lock = threading.Lock()
    
    def consume(self):
        """Simulate battery consumption"""
        with self.lock:
            if not self.charging and not self.returning_to_base:
                self.level -= self.consumption_rate
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
                    print(f"[BATTERY] Arrived at base after {time_elapsed:.1f} seconds, starting to charge")
                    return
            
            # If we're charging
            if self.charging and self.level < 100:
                # Calculate charge increase based on time elapsed since last check
                if not hasattr(self, 'last_charge_time'):
                    self.last_charge_time = current_time
                
                time_elapsed = current_time - self.last_charge_time
                self.last_charge_time = current_time
                
                # Calculate charge based on time elapsed and charging rate
                # Charging rate is percent per second
                charge_increase = time_elapsed * self.charging_rate
                self.level = min(100, self.level + charge_increase)
                
                # Calculate and display estimated time remaining
                if self.level < 80:
                    percent_remaining = 80 - self.level
                    time_remaining = percent_remaining / self.charging_rate
                    print(f"[BATTERY] Charging: {self.level:.1f}%, estimated time to 80%: {time_remaining:.1f} seconds")
                
                # Once charged enough, allow operations to continue
                if self.level >= 80:  # Charge to 80% before resuming operations
                    total_charge_time = current_time - self.charging_start_time
                    self.returning_to_base = False
                    self.charging = False
                    self.returning_start_time = None
                    self.charging_start_time = None
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
            
            if self.charging and self.charging_start_time:
                elapsed = time.time() - self.charging_start_time
                percent_to_charge = 80 - max(self.threshold, self.level)  # How much we need to charge
                total_expected_time = (percent_to_charge / self.charging_rate)
                status["charge_progress"] = min(100, (elapsed / total_expected_time) * 100)
                status["charge_time_left"] = max(0, total_expected_time - elapsed)
            
            return status


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
    
    def send_to_server(self, avg_temp, avg_humidity, anomalies, battery_level, status="normal"):
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
    
    def __init__(self, root):
        # Initialize with ttkbootstrap style
        self.root = root
        self.root.title("Drone Edge Computing Unit")
        self.root.geometry("1000x800")
        
        # Create tabbed interface with modified style
        self.tab_control = ttk.Notebook(root)
        
        # Create tabs
        self.data_tab = ttk.Frame(self.tab_control)
        self.charts_tab = ttk.Frame(self.tab_control)
        self.anomaly_tab = ttk.Frame(self.tab_control)
        self.battery_tab = ttk.Frame(self.tab_control) 
        self.log_tab = ttk.Frame(self.tab_control)
        
        self.tab_control.add(self.data_tab, text="Data Stream")
        self.tab_control.add(self.charts_tab, text="Charts")
        self.tab_control.add(self.anomaly_tab, text="Anomalies")
        self.tab_control.add(self.battery_tab, text="Battery Status")
        self.tab_control.add(self.log_tab, text="Logs")
        self.tab_control.pack(expand=1, fill="both")
        
        # Setting up the tabs
        self._setup_data_tab()
        self._setup_charts_tab()
        self._setup_anomaly_tab()
        self._setup_battery_tab()
        self._setup_log_tab()
        
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
        index = len(self.data_tree.get_children()) + 1
        
        # Insert new data
        self.data_tree.insert("", "end", text=str(index), 
                              values=(sensor_data["sensor_id"], 
                                     f"{sensor_data['temperature']:.2f}°C",
                                     f"{sensor_data['humidity']:.2f}%",
                                     sensor_data["timestamp"]))
        
        # Keep only the last 100 entries
        if index > 100:
            self.data_tree.delete(self.data_tree.get_children()[0])
        
        # Auto-scroll to the bottom
        self.data_tree.yview_moveto(1)
        
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
        
        # Update data
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
        
        # Set y range from 0 to max of 100 or slightly above current max
        y_max = max(100, max(self.battery_levels) * 1.1) if self.battery_levels else 100
        self.battery_ax.set_ylim(0, y_max)
        
        # Add threshold line with improved styling
        if not hasattr(self, 'threshold_line'):
            self.threshold_line = self.battery_ax.axhline(y=20, color='#dc3545', linestyle='--', 
                                                        alpha=0.7, linewidth=1.5)
        
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
        self.log_text.see(tk.END)  # Auto-scroll to the latest log

class DroneServer:
    """Main drone server class that manages sensor connections, data processing, and server communication"""
    
    def __init__(self, listen_ip="127.0.0.1", listen_port=3400, 
                 server_ip="127.0.0.1", server_port=3500,
                 drone_id="drone_alpha"):
        
        # Initialize components
        self.root = tk.Tk()
        self.gui = DroneGUI(self.root)
        self.edge_processor = EdgeProcessor()
        self.battery_manager = BatteryManager()
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
        
        # Start the server
        self.log("Drone server initializing...")
        self.server_thread = threading.Thread(target=self._start_server)
        self.processor_thread = threading.Thread(target=self._process_data)
        self.battery_thread = threading.Thread(target=self._manage_battery)
        self.server_comm_thread = threading.Thread(target=self._communicate_with_server)
    
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
                        self.log(f"Received data from sensor {sensor_data.get('sensor_id')}")
                        
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
                # Always check battery status
                battery_status = self.battery_manager.check_status()

                # Default values
                avg_temp = None
                avg_humidity = None
                anomalies = []
                drone_status = "normal"

                if battery_status["charging"]:
                    drone_status = "charging"
                elif battery_status["returning_to_base"]:
                    drone_status = "returning_to_base"
                else:
                    # Only compute averages if operating normally
                    avg_temp, avg_humidity = self.edge_processor.compute_averages()
                    anomalies = self.edge_processor.get_anomalies()
                    drone_status = "normal"

                # Always try to send something, even when returning or charging
                success = self.drone_client.send_to_server(
                    avg_temp, 
                    avg_humidity, 
                    anomalies, 
                    battery_status["level"],
                    status=drone_status  # <-- New status field
                )

                # Update GUI connection status
                self.root.after(0, self.gui.update_connection_status, success)

                if success:
                    self.log(f"Data sent to central server successfully (Status: {drone_status})")
                else:
                    self.log("Failed to send data to central server")

                time.sleep(5)  # Send data every 5 seconds

            except Exception as e:
                self.log(f"Error communicating with server: {e}")
                time.sleep(5)



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