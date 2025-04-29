import socket
import threading
import json
import time
import tkinter as tk
from tkinter import ttk, scrolledtext
import datetime
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from collections import deque
import matplotlib.dates as mdates


class ServerGUI:
    """GUI for the central server to display data and status"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("Environmental Monitoring Central Server")
        self.root.geometry("1200x800")
        
        # Create tabbed interface
        self.tab_control = ttk.Notebook(root)
        
        # Create tabs
        self.dashboard_tab = ttk.Frame(self.tab_control)
        self.data_tab = ttk.Frame(self.tab_control)
        self.anomaly_tab = ttk.Frame(self.tab_control)
        self.log_tab = ttk.Frame(self.tab_control)
        
        self.tab_control.add(self.dashboard_tab, text="Dashboard")
        self.tab_control.add(self.data_tab, text="Raw Data")
        self.tab_control.add(self.anomaly_tab, text="Anomalies")
        self.tab_control.add(self.log_tab, text="Logs")
        self.tab_control.pack(expand=1, fill="both")
        
        # Set up the dashboard tab with current readings and charts
        self._setup_dashboard_tab()
        
        # Set up the data tab with historical data
        self._setup_data_tab()
        
        # Set up the anomalies tab
        self._setup_anomaly_tab()
        
        # Set up the log tab
        self._setup_log_tab()
        
        # Status bar at the bottom
        self._setup_status_bar()
        
        # Data structures for storing and displaying data
        self.drone_data = {}  # Store data by drone_id
        self.historical_data = {
            'timestamps': deque(maxlen=100),
            'temperatures': deque(maxlen=100),
            'humidities': deque(maxlen=100),
            'battery_levels': deque(maxlen=100)
        }
        
        # Initialize the drone status dictionary
        self.drone_statuses = {}  # Store connection status by drone_id
    
    def _setup_dashboard_tab(self):
        """Set up the dashboard with current readings and charts"""
        # Top panel for current readings
        top_frame = ttk.Frame(self.dashboard_tab)
        top_frame.pack(fill="x", padx=10, pady=10)
        
        # Current readings panel
        readings_frame = ttk.LabelFrame(top_frame, text="Current Readings")
        readings_frame.pack(side="left", padx=10, pady=10, fill="x", expand=True)
        
        # Current temperature reading
        ttk.Label(readings_frame, text="Temperature:").grid(row=0, column=0, padx=10, pady=5, sticky="w")
        self.current_temp = ttk.Label(readings_frame, text="--.-°C")
        self.current_temp.grid(row=0, column=1, padx=10, pady=5, sticky="w")
        
        # Current humidity reading
        ttk.Label(readings_frame, text="Humidity:").grid(row=1, column=0, padx=10, pady=5, sticky="w")
        self.current_humidity = ttk.Label(readings_frame, text="--.-%")
        self.current_humidity.grid(row=1, column=1, padx=10, pady=5, sticky="w")
        
        # Connected drones
        ttk.Label(readings_frame, text="Connected Drones:").grid(row=2, column=0, padx=10, pady=5, sticky="w")
        self.connected_drones = ttk.Label(readings_frame, text="0")
        self.connected_drones.grid(row=2, column=1, padx=10, pady=5, sticky="w")
        
        # Active anomalies
        ttk.Label(readings_frame, text="Active Anomalies:").grid(row=3, column=0, padx=10, pady=5, sticky="w")
        self.active_anomalies = ttk.Label(readings_frame, text="0")
        self.active_anomalies.grid(row=3, column=1, padx=10, pady=5, sticky="w")
        
        # Drone status panel
        drone_status_frame = ttk.LabelFrame(top_frame, text="Drone Status")
        drone_status_frame.pack(side="right", padx=10, pady=10, fill="both")
        
        # Create a tree view for drone status
        self.drone_status_tree = ttk.Treeview(drone_status_frame, columns=("Status", "Battery", "Last Seen"))
        self.drone_status_tree.heading("#0", text="Drone ID")
        self.drone_status_tree.heading("Status", text="Status")
        self.drone_status_tree.heading("Battery", text="Battery")
        self.drone_status_tree.heading("Last Seen", text="Last Seen")
        
        self.drone_status_tree.column("#0", width=100)
        self.drone_status_tree.column("Status", width=100)
        self.drone_status_tree.column("Battery", width=100)
        self.drone_status_tree.column("Last Seen", width=150)
        
        self.drone_status_tree.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Charts frame
        charts_frame = ttk.Frame(self.dashboard_tab)
        charts_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Create matplotlib figures for visualization
        self.fig, self.axes = plt.subplots(2, 1, figsize=(10, 8))
        self.canvas = FigureCanvasTkAgg(self.fig, master=charts_frame)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
        
        # Configure the temperature plot
        self.temp_line, = self.axes[0].plot([], [], 'r-', label='Temperature (°C)')
        self.axes[0].set_title('Temperature Over Time')
        self.axes[0].set_ylabel('Temperature (°C)')
        self.axes[0].legend(loc='upper right')
        self.axes[0].grid(True)
        
        # Configure the humidity plot
        self.humidity_line, = self.axes[1].plot([], [], 'b-', label='Humidity (%)')
        self.axes[1].set_title('Humidity Over Time')
        self.axes[1].set_xlabel('Time')
        self.axes[1].set_ylabel('Humidity (%)')
        self.axes[1].legend(loc='upper right')
        self.axes[1].grid(True)
        
        self.fig.tight_layout()
    
    def _setup_data_tab(self):
        """Set up the data tab with a table of historical data"""
        # Create a frame for filtering
        filter_frame = ttk.Frame(self.data_tab)
        filter_frame.pack(fill="x", padx=10, pady=10)
        
        # Drone filter
        ttk.Label(filter_frame, text="Drone:").pack(side="left", padx=5, pady=5)
        self.drone_filter = ttk.Combobox(filter_frame, values=["All"])
        self.drone_filter.pack(side="left", padx=5, pady=5)
        self.drone_filter.current(0)
        
        # Time range filter
        ttk.Label(filter_frame, text="Time Range:").pack(side="left", padx=5, pady=5)
        self.time_range = ttk.Combobox(filter_frame, 
                                      values=["Last 10 readings", "Last 50 readings", "Last 100 readings", "All"])
        self.time_range.pack(side="left", padx=5, pady=5)
        self.time_range.current(1)  # Default to last 50 readings
        
        # Apply filter button
        ttk.Button(filter_frame, text="Apply Filter", command=self._apply_filter).pack(side="left", padx=10, pady=5)
        
        # Export button
        ttk.Button(filter_frame, text="Export Data", command=self._export_data).pack(side="right", padx=10, pady=5)
        
        # Create data table
        table_frame = ttk.Frame(self.data_tab)
        table_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Create Treeview for data
        self.data_tree = ttk.Treeview(table_frame, 
                                     columns=("Drone ID", "Timestamp", "Temperature", "Humidity", "Battery"))
        self.data_tree.heading("#0", text="ID")
        self.data_tree.heading("Drone ID", text="Drone ID")
        self.data_tree.heading("Timestamp", text="Timestamp")
        self.data_tree.heading("Temperature", text="Temperature")
        self.data_tree.heading("Humidity", text="Humidity")
        self.data_tree.heading("Battery", text="Battery")
        
        self.data_tree.column("#0", width=50, stretch=tk.NO)
        self.data_tree.column("Drone ID", width=100, stretch=tk.YES)
        self.data_tree.column("Timestamp", width=200, stretch=tk.YES)
        self.data_tree.column("Temperature", width=100, stretch=tk.YES)
        self.data_tree.column("Humidity", width=100, stretch=tk.YES)
        self.data_tree.column("Battery", width=100, stretch=tk.YES)
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.data_tree.yview)
        self.data_tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.data_tree.pack(side="left", fill="both", expand=True)
    
    def _setup_anomaly_tab(self):
        """Set up the anomalies tab with a table of detected anomalies"""
        # Create anomaly filter frame
        filter_frame = ttk.Frame(self.anomaly_tab)
        filter_frame.pack(fill="x", padx=10, pady=10)
        
        # Filter by type
        ttk.Label(filter_frame, text="Anomaly Type:").pack(side="left", padx=5, pady=5)
        self.anomaly_type_filter = ttk.Combobox(filter_frame, 
                                               values=["All", "temperature_too_high", "temperature_too_low", 
                                                      "humidity_too_high", "humidity_too_low"])
        self.anomaly_type_filter.pack(side="left", padx=5, pady=5)
        self.anomaly_type_filter.current(0)
        
        # Filter by drone
        ttk.Label(filter_frame, text="Drone:").pack(side="left", padx=5, pady=5)
        self.anomaly_drone_filter = ttk.Combobox(filter_frame, values=["All"])
        self.anomaly_drone_filter.pack(side="left", padx=5, pady=5)
        self.anomaly_drone_filter.current(0)
        
        # Apply filter button
        ttk.Button(filter_frame, text="Apply Filter", command=self._apply_anomaly_filter).pack(side="left", padx=10, pady=5)
        
        # Create anomaly table
        table_frame = ttk.Frame(self.anomaly_tab)
        table_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Create Treeview for anomalies
        self.anomaly_tree = ttk.Treeview(table_frame, 
                                        columns=("Drone ID", "Sensor ID", "Issue", "Value", "Timestamp"))
        self.anomaly_tree.heading("#0", text="ID")
        self.anomaly_tree.heading("Drone ID", text="Drone ID")
        self.anomaly_tree.heading("Sensor ID", text="Sensor ID")
        self.anomaly_tree.heading("Issue", text="Issue")
        self.anomaly_tree.heading("Value", text="Value")
        self.anomaly_tree.heading("Timestamp", text="Timestamp")
        
        self.anomaly_tree.column("#0", width=50, stretch=tk.NO)
        self.anomaly_tree.column("Drone ID", width=100, stretch=tk.YES)
        self.anomaly_tree.column("Sensor ID", width=100, stretch=tk.YES)
        self.anomaly_tree.column("Issue", width=150, stretch=tk.YES)
        self.anomaly_tree.column("Value", width=100, stretch=tk.YES)
        self.anomaly_tree.column("Timestamp", width=200, stretch=tk.YES)
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.anomaly_tree.yview)
        self.anomaly_tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.anomaly_tree.pack(side="left", fill="both", expand=True)
        
        # Store all anomalies
        self.all_anomalies = []
    
    def _setup_log_tab(self):
        """Set up the log tab with a text area for logs"""
        # Create scrolled text widget for logs
        self.log_text = scrolledtext.ScrolledText(self.log_tab, wrap=tk.WORD)
        self.log_text.pack(fill="both", expand=True, padx=10, pady=10)
    
    def _setup_status_bar(self):
        """Set up status bar at the bottom of the window"""
        status_frame = ttk.Frame(self.root)
        status_frame.pack(side="bottom", fill="x")
        
        # Server status
        self.server_status = ttk.Label(status_frame, text="Server: Running")
        self.server_status.pack(side="left", padx=10)
        
        # Connection count
        self.connection_count = ttk.Label(status_frame, text="Connections: 0")
        self.connection_count.pack(side="left", padx=10)
        
        # Last updated
        self.last_updated = ttk.Label(status_frame, text="Last Updated: Never")
        self.last_updated.pack(side="right", padx=10)
    
    def _apply_filter(self):
        """Apply filter to the data table"""
        # This will be implemented to filter the data based on selected criteria
        pass
    
    def _apply_anomaly_filter(self):
        """Apply filter to the anomaly table"""
        # Clear the anomaly tree
        for item in self.anomaly_tree.get_children():
            self.anomaly_tree.delete(item)
        
        # Get filter values
        anomaly_type = self.anomaly_type_filter.get()
        drone_id = self.anomaly_drone_filter.get()
        
        # Apply filters
        filtered_anomalies = self.all_anomalies
        
        if anomaly_type != "All":
            filtered_anomalies = [a for a in filtered_anomalies if a["issue"] == anomaly_type]
        
        if drone_id != "All":
            filtered_anomalies = [a for a in filtered_anomalies if a["drone_id"] == drone_id]
        
        # Insert filtered anomalies
        for i, anomaly in enumerate(filtered_anomalies):
            self.anomaly_tree.insert("", "end", text=str(i+1),
                                    values=(anomaly["drone_id"],
                                           anomaly["sensor_id"],
                                           anomaly["issue"],
                                           f"{anomaly['value']:.2f}",
                                           anomaly["timestamp"]))
    
    def _export_data(self):
        """Export data to CSV file"""
        # This would be implemented to export data to a file
        self.log("Export functionality not implemented yet")
    
    def update_drone_status(self, drone_id, status, battery_level):
        """Update the drone status in the UI"""
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Update drone status dictionary
        if drone_id not in self.drone_statuses:
            self.drone_statuses[drone_id] = {
                "status": status,
                "battery": battery_level,
                "last_seen": current_time,
                "tree_id": None
            }
            
            # Add to filter dropdowns
            drones = list(self.drone_filter['values'])
            if drone_id not in drones:
                drones.append(drone_id)
                self.drone_filter['values'] = drones
                self.anomaly_drone_filter['values'] = drones
            
            # Add to tree view
            tree_id = self.drone_status_tree.insert("", "end", text=drone_id, 
                                                  values=(status, f"{battery_level}%", current_time))
            self.drone_statuses[drone_id]["tree_id"] = tree_id
        else:
            # Update existing entry
            self.drone_statuses[drone_id]["status"] = status
            self.drone_statuses[drone_id]["battery"] = battery_level
            self.drone_statuses[drone_id]["last_seen"] = current_time
            
            # Update tree view
            tree_id = self.drone_statuses[drone_id]["tree_id"]
            self.drone_status_tree.item(tree_id, values=(status, f"{battery_level}%", current_time))
        
        # Update connected drones count
        connected_count = sum(1 for status in self.drone_statuses.values() 
                            if status["last_seen"] > (datetime.datetime.now() - 
                                                    datetime.timedelta(seconds=30)).strftime("%Y-%m-%d %H:%M:%S"))
        self.connected_drones.config(text=str(connected_count))
    
    def update_current_readings(self, avg_temp, avg_humidity):
        """Update the current readings display"""
        self.current_temp.config(text=f"{avg_temp:.1f}°C")
        self.current_humidity.config(text=f"{avg_humidity:.1f}%")
    
    def update_charts(self):
        """Update the temperature and humidity charts"""
        if not self.historical_data['timestamps']:
            return
        
        # Convert timestamps to datetime objects for better plotting
        times = [datetime.datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ") for ts in self.historical_data['timestamps']]
        
        # Update temperature plot
        self.temp_line.set_data(times, self.historical_data['temperatures'])
        self.axes[0].relim()
        self.axes[0].autoscale_view()
        
        # Update humidity plot
        self.humidity_line.set_data(times, self.historical_data['humidities'])
        self.axes[1].relim()
        self.axes[1].autoscale_view()
        
        # Format x-axis with appropriate date formatter
        self.axes[0].xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
        self.axes[1].xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
        
        # Rotate date labels for better readability
        plt.setp(self.axes[0].xaxis.get_majorticklabels(), rotation=45)
        plt.setp(self.axes[1].xaxis.get_majorticklabels(), rotation=45)
        
        self.fig.tight_layout()
        self.canvas.draw()
    
    def add_data_entry(self, drone_data):
        """Add a data entry to the data table"""
        # Get the count of existing items to generate a new index
        index = len(self.data_tree.get_children()) + 1
        
        # Insert new data
        self.data_tree.insert("", "end", text=str(index),
                             values=(drone_data["drone_id"],
                                    drone_data["timestamp"],
                                    f"{drone_data['average_temperature']:.2f}°C",
                                    f"{drone_data['average_humidity']:.2f}%",
                                    f"{drone_data['battery_level']}%"))
        
        # Keep only the last 1000 entries
        if index > 1000:
            self.data_tree.delete(self.data_tree.get_children()[0])
        
        # Auto-scroll to the bottom
        self.data_tree.yview_moveto(1)
        
        # Add to historical data for charts
        self.historical_data['timestamps'].append(drone_data["timestamp"])
        self.historical_data['temperatures'].append(drone_data["average_temperature"])
        self.historical_data['humidities'].append(drone_data["average_humidity"])
        self.historical_data['battery_levels'].append(drone_data["battery_level"])
        
        # Update the charts
        self.update_charts()
        
        # Update last updated timestamp
        self.last_updated.config(text=f"Last Updated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    def add_anomalies(self, drone_id, anomalies):
        """Add anomalies to the anomaly table"""
        # Add drone_id to each anomaly
        for anomaly in anomalies:
            anomaly["drone_id"] = drone_id
            # Add to all anomalies list for filtering
            self.all_anomalies.append(anomaly)
        
        # Only keep the latest 1000 anomalies
        if len(self.all_anomalies) > 1000:
            self.all_anomalies = self.all_anomalies[-1000:]
        
        # Update the anomaly count
        self.active_anomalies.config(text=str(len(self.all_anomalies)))
        
        # Reapply current filter
        self._apply_anomaly_filter()
    
    def log(self, message):
        """Add a message to the log panel"""
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {message}\n"
        self.log_text.insert(tk.END, log_entry)
        self.log_text.see(tk.END)  # Auto-scroll to the latest log
    
    def update_server_status(self, status, connections):
        """Update the server status bar"""
        self.server_status.config(text=f"Server: {status}")
        self.connection_count.config(text=f"Connections: {connections}")


class CentralServer:
    """Central server that receives data from drones and displays it"""
    
    def __init__(self, listen_ip="127.0.0.1", listen_port=3500):
        # Initialize GUI
        self.root = tk.Tk()
        self.gui = ServerGUI(self.root)
        
        # Server settings
        self.listen_ip = listen_ip
        self.listen_port = listen_port
        
        # Thread control
        self.server_running = False
        self.active_connections = {}
        self.connection_lock = threading.Lock()
        
        # Start the server
        self.gui.log("Central server initializing...")
    
    def start(self):
        """Start the server and GUI"""
        self.server_running = True
        
        # Start server thread
        self.server_thread = threading.Thread(target=self._start_server)
        self.server_thread.daemon = True
        self.server_thread.start()
        
        # Start connection monitor thread
        self.monitor_thread = threading.Thread(target=self._monitor_connections)
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
        
        self.gui.log("Central server started and ready for drone connections")
        self.root.protocol("WM_DELETE_WINDOW", self.stop)  # Handle window close
        self.root.mainloop()
    
    def stop(self):
        """Stop the server and close all connections"""
        self.server_running = False
        
        # Close all active connections
        with self.connection_lock:
            for addr, client_info in list(self.active_connections.items()):
                conn = client_info["connection"]
                if conn:
                    try:
                        conn.close()
                    except:
                        pass
            self.active_connections.clear()
        
        # Close server socket if exists
        if hasattr(self, 'server_socket') and self.server_socket:
            self.server_socket.close()
        
        self.gui.log("Server shutting down")
        self.root.destroy()
    
    def _start_server(self):
        """Start the TCP server to listen for drone connections"""
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.listen_ip, self.listen_port))
            self.server_socket.listen(5)
            self.gui.log(f"Server listening on {self.listen_ip}:{self.listen_port}")
            
            # Update server status
            self.gui.update_server_status("Running", 0)
            
            while self.server_running:
                # Set a timeout so we can check server_running periodically
                self.server_socket.settimeout(1.0)
                
                try:
                    client_socket, addr = self.server_socket.accept()
                    
                    # Accept the connection and start a new thread to handle it
                    self.gui.log(f"New connection from {addr}")
                    
                    # Add to active connections with timestamp
                    with self.connection_lock:
                        self.active_connections[addr] = {
                            "connection": client_socket,
                            "last_active": time.time(),
                            "drone_id": None  # Will be set when first data is received
                        }
                    
                    # Update connection count
                    self.gui.update_server_status("Running", len(self.active_connections))
                    
                    # Start client handler thread
                    client_thread = threading.Thread(target=self._handle_client, 
                                                   args=(client_socket, addr))
                    client_thread.daemon = True
                    client_thread.start()
                
                except socket.timeout:
                    # This is expected, just continue the loop
                    continue
                except Exception as e:
                    if self.server_running:  # Only log if we're not shutting down
                        self.gui.log(f"Error accepting connection: {e}")
        
        except Exception as e:
            self.gui.log(f"Server error: {e}")
            self.gui.update_server_status("Error", 0)
        finally:
            if hasattr(self, 'server_socket'):
                self.server_socket.close()
    
    def _handle_client(self, client_socket, addr):
        """Handle communication with a connected drone"""
        try:
            self.gui.log(f"Handling client {addr}")
            client_socket.settimeout(60)  # 60 second timeout
            
            # Receive data from the client
            buffer = ""
            while self.server_running:
                try:
                    data = client_socket.recv(4096).decode('utf-8')
                    if not data:
                        self.gui.log(f"Client {addr} disconnected")
                        break
                    
                    # Update last active timestamp
                    with self.connection_lock:
                        if addr in self.active_connections:
                            self.active_connections[addr]["last_active"] = time.time()
                    
                    buffer += data
                    
                    # Process complete JSON objects
                    while '\n' in buffer:
                        line, buffer = buffer.split('\n', 1)
                        try:
                            drone_data = json.loads(line)
                            
                            # Update drone ID if not set
                            with self.connection_lock:
                                if addr in self.active_connections:
                                    if not self.active_connections[addr]["drone_id"]:
                                        self.active_connections[addr]["drone_id"] = drone_data["drone_id"]
                                        self.gui.log(f"Identified drone {drone_data['drone_id']} at {addr}")
                            
                            # Process the data
                            self._process_drone_data(drone_data)
                            
                        except json.JSONDecodeError:
                            self.gui.log(f"Error: Invalid JSON from {addr}")
                            continue
                
                except socket.timeout:
                    self.gui.log(f"No data received from {addr} for 60 seconds, checking connection")
                    # Don't close yet, let the monitor thread handle timeouts
                    continue
        
        except ConnectionResetError:
            self.gui.log(f"Connection to {addr} reset by peer")
        except Exception as e:
            self.gui.log(f"Error handling client {addr}: {e}")
        finally:
            # Mark connection as inactive
            with self.connection_lock:
                if addr in self.active_connections:
                    self.active_connections[addr]["connection"] = None
            
            # Update connection count
            active_count = sum(1 for client in self.active_connections.values() if client["connection"] is not None)
            self.gui.update_server_status("Running", active_count)
            
            # Close the socket
            client_socket.close()
    
    def _process_drone_data(self, drone_data):
        """Process data received from a drone"""
        # Log reception of data
        self.gui.log(f"Received data from drone {drone_data['drone_id']}")
        
        # Update GUI with current readings
        self.gui.update_current_readings(
            drone_data["average_temperature"],
            drone_data["average_humidity"]
        )
        
        # Update drone status
        status = "Normal"
        if drone_data.get("anomalies") and len(drone_data["anomalies"]) > 0:
            status = "Anomalies Detected"
        
        self.gui.update_drone_status(
            drone_data["drone_id"],
            status,
            drone_data["battery_level"]
        )
        
        # Add data entry to table
        self.gui.add_data_entry(drone_data)