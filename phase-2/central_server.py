#!/usr/bin/env python3
"""Central server for the environmental monitoring system.
Receives data from drones, displays it in real-time, and stores it for analysis."""
from collections import defaultdict
import socket
import json
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading
import datetime
import time
import argparse
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import matplotlib.dates as mdates
from matplotlib.backends.backend_tkagg import NavigationToolbar2Tk

# Check if ttkbootstrap is available
try:
    import ttkbootstrap as ttk
    from ttkbootstrap import Style
    USING_BOOTSTRAP = True
except ImportError:
    import tkinter.ttk as ttk
    USING_BOOTSTRAP = False

class ServerGUI:
    

    def __init__(self, root):
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
        self.last_anomaly_report = defaultdict(dict)  # Track last reported anomaly for each drone
        # Chart data storage
        self.chart_data = {
            "drone_ids": set(),
            "timestamps": [],
            "temperature": {},
            "humidity": {}
        }
        
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
        charts_tab = ttk.Frame(self.notebook)  # New charts tab
        
        # Add tabs to notebook
        self.notebook.add(main_tab, text="Main Dashboard")
        self.notebook.add(data_logs_tab, text="Data Logs")
        self.notebook.add(charts_tab, text="Charts")  # Add charts tab
        
        # Configure main tab grid weights
        main_tab.grid_columnconfigure(0, weight=2)  # Left column (tables)
        main_tab.grid_columnconfigure(1, weight=1)  # Right column (log)
        main_tab.grid_rowconfigure(0, weight=3)  # Drone status table
        main_tab.grid_rowconfigure(1, weight=4)  # Anomaly table
        
        # Configure data logs tab grid weights
        data_logs_tab.grid_columnconfigure(0, weight=1)
        data_logs_tab.grid_rowconfigure(0, weight=1)
        
        # Configure charts tab grid weights
        charts_tab.grid_columnconfigure(0, weight=1)
        charts_tab.grid_rowconfigure(0, weight=1)
        
        # Create panels in main tab
        self.setup_drone_status_panel(main_tab)
        self.setup_anomaly_panel(main_tab)
        self.setup_log_panel(main_tab)
        
        # Create data logs panel in data logs tab
        self.setup_data_logs_panel(data_logs_tab)
        
        # Create charts panel in charts tab
        self.setup_charts_panel(charts_tab)
        
        # Setup status bar in main frame
        self.setup_status_bar(main_frame)

    def setup_charts_panel(self, parent):
        """Set up the charts panel with temperature and humidity charts"""
        # Create notebook for sub-tabs
        self.charts_notebook = ttk.Notebook(parent)
        self.charts_notebook.grid(row=0, column=0, sticky="nsew")
        
        # Create sub-tab frames
        temp_tab = ttk.Frame(self.charts_notebook)
        humidity_tab = ttk.Frame(self.charts_notebook)
        
        # Add sub-tabs to notebook
        self.charts_notebook.add(temp_tab, text="Temperature")
        self.charts_notebook.add(humidity_tab, text="Humidity")
        
        # Configure grid weights for sub-tabs
        temp_tab.grid_columnconfigure(0, weight=1)
        temp_tab.grid_rowconfigure(0, weight=1)
        humidity_tab.grid_columnconfigure(0, weight=1)
        humidity_tab.grid_rowconfigure(0, weight=1)
        
        # Prepare data storage for charts
        self.chart_data = {
            "timestamps": [],
            "temperature": [],
            "humidity": []
        }
        
        # Setup chart frames
        self.setup_temperature_chart(temp_tab)
        self.setup_humidity_chart(humidity_tab)

    def setup_temperature_chart(self, parent):
        """Set up the temperature chart with pause/zoom functionality"""
        # Create frame for chart with padding
        if USING_BOOTSTRAP:
            chart_frame = ttk.Labelframe(parent, text="Temperature Over Time", padding=10, bootstyle="primary")
        else:
            chart_frame = ttk.LabelFrame(parent, text="Temperature Over Time", padding=10)
            
        chart_frame.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")
        
        # Configure grid weights
        chart_frame.grid_columnconfigure(0, weight=1)
        chart_frame.grid_rowconfigure(0, weight=1)
        
        # Create control frame for time range selection and controls
        control_frame = ttk.Frame(chart_frame)
        control_frame.grid(row=1, column=0, sticky="ew", pady=5)
        
        # Add time range selector
        ttk.Label(control_frame, text="Time Range:").pack(side="left", padx=5)
        self.temp_timerange_var = tk.StringVar(value="Last Hour")
        timerange_combo = ttk.Combobox(control_frame, textvariable=self.temp_timerange_var, 
                                    values=["Last Hour", "Last 12 Hours", "Last 24 Hours", "All Data"])
        timerange_combo.pack(side="left", padx=5)
        
        # Add pause/resume button
        self.temp_paused = False
        self.temp_pause_btn = ttk.Button(control_frame, text="Pause", 
                                    command=self.toggle_temp_pause)
        self.temp_pause_btn.pack(side="left", padx=10)
        
        # Add zoom controls
        ttk.Button(control_frame, text="Zoom In", 
                command=lambda: self.zoom_temp_chart(0.8)).pack(side="left", padx=2)
        ttk.Button(control_frame, text="Zoom Out", 
                command=lambda: self.zoom_temp_chart(1.25)).pack(side="left", padx=2)
        ttk.Button(control_frame, text="Reset Zoom", 
                command=self.reset_temp_zoom).pack(side="left", padx=2)
        
        # Create matplotlib figure
        self.temp_figure = Figure(figsize=(6, 4), dpi=100)
        self.temp_plot = self.temp_figure.add_subplot(111)
        self.temp_plot.set_title("Drone Temperature Readings")
        self.temp_plot.set_xlabel("Time")
        self.temp_plot.set_ylabel("Temperature (°C)")
        self.temp_plot.grid(True)
        
        # Store original axis limits for zoom functionality
        self.temp_original_xlim = None
        self.temp_original_ylim = None
        
        # Create canvas with navigation toolbar
        self.temp_canvas = FigureCanvasTkAgg(self.temp_figure, master=chart_frame)
        self.temp_canvas_widget = self.temp_canvas.get_tk_widget()
        self.temp_canvas_widget.grid(row=0, column=0, sticky="nsew")
        
        # Add navigation toolbar for additional zoom/pan functionality
        toolbar_frame = ttk.Frame(chart_frame)
        toolbar_frame.grid(row=2, column=0, sticky="ew", pady=2)
        self.temp_toolbar = NavigationToolbar2Tk(self.temp_canvas, toolbar_frame)
        self.temp_toolbar.update()
        
        # Bind changes to auto-update
        self.temp_timerange_var.trace_add("write", lambda *args: self.update_temperature_chart())

    def setup_humidity_chart(self, parent):
        """Set up the humidity chart with pause/zoom functionality"""
        # Create frame for chart with padding
        if USING_BOOTSTRAP:
            chart_frame = ttk.Labelframe(parent, text="Humidity Over Time", padding=10, bootstyle="info")
        else:
            chart_frame = ttk.LabelFrame(parent, text="Humidity Over Time", padding=10)
            
        chart_frame.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")
        
        # Configure grid weights
        chart_frame.grid_columnconfigure(0, weight=1)
        chart_frame.grid_rowconfigure(0, weight=1)
        
        # Create control frame for time range selection and controls
        control_frame = ttk.Frame(chart_frame)
        control_frame.grid(row=1, column=0, sticky="ew", pady=5)
        
        # Add time range selector
        ttk.Label(control_frame, text="Time Range:").pack(side="left", padx=5)
        self.humidity_timerange_var = tk.StringVar(value="Last Hour")
        timerange_combo = ttk.Combobox(control_frame, textvariable=self.humidity_timerange_var, 
                                    values=["Last Hour", "Last 12 Hours", "Last 24 Hours", "All Data"])
        timerange_combo.pack(side="left", padx=5)
        
        # Add pause/resume button
        self.humidity_paused = False
        self.humidity_pause_btn = ttk.Button(control_frame, text="Pause", 
                                        command=self.toggle_humidity_pause)
        self.humidity_pause_btn.pack(side="left", padx=10)
        
        # Add zoom controls
        ttk.Button(control_frame, text="Zoom In", 
                command=lambda: self.zoom_humidity_chart(0.8)).pack(side="left", padx=2)
        ttk.Button(control_frame, text="Zoom Out", 
                command=lambda: self.zoom_humidity_chart(1.25)).pack(side="left", padx=2)
        ttk.Button(control_frame, text="Reset Zoom", 
                command=self.reset_humidity_zoom).pack(side="left", padx=2)
        
        # Create matplotlib figure
        self.humidity_figure = Figure(figsize=(6, 4), dpi=100)
        self.humidity_plot = self.humidity_figure.add_subplot(111)
        self.humidity_plot.set_title("Drone Humidity Readings")
        self.humidity_plot.set_xlabel("Time")
        self.humidity_plot.set_ylabel("Humidity (%)")
        self.humidity_plot.grid(True)
        
        # Store original axis limits for zoom functionality
        self.humidity_original_xlim = None
        self.humidity_original_ylim = None
        
        # Create canvas with navigation toolbar
        self.humidity_canvas = FigureCanvasTkAgg(self.humidity_figure, master=chart_frame)  
        self.humidity_canvas_widget = self.humidity_canvas.get_tk_widget()
        self.humidity_canvas_widget.grid(row=0, column=0, sticky="nsew")
        
        # Add navigation toolbar for additional zoom/pan functionality
        toolbar_frame = ttk.Frame(chart_frame)
        toolbar_frame.grid(row=2, column=0, sticky="ew", pady=2)
        self.humidity_toolbar = NavigationToolbar2Tk(self.humidity_canvas, toolbar_frame)
        self.humidity_toolbar.update()
        
        # Bind changes to auto-update
        self.humidity_timerange_var.trace_add("write", lambda *args: self.update_humidity_chart())

    # Pause/Resume functionality methods
    def toggle_temp_pause(self):
        """Toggle pause/resume for temperature chart"""
        self.temp_paused = not self.temp_paused
        self.temp_pause_btn.config(text="Resume" if self.temp_paused else "Pause")
        
        if self.temp_paused:
            self.log("Temperature chart paused", "info")
        else:
            self.log("Temperature chart resumed", "info")
            # Update chart immediately when resuming
            self.update_temperature_chart()

    def toggle_humidity_pause(self):
        """Toggle pause/resume for humidity chart"""
        self.humidity_paused = not self.humidity_paused
        self.humidity_pause_btn.config(text="Resume" if self.humidity_paused else "Pause")
        
        if self.humidity_paused:
            self.log("Humidity chart paused", "info")
        else:
            self.log("Humidity chart resumed", "info")
            # Update chart immediately when resuming
            self.update_humidity_chart()

    # Zoom functionality methods
    def zoom_temp_chart(self, factor):
        """Zoom temperature chart by the given factor"""
        xlim = self.temp_plot.get_xlim()
        ylim = self.temp_plot.get_ylim()
        
        # Calculate center points
        x_center = (xlim[0] + xlim[1]) / 2
        y_center = (ylim[0] + ylim[1]) / 2
        
        # Calculate new ranges
        x_range = (xlim[1] - xlim[0]) * factor / 2
        y_range = (ylim[1] - ylim[0]) * factor / 2
        
        # Set new limits
        self.temp_plot.set_xlim(x_center - x_range, x_center + x_range)
        self.temp_plot.set_ylim(y_center - y_range, y_center + y_range)
        
        # Redraw canvas
        self.temp_canvas.draw()

    def zoom_humidity_chart(self, factor):
        """Zoom humidity chart by the given factor"""
        xlim = self.humidity_plot.get_xlim()
        ylim = self.humidity_plot.get_ylim()
        
        # Calculate center points
        x_center = (xlim[0] + xlim[1]) / 2
        y_center = (ylim[0] + ylim[1]) / 2
        
        # Calculate new ranges
        x_range = (xlim[1] - xlim[0]) * factor / 2
        y_range = (ylim[1] - ylim[0]) * factor / 2
        
        # Set new limits
        self.humidity_plot.set_xlim(x_center - x_range, x_center + x_range)
        self.humidity_plot.set_ylim(y_center - y_range, y_center + y_range)
        
        # Redraw canvas
        self.humidity_canvas.draw()

    def reset_temp_zoom(self):
        """Reset temperature chart zoom to show all data"""
        if self.temp_original_xlim and self.temp_original_ylim:
            self.temp_plot.set_xlim(self.temp_original_xlim)
            self.temp_plot.set_ylim(self.temp_original_ylim)
        else:
            self.temp_plot.autoscale()
        self.temp_canvas.draw()

    def reset_humidity_zoom(self):
        """Reset humidity chart zoom to show all data"""
        if self.humidity_original_xlim and self.humidity_original_ylim:
            self.humidity_plot.set_xlim(self.humidity_original_xlim)
            self.humidity_plot.set_ylim(self.humidity_original_ylim)
        else:
            self.humidity_plot.autoscale()
        self.humidity_canvas.draw()

    def filter_chart_data(self, timerange):
        """Filter chart data based on the selected time range"""
        now = datetime.datetime.now()
        
        # Create empty result structure
        result = {
            "timestamps": [],
            "temperature": [],
            "humidity": []
        }
        
        # If no data, return empty result
        if not self.chart_data["timestamps"]:
            return result
        
        # Define cutoff time based on selected time range
        if timerange == "Last Hour":
            cutoff = now - datetime.timedelta(hours=1)
        elif timerange == "Last 12 Hours":
            cutoff = now - datetime.timedelta(hours=12)
        elif timerange == "Last 24 Hours":
            cutoff = now - datetime.timedelta(hours=24)
        else:  # All Data
            cutoff = datetime.datetime.min
        
        # Process timestamps to datetime objects
        valid_indices = []
        for i, ts in enumerate(self.chart_data["timestamps"]):
            try:
                # Convert timestamp string to datetime object
                if isinstance(ts, datetime.datetime):
                    dt = ts
                elif 'T' in ts:
                    # ISO format handling
                    if ts.endswith('Z'):
                        dt = datetime.datetime.strptime(ts[:-1], "%Y-%m-%dT%H:%M:%S")
                    else:
                        dt = datetime.datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S")
                else:
                    # Try a simpler format
                    dt = datetime.datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
                
                # Include data point if it's after the cutoff time
                if dt >= cutoff:
                    valid_indices.append(i)
                    result["timestamps"].append(dt)
                
            except (ValueError, TypeError) as e:
                print(f"Error parsing timestamp '{ts}': {e}")
        
        # Extract temperature and humidity data for valid indices
        for i in valid_indices:
            if i < len(self.chart_data["temperature"]):
                result["temperature"].append(self.chart_data["temperature"][i])
            if i < len(self.chart_data["humidity"]):
                result["humidity"].append(self.chart_data["humidity"][i])
        
        return result

    def update_temperature_chart(self):
        """Update the temperature chart with current data (respects pause state)"""
        # Don't update if paused
        if hasattr(self, 'temp_paused') and self.temp_paused:
            return
        
        # Clear the plot
        self.temp_plot.clear()
        
        # Get selected time range
        selected_timerange = self.temp_timerange_var.get()
        
        # Get filtered data based on time range
        filtered_data = self.filter_chart_data(selected_timerange)
        
        if not filtered_data["timestamps"] or not filtered_data["temperature"]:
            # No data to display
            self.temp_plot.set_title("No Temperature Data Available")
            self.temp_canvas.draw()
            return
        
        # Get the dates from filtered data
        dates = filtered_data["timestamps"]
        
        # Filter out None values
        valid_points = [(dates[i], val) for i, val in enumerate(filtered_data["temperature"]) 
                        if val is not None]
        
        if not valid_points:
            self.temp_plot.set_title("No Valid Temperature Data")
            self.temp_canvas.draw()
            return
        
        # Unpack the valid points
        plot_dates, plot_values = zip(*valid_points)
        
        # Plot the temperature data
        self.temp_plot.plot(plot_dates, plot_values, 
                        marker='o', linestyle='-', markersize=5, 
                        color='#FF5733', label="Temperature")
        
        # Format the plot
        self.temp_plot.set_title("Temperature Over Time")
        self.temp_plot.set_xlabel("Time")
        self.temp_plot.set_ylabel("Temperature (°C)")
        self.temp_plot.grid(True)
        
        # Store original limits for zoom reset (only if not already stored)
        if self.temp_original_xlim is None:
            self.temp_original_xlim = self.temp_plot.get_xlim()
            self.temp_original_ylim = self.temp_plot.get_ylim()
        
        # Format date on x-axis
        self.temp_plot.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
        
        # Set appropriate time interval on x-axis
        if len(dates) > 20:
            self.temp_plot.xaxis.set_major_locator(mdates.HourLocator(interval=1))
        
        # Format y-axis with 1 decimal place
        self.temp_plot.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:.1f}"))
        
        # Adjust layout and redraw
        self.temp_figure.tight_layout()
        self.temp_canvas.draw()

    def update_humidity_chart(self):
        """Update the humidity chart with current data (respects pause state)"""
        # Don't update if paused
        if hasattr(self, 'humidity_paused') and self.humidity_paused:
            return
        
        # Clear the plot
        self.humidity_plot.clear()
        
        # Get selected time range
        selected_timerange = self.humidity_timerange_var.get()
        
        # Get filtered data based on time range
        filtered_data = self.filter_chart_data(selected_timerange)
        
        if not filtered_data["timestamps"] or not filtered_data["humidity"]:
            # No data to display
            self.humidity_plot.set_title("No Humidity Data Available")
            self.humidity_canvas.draw()
            return
        
        # Get the dates from filtered data
        dates = filtered_data["timestamps"]
        
        # Filter out None values
        valid_points = [(dates[i], val) for i, val in enumerate(filtered_data["humidity"]) 
                        if val is not None]
        
        if not valid_points:
            self.humidity_plot.set_title("No Valid Humidity Data")
            self.humidity_canvas.draw()
            return
        
        # Unpack the valid points
        plot_dates, plot_values = zip(*valid_points)
        
        # Plot the humidity data
        self.humidity_plot.plot(plot_dates, plot_values, 
                            marker='o', linestyle='-', markersize=5, 
                            color='#3498DB', label="Humidity")
        
        # Format the plot
        self.humidity_plot.set_title("Humidity Over Time")
        self.humidity_plot.set_xlabel("Time")
        self.humidity_plot.set_ylabel("Humidity (%)")
        self.humidity_plot.grid(True)
        
        # Store original limits for zoom reset (only if not already stored)
        if self.humidity_original_xlim is None:
            self.humidity_original_xlim = self.humidity_plot.get_xlim()
            self.humidity_original_ylim = self.humidity_plot.get_ylim()
        
        # Format date on x-axis
        self.humidity_plot.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
        
        # Set appropriate time interval on x-axis
        if len(dates) > 20:
            self.humidity_plot.xaxis.set_major_locator(mdates.HourLocator(interval=1))
        
        # Format y-axis with 1 decimal place
        self.humidity_plot.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:.1f}"))
        
        # Adjust layout and redraw
        self.humidity_figure.tight_layout()
        self.humidity_canvas.draw()

    # Modified add_data_to_charts method
    def add_data_to_charts(self, drone_data):
        """Add new data point to chart data storage"""
        with self.update_lock:
            # Extract timestamp - use received_at if available, otherwise use current time
            timestamp = drone_data.get("timestamp", drone_data.get("received_at", datetime.datetime.now().isoformat()))
            
            # Extract temperature and humidity
            temperature = drone_data.get("average_temperature")
            humidity = drone_data.get("average_humidity")
            
            # Add data to chart data storage
            self.chart_data["timestamps"].append(timestamp)
            self.chart_data["temperature"].append(temperature)
            self.chart_data["humidity"].append(humidity)
            
            # Limit data points to prevent memory issues (keep last 1000 points)
            if len(self.chart_data["timestamps"]) > 1000:
                self.chart_data["timestamps"].pop(0)
                self.chart_data["temperature"].pop(0)
                self.chart_data["humidity"].pop(0)
        
        # Update charts if not paused
        if not getattr(self, 'temp_paused', False):
            self.root.after(0, self.update_temperature_chart)
        if not getattr(self, 'humidity_paused', False):
            self.root.after(0, self.update_humidity_chart)
    def setup_drone_status_panel(self, parent):        
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
        columns = ("timestamp", "drone_id", "temperature", "humidity", "battery", "status")
        self.data_logs_table = ttk.Treeview(data_logs_frame, columns=columns, show="headings", height=15)
        
        # Configure columns
        self.data_logs_table.heading("timestamp", text="Timestamp")
        self.data_logs_table.heading("drone_id", text="Drone ID")
        self.data_logs_table.heading("temperature", text="Temperature (°C)")
        self.data_logs_table.heading("humidity", text="Humidity (%)")
        self.data_logs_table.heading("battery", text="Battery (%)")
        self.data_logs_table.heading("status", text="Status")
    
        
        # Set column widths and anchors
        self.data_logs_table.column("timestamp", width=150, anchor="center")
        self.data_logs_table.column("drone_id", width=100, anchor="center")
        self.data_logs_table.column("temperature", width=100, anchor="center")
        self.data_logs_table.column("humidity", width=100, anchor="center")
        self.data_logs_table.column("battery", width=80, anchor="center")
        self.data_logs_table.column("status", width=150, anchor="center")        
        
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
        # Schedule GUI update to be thread-safe
        self.root.after(0, self._update_log, message, level)

    def _update_log(self, message, level):        
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
        # Schedule GUI update to be thread-safe
        self.root.after(0, self._update_status_display, status, active_connection_count)

    def _update_status_display(self, status, active_connection_count):        
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

        # Check for special status values BEFORE standardizing format
        if raw_status.lower() == "returning_to_base" or raw_status.lower() == "returning to base":
            status = "Returning To Base"
        elif raw_status.lower() == "charging":
            status = "Charging"
        # Only standardize if not already handled by special cases
        else:
            # Standardize status format (convert snake_case to Title Case)
            if "_" in raw_status:
                status = " ".join(word.capitalize() for word in raw_status.split("_"))
            else:
                status = raw_status        

        # Handle low battery status (unless already in a special status)
        if battery < 20 and status not in ["Returning To Base", "Charging"]:
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
                    "warning" if status in ["Returning To Base"] else
                    "success" if status == "Charging" else "info")

        # Update data logs table                
        self.root.after(0, self._update_data_logs, drone_data, status)

        # Update drone status display
        self.root.after(0, self._update_drone_display, drone_data, status)

        # Add data to charts
        if status not in ["Charging", "Returning To Base"]:
            self.add_data_to_charts(drone_data)

    def _update_data_logs(self, drone_data, status):        
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
        
        # Determine row tag based on status and conditions
        tag = "normal"        
        if status == "Returning To Base":
            tag = "returning"
        elif status == "Charging":
            tag = "charging"
        elif battery < 20:
            tag = "low_battery"
        elif status == "normal":
            tag = "normal"
        
        # Insert into data logs table (newest at the top)
        values = (display_timestamp, drone_id, display_temp, display_humidity, 
                  display_battery, status)
        self.data_logs_table.insert("", 0, values=values, tags=(tag,))
        
        # Limit visible logs (delete old ones if over 1000)
        children = self.data_logs_table.get_children()
        if len(children) > 1000:
            self.data_logs_table.delete(children[-1])

    def _update_drone_display(self, drone_data, status=None):        
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
        elif status == "normal":
            tag = "normal"
        
        # Update or insert into table
        values = (drone_id, display_timestamp, display_temp, display_humidity, display_battery, status)
        if item_id:
            self.drone_table.item(item_id, values=values, tags=(tag,))
        else:
            self.drone_table.insert("", tk.END, values=values, tags=(tag,))

    def add_anomalies(self, drone_id, anomalies):
        """
        Adds detected anomalies to the anomaly list and updates the GUI.
        Logs the anomaly only if it's a new or changed anomaly value for a specific sensor/issue.
        """
        if not anomalies:
            return

        with self.update_lock:            
            if drone_id not in self.last_anomaly_report:
                self.last_anomaly_report[drone_id] = {}

            for anomaly in anomalies:
                sensor_id = anomaly.get("sensor_id")
                issue = anomaly.get("issue")
                value = anomaly.get("value")
                


        
                anomaly_key = (sensor_id, issue)

        
        if anomaly_key not in self.last_anomaly_report[drone_id] or \
            self.last_anomaly_report[drone_id][anomaly_key] != value:

 
            anomaly_entry = anomaly.copy()
            anomaly_entry["drone_id"] = drone_id
 

            self.anomalies.append(anomaly_entry)

 
            self.last_anomaly_report[drone_id][anomaly_key] = value

            if len(self.anomalies) > 1000:
                self.anomalies.pop(0)


            
            self.root.after(0, self._update_anomaly_display, [anomaly_entry])
            
            log_issue = anomaly.get("issue", "unknown")
            log_sensor_id = anomaly.get("sensor_id", "unknown")
            log_value = anomaly.get("value", "N/A")
            self.log(f"Anomaly detected on {drone_id}, sensor {log_sensor_id}: {log_issue} ({log_value})", "warning")

    def _update_anomaly_display(self, new_anomalies):
        # Process each new anomaly
        for anomaly in new_anomalies:
            # Extract data
            drone_id = anomaly.get("drone_id", "unknown")
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
            # Use self.gui.log as this is the server class logging
            self.gui.log("Received data without drone_id. Cannot process.", level='warning')
            return
        
        self.gui.log(f"Processing data from drone {drone_id}")

        self.gui.add_data_entry(drone_data)

        # Process anomalies if present
        anomalies = drone_data.get("anomalies")
        if anomalies and isinstance(anomalies, list):
            current_status = self.gui.drone_statuses.get(drone_id, {}).get("status")

            # 'Returning To Base' or 'Charging' states.
            if current_status not in ["Returning To Base", "Charging"]:
                # Call the add_anomalies method in ServerGUI to handle logging and UI updates                 
                self.gui.add_anomalies(drone_id, anomalies)            
                #self.gui.log(f"Skipping detailed anomaly processing for {drone_id} due to status: {current_status}", "info")    


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

