#!/usr/bin/env python3
"""Central server for the environmental monitoring system.
Receives data from drones, displays it in real-time, and stores it for analysis."""

import socket
import threading
import json
import time
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import datetime
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from collections import deque
import matplotlib.dates as mdates
import csv
import os
import sys
import argparse

class ServerGUI:
    """GUI for the central server to display and analyze environmental data"""

    def __init__(self, root):
        self.root = root
        self.root.title("Environmental Monitoring - Central Command")
        self.root.geometry("1280x900")
        self.root.minsize(1000, 700)

        # Configure styles
        self.configure_styles()

        # Create tabbed interface
        self.tab_control = ttk.Notebook(root)

        # Create tabs
        self.dashboard_tab = ttk.Frame(self.tab_control)
        self.data_tab = ttk.Frame(self.tab_control)
        self.anomaly_tab = ttk.Frame(self.tab_control)
        self.analytics_tab = ttk.Frame(self.tab_control)
        self.log_tab = ttk.Frame(self.tab_control)

        self.tab_control.add(self.dashboard_tab, text="Dashboard")
        self.tab_control.add(self.data_tab, text="Data Explorer")
        self.tab_control.add(self.anomaly_tab, text="Anomaly Tracker")
        self.tab_control.add(self.analytics_tab, text="Analytics")
        self.tab_control.add(self.log_tab, text="System Logs")
        self.tab_control.pack(expand=1, fill="both")

        # Set up each tab
        self._setup_dashboard_tab()
        self._setup_data_tab()
        self._setup_anomaly_tab()
        self._setup_analytics_tab()
        self._setup_log_tab()

        # Set up status bar at the bottom
        self._setup_status_bar()

        # Data structures
        # self.drone_data = {} # This was less useful, using drone_specific_data instead
        self.historical_data = { # Limited size for quick chart updates
            'timestamps': deque(maxlen=1000),
            'temperatures': deque(maxlen=1000),
            'humidities': deque(maxlen=1000),
            'battery_levels': deque(maxlen=1000)
        }

        # Drone-specific data structures for detailed history and filtering
        self.drone_specific_data = {}  # Store data by drone_id, deque(maxlen=5000) per drone

        # System metrics
        self.system_start_time = datetime.datetime.now()
        self.data_points_received = 0 # Total number of individual sensor readings
        self.anomalies_detected = 0 # Total number of anomalies recorded

        # Initialize the drone status dictionary
        self.drone_statuses = {}  # Store connection status and latest data by drone_id

        # All anomalies list for filtering and analysis
        self.all_anomalies = [] # deque(maxlen=5000) might be better for very long runs

        # Auto-update timer
        self.update_timer = None
        self.auto_update_interval = 5000  # milliseconds (5 seconds)
        self.setup_auto_update()

        # Link to the server instance (will be set by CentralServer)
        self.server_instance = None

    def configure_styles(self):
        """Configure ttk styles for better appearance"""
        style = ttk.Style()
        style.theme_use('clam')  # Use 'clam' theme as base

        # Configure notebook (tabs)
        style.configure('TNotebook', background='#f0f0f0', tabmargins=[2, 5, 2, 0])
        style.map('TNotebook.Tab', background=[('selected', '#4a6ea9')],
                   foreground=[('selected', '#ffffff')])
        style.configure('TNotebook.Tab', padding=[10, 5], font=('Arial', 10))

        # Configure frames
        style.configure('TFrame', background='#f5f5f5')
        style.configure('Dashboard.TFrame', background='#ffffff')

        # Configure labels
        style.configure('TLabel', font=('Arial', 10))
        style.configure('Header.TLabel', font=('Arial', 12, 'bold'))
        style.configure('Stats.TLabel', font=('Arial', 11), padding=5)
        style.configure('Value.TLabel', font=('Arial', 11, 'bold'), foreground='#2c3e50')

        # Configure buttons
        style.configure('TButton', font=('Arial', 10), padding=5)
        style.configure('Action.TButton', font=('Arial', 10, 'bold'),
                        background='#4a6ea9', foreground='white')

        # Configure Treeview
        style.configure('Treeview', font=('Arial', 9), rowheight=20)
        style.configure('Treeview.Heading', font=('Arial', 10, 'bold'))
        style.map('Treeview', background=[('selected', '#347083')],
                   foreground=[('selected', 'white')])


    def _setup_dashboard_tab(self):
        """Set up the dashboard with current readings, drone status, and charts"""
        # Use a grid layout for better organization
        self.dashboard_tab.columnconfigure(0, weight=2)
        self.dashboard_tab.columnconfigure(1, weight=3)
        self.dashboard_tab.rowconfigure(0, weight=1)
        self.dashboard_tab.rowconfigure(1, weight=4)

        # System overview panel (top left)
        overview_frame = ttk.LabelFrame(self.dashboard_tab, text="System Overview")
        overview_frame.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")

        # System metrics
        ttk.Label(overview_frame, text="System Status:", style='Stats.TLabel').grid(row=0, column=0, sticky="w", padx=10, pady=2)
        self.system_status = ttk.Label(overview_frame, text="Offline", style='Value.TLabel', foreground="#e74c3c")
        self.system_status.grid(row=0, column=1, sticky="w", padx=10, pady=2)

        ttk.Label(overview_frame, text="Running Since:", style='Stats.TLabel').grid(row=1, column=0, sticky="w", padx=10, pady=2)
        self.uptime_label = ttk.Label(overview_frame, text="00:00:00", style='Value.TLabel')
        self.uptime_label.grid(row=1, column=1, sticky="w", padx=10, pady=2)

        ttk.Label(overview_frame, text="Connected Drones:", style='Stats.TLabel').grid(row=2, column=0, sticky="w", padx=10, pady=2)
        self.connected_drones = ttk.Label(overview_frame, text="0", style='Value.TLabel')
        self.connected_drones.grid(row=2, column=1, sticky="w", padx=10, pady=2)

        ttk.Label(overview_frame, text="Data Points:", style='Stats.TLabel').grid(row=3, column=0, sticky="w", padx=10, pady=2)
        self.data_points = ttk.Label(overview_frame, text="0", style='Value.TLabel')
        self.data_points.grid(row=3, column=1, sticky="w", padx=10, pady=2)

        ttk.Label(overview_frame, text="Active Anomalies:", style='Stats.TLabel').grid(row=4, column=0, sticky="w", padx=10, pady=2)
        self.active_anomalies = ttk.Label(overview_frame, text="0", style='Value.TLabel')
        self.active_anomalies.grid(row=4, column=1, sticky="w", padx=10, pady=2)

        # Current readings panel (top right)
        readings_frame = ttk.LabelFrame(self.dashboard_tab, text="Current Environmental Readings")
        readings_frame.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")
        readings_frame.columnconfigure(0, weight=1)
        readings_frame.columnconfigure(1, weight=1)
        readings_frame.columnconfigure(2, weight=1)

        # Temperature gauge
        temp_frame = ttk.Frame(readings_frame)
        temp_frame.grid(row=0, column=0, padx=10, pady=5, sticky="nsew")

        ttk.Label(temp_frame, text="TEMPERATURE", style='Header.TLabel').pack(anchor="center", pady=5)
        self.current_temp = ttk.Label(temp_frame, text="--.-°C", font=('Arial', 18, 'bold'), foreground="#e74c3c")
        self.current_temp.pack(anchor="center", pady=5)
        ttk.Label(temp_frame, text="System Average", style='Stats.TLabel').pack(anchor="center")

        # Humidity gauge
        humidity_frame = ttk.Frame(readings_frame)
        humidity_frame.grid(row=0, column=1, padx=10, pady=5, sticky="nsew")

        ttk.Label(humidity_frame, text="HUMIDITY", style='Header.TLabel').pack(anchor="center", pady=5)
        self.current_humidity = ttk.Label(humidity_frame, text="--.-%", font=('Arial', 18, 'bold'), foreground="#3498db")
        self.current_humidity.pack(anchor="center", pady=5)
        ttk.Label(humidity_frame, text="System Average", style='Stats.TLabel').pack(anchor="center")

        # Battery gauge
        battery_frame = ttk.Frame(readings_frame)
        battery_frame.grid(row=0, column=2, padx=10, pady=5, sticky="nsew")

        ttk.Label(battery_frame, text="BATTERY", style='Header.TLabel').pack(anchor="center", pady=5)
        self.avg_battery = ttk.Label(battery_frame, text="--%", font=('Arial', 18, 'bold'), foreground="#2ecc71")
        self.avg_battery.pack(anchor="center", pady=5)
        ttk.Label(battery_frame, text="Average Level", style='Stats.TLabel').pack(anchor="center")

        # Drone status table (bottom left)
        status_frame = ttk.LabelFrame(self.dashboard_tab, text="Drone Fleet Status")
        status_frame.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")

        # Create a tree view for drone status
        self.drone_status_tree = ttk.Treeview(status_frame, columns=("Status", "Battery", "Temp", "Humidity", "Last Seen"))
        self.drone_status_tree.heading("#0", text="Drone ID")
        self.drone_status_tree.heading("Status", text="Status")
        self.drone_status_tree.heading("Battery", text="Battery")
        self.drone_status_tree.heading("Temp", text="Temperature")
        self.drone_status_tree.heading("Humidity", text="Humidity")
        self.drone_status_tree.heading("Last Seen", text="Last Seen")

        self.drone_status_tree.column("#0", width=80, anchor="center")
        self.drone_status_tree.column("Status", width=90, anchor="center")
        self.drone_status_tree.column("Battery", width=70, anchor="center")
        self.drone_status_tree.column("Temp", width=90, anchor="center")
        self.drone_status_tree.column("Humidity", width=90, anchor="center")
        self.drone_status_tree.column("Last Seen", width=130, anchor="center")

        # Add scrollbar
        status_scroll = ttk.Scrollbar(status_frame, orient="vertical", command=self.drone_status_tree.yview)
        self.drone_status_tree.configure(yscrollcommand=status_scroll.set)
        status_scroll.pack(side="right", fill="y")
        self.drone_status_tree.pack(side="left", fill="both", expand=True)

        # Charts frame (bottom right)
        charts_frame = ttk.LabelFrame(self.dashboard_tab, text="Environmental Trends")
        charts_frame.grid(row=1, column=1, padx=10, pady=10, sticky="nsew")

        # Create matplotlib figures for visualization
        self.fig, self.axes = plt.subplots(2, 1, figsize=(8, 6), dpi=80)
        self.canvas = FigureCanvasTkAgg(self.fig, master=charts_frame)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

        # Configure the temperature plot
        self.temp_line, = self.axes[0].plot([], [], 'r-', linewidth=2, label='Temperature (°C)')
        self.axes[0].set_title('Temperature Trend')
        self.axes[0].set_ylabel('Temperature (°C)')
        self.axes[0].legend(loc='upper right')
        self.axes[0].grid(True, linestyle='--', alpha=0.7)

        # Configure the humidity plot
        self.humidity_line, = self.axes[1].plot([], [], 'b-', linewidth=2, label='Humidity (%)')
        self.axes[1].set_title('Humidity Trend')
        self.axes[1].set_xlabel('Time')
        self.axes[1].set_ylabel('Humidity (%)')
        self.axes[1].legend(loc='upper right')
        self.axes[1].grid(True, linestyle='--', alpha=0.7)

        # Time period control for charts
        time_control_frame = ttk.Frame(charts_frame)
        time_control_frame.pack(fill="x", pady=5)

        ttk.Label(time_control_frame, text="Time Range:").pack(side="left", padx=5)
        self.time_range_var = tk.StringVar(value="Last 1 hour")
        time_range_combo = ttk.Combobox(time_control_frame, textvariable=self.time_range_var,
                                        values=["Last 10 minutes", "Last 30 minutes", "Last 1 hour", "Last 24 hours", "All data"],
                                        state="readonly") # Make it read-only
        time_range_combo.pack(side="left", padx=5)
        time_range_combo.bind("<<ComboboxSelected>>", self.update_charts)

        ttk.Button(time_control_frame, text="Refresh", command=self.update_charts).pack(side="right", padx=5)

        self.fig.tight_layout()


    def _setup_data_tab(self):
        """Set up the data tab with filtering options and data table"""
        # Configure grid
        self.data_tab.columnconfigure(0, weight=1)
        self.data_tab.rowconfigure(0, weight=0)
        self.data_tab.rowconfigure(1, weight=1)

        # Create a frame for filtering
        filter_frame = ttk.LabelFrame(self.data_tab, text="Data Filters")
        filter_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew")

        # First row of filters
        filter_row1 = ttk.Frame(filter_frame)
        filter_row1.pack(fill="x", padx=5, pady=5)

        # Drone filter
        ttk.Label(filter_row1, text="Drone:").pack(side="left", padx=5, pady=5)
        self.drone_filter = ttk.Combobox(filter_row1, values=["All"], width=15, state="readonly")
        self.drone_filter.pack(side="left", padx=5, pady=5)
        self.drone_filter.current(0)

        # Time range filter
        ttk.Label(filter_row1, text="Time Range:").pack(side="left", padx=20, pady=5)
        self.time_filter = ttk.Combobox(filter_row1,
                                       values=["Last hour", "Last 6 hours", "Last 24 hours", "Last 7 days", "All data"],
                                      width=15, state="readonly")
        self.time_filter.pack(side="left", padx=5, pady=5)
        self.time_filter.current(2)  # Default to last 24 hours

        # Second row of filters
        filter_row2 = ttk.Frame(filter_frame)
        filter_row2.pack(fill="x", padx=5, pady=5)

        # Temperature range filter
        ttk.Label(filter_row2, text="Temperature:").pack(side="left", padx=5, pady=5)
        ttk.Label(filter_row2, text="Min:").pack(side="left")
        self.temp_min = ttk.Entry(filter_row2, width=5)
        self.temp_min.pack(side="left", padx=2, pady=5)
        ttk.Label(filter_row2, text="Max:").pack(side="left", padx=5)
        self.temp_max = ttk.Entry(filter_row2, width=5)
        self.temp_max.pack(side="left", padx=2, pady=5)

        # Humidity range filter
        ttk.Label(filter_row2, text="Humidity:").pack(side="left", padx=20, pady=5)
        ttk.Label(filter_row2, text="Min:").pack(side="left")
        self.humid_min = ttk.Entry(filter_row2, width=5)
        self.humid_min.pack(side="left", padx=2, pady=5)
        ttk.Label(filter_row2, text="Max:").pack(side="left", padx=5)
        self.humid_max = ttk.Entry(filter_row2, width=5)
        self.humid_max.pack(side="left", padx=2, pady=5)

        # Action buttons
        button_frame = ttk.Frame(filter_frame)
        button_frame.pack(fill="x", padx=5, pady=10)

        ttk.Button(button_frame, text="Apply Filter", command=self._apply_filter).pack(side="left", padx=10, pady=5)
        ttk.Button(button_frame, text="Reset Filter", command=self._reset_filter).pack(side="left", padx=10, pady=5)
        ttk.Button(button_frame, text="Export Data", command=self._export_data).pack(side="right", padx=10, pady=5)

        # Create data table
        table_frame = ttk.Frame(self.data_tab)
        table_frame.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")

        # Create Treeview for data
        self.data_tree = ttk.Treeview(table_frame,
                                     columns=("Drone ID", "Timestamp", "Temperature", "Humidity", "Battery", "Readings"))
        self.data_tree.heading("#0", text="ID")
        self.data_tree.heading("Drone ID", text="Drone ID")
        self.data_tree.heading("Timestamp", text="Timestamp")
        self.data_tree.heading("Temperature", text="Temperature")
        self.data_tree.heading("Humidity", text="Humidity")
        self.data_tree.heading("Battery", text="Battery")
        self.data_tree.heading("Readings", text="# Readings")

        self.data_tree.column("#0", width=50, stretch=tk.NO, anchor="center")
        self.data_tree.column("Drone ID", width=100, stretch=tk.YES, anchor="center")
        self.data_tree.column("Timestamp", width=180, stretch=tk.YES, anchor="center")
        self.data_tree.column("Temperature", width=100, stretch=tk.YES, anchor="center")
        self.data_tree.column("Humidity", width=100, stretch=tk.YES, anchor="center")
        self.data_tree.column("Battery", width=100, stretch=tk.YES, anchor="center")
        self.data_tree.column("Readings", width=100, stretch=tk.YES, anchor="center")

        # Add scrollbars
        y_scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.data_tree.yview)
        x_scrollbar = ttk.Scrollbar(table_frame, orient="horizontal", command=self.data_tree.xview)
        self.data_tree.configure(yscrollcommand=y_scrollbar.set, xscrollcommand=x_scrollbar.set)

        y_scrollbar.pack(side="right", fill="y")
        x_scrollbar.pack(side="bottom", fill="x")
        self.data_tree.pack(side="left", fill="both", expand=True)


    def _setup_anomaly_tab(self):
        """Set up the anomalies tab with a table of detected anomalies"""
        # Configure grid
        self.anomaly_tab.columnconfigure(0, weight=1)
        self.anomaly_tab.rowconfigure(0, weight=0)
        self.anomaly_tab.rowconfigure(1, weight=1)

        # Create anomaly filter frame
        filter_frame = ttk.LabelFrame(self.anomaly_tab, text="Anomaly Filters")
        filter_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew")

        # First row of filters
        filter_row = ttk.Frame(filter_frame)
        filter_row.pack(fill="x", padx=5, pady=5)

        # Filter by type
        ttk.Label(filter_row, text="Anomaly Type:").pack(side="left", padx=5, pady=5)
        self.anomaly_type_filter = ttk.Combobox(filter_row,
                                                values=["All", "Temperature High", "Temperature Low",
                                                       "Humidity High", "Humidity Low", "Battery Low", "Connection Lost"],
                                               width=15, state="readonly")
        self.anomaly_type_filter.pack(side="left", padx=5, pady=5)
        self.anomaly_type_filter.current(0)

        # Filter by drone
        ttk.Label(filter_row, text="Drone:").pack(side="left", padx=20, pady=5)
        self.anomaly_drone_filter = ttk.Combobox(filter_row, values=["All"], width=15, state="readonly")
        self.anomaly_drone_filter.pack(side="left", padx=5, pady=5)
        self.anomaly_drone_filter.current(0)

        # Filter by time range
        ttk.Label(filter_row, text="Time Range:").pack(side="left", padx=20, pady=5)
        self.anomaly_time_filter = ttk.Combobox(filter_row,
                                               values=["Last hour", "Last 24 hours", "Last 7 days", "All"],
                                              width=15, state="readonly")
        self.anomaly_time_filter.pack(side="left", padx=5, pady=5)
        self.anomaly_time_filter.current(1)  # Default to last 24 hours

        # Action buttons
        button_frame = ttk.Frame(filter_frame)
        button_frame.pack(fill="x", padx=5, pady=5)

        ttk.Button(button_frame, text="Apply Filter", command=self._apply_anomaly_filter).pack(side="left", padx=10, pady=5)
        ttk.Button(button_frame, text="Reset Filter", command=self._reset_anomaly_filter).pack(side="left", padx=10, pady=5)
        ttk.Button(button_frame, text="Export Anomalies", command=self._export_anomalies).pack(side="right", padx=10, pady=5)

        # Create anomaly table
        table_frame = ttk.Frame(self.anomaly_tab)
        table_frame.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")

        # Create Treeview for anomalies
        self.anomaly_tree = ttk.Treeview(table_frame,
                                        columns=("Drone ID", "Sensor ID", "Issue", "Value", "Threshold", "Timestamp"))
        self.anomaly_tree.heading("#0", text="ID")
        self.anomaly_tree.heading("Drone ID", text="Drone ID")
        self.anomaly_tree.heading("Sensor ID", text="Sensor ID")
        self.anomaly_tree.heading("Issue", text="Issue")
        self.anomaly_tree.heading("Value", text="Value")
        self.anomaly_tree.heading("Threshold", text="Threshold")
        self.anomaly_tree.heading("Timestamp", text="Timestamp")

        self.anomaly_tree.column("#0", width=50, stretch=tk.NO, anchor="center")
        self.anomaly_tree.column("Drone ID", width=100, stretch=tk.YES, anchor="center")
        self.anomaly_tree.column("Sensor ID", width=100, stretch=tk.YES, anchor="center")
        self.anomaly_tree.column("Issue", width=150, stretch=tk.YES)
        self.anomaly_tree.column("Value", width=80, stretch=tk.YES, anchor="center")
        self.anomaly_tree.column("Threshold", width=80, stretch=tk.YES, anchor="center")
        self.anomaly_tree.column("Timestamp", width=180, stretch=tk.YES, anchor="center")

        # Add scrollbars
        y_scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.anomaly_tree.yview)
        x_scrollbar = ttk.Scrollbar(table_frame, orient="horizontal", command=self.anomaly_tree.xview)
        self.anomaly_tree.configure(yscrollcommand=y_scrollbar.set, xscrollcommand=x_scrollbar.set)

        y_scrollbar.pack(side="right", fill="y")
        x_scrollbar.pack(side="bottom", fill="x")
        self.anomaly_tree.pack(side="left", fill="both", expand=True)


    def _setup_analytics_tab(self):
        """Set up the analytics tab with statistical charts and metrics"""
        # Configure grid
        self.analytics_tab.columnconfigure(0, weight=1)
        self.analytics_tab.columnconfigure(1, weight=1)
        self.analytics_tab.rowconfigure(0, weight=1)
        self.analytics_tab.rowconfigure(1, weight=1)

        # Temperature statistics panel
        temp_frame = ttk.LabelFrame(self.analytics_tab, text="Temperature Statistics")
        temp_frame.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")

        # Create figure for temperature histogram
        self.temp_fig, self.temp_ax = plt.subplots(figsize=(5, 4), dpi=80)
        self.temp_canvas = FigureCanvasTkAgg(self.temp_fig, master=temp_frame)
        self.temp_canvas.get_tk_widget().pack(fill="both", expand=True, padx=5, pady=5)

        self.temp_ax.set_title('Temperature Distribution')
        self.temp_ax.set_xlabel('Temperature (°C)')
        self.temp_ax.set_ylabel('Frequency')
        self.temp_ax.grid(True, linestyle='--', alpha=0.7)

        # Humidity statistics panel
        humidity_frame = ttk.LabelFrame(self.analytics_tab, text="Humidity Statistics")
        humidity_frame.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")

        # Create figure for humidity histogram
        self.humidity_fig, self.humidity_ax = plt.subplots(figsize=(5, 4), dpi=80)
        self.humidity_canvas = FigureCanvasTkAgg(self.humidity_fig, master=humidity_frame)
        self.humidity_canvas.get_tk_widget().pack(fill="both", expand=True, padx=5, pady=5)

        self.humidity_ax.set_title('Humidity Distribution')
        self.humidity_ax.set_xlabel('Humidity (%)')
        self.humidity_ax.set_ylabel('Frequency')
        self.humidity_ax.grid(True, linestyle='--', alpha=0.7)

        # Drone comparison panel
        drone_frame = ttk.LabelFrame(self.analytics_tab, text="Drone Comparison")
        drone_frame.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")

        # Create figure for drone comparison
        self.drone_fig, self.drone_ax = plt.subplots(figsize=(5, 4), dpi=80)
        self.drone_canvas = FigureCanvasTkAgg(self.drone_fig, master=drone_frame)
        self.drone_canvas.get_tk_widget().pack(fill="both", expand=True, padx=5, pady=5)

        self.drone_ax.set_title('Average Temperature by Drone')
        self.drone_ax.set_xlabel('Drone ID')
        self.drone_ax.set_ylabel('Average Temperature (°C)')
        self.drone_ax.grid(True, linestyle='--', alpha=0.7, axis='y') # Grid only on y-axis

        # Anomaly distribution panel
        anomaly_frame = ttk.LabelFrame(self.analytics_tab, text="Anomaly Distribution")
        anomaly_frame.grid(row=1, column=1, padx=10, pady=10, sticky="nsew")

        # Create figure for anomaly pie chart
        self.anomaly_fig, self.anomaly_ax = plt.subplots(figsize=(5, 4), dpi=80)
        self.anomaly_canvas = FigureCanvasTkAgg(self.anomaly_fig, master=anomaly_frame)
        self.anomaly_canvas.get_tk_widget().pack(fill="both", expand=True, padx=5, pady=5)

        self.anomaly_ax.set_title('Anomaly Types')

        # Refresh button for analytics
        control_frame = ttk.Frame(self.analytics_tab)
        control_frame.grid(row=2, column=0, columnspan=2, padx=10, pady=5, sticky="ew")

        ttk.Button(control_frame, text="Refresh Analytics", command=self.update_analytics).pack(side="right", padx=10, pady=5)

        # Make sure plots are properly laid out
        self.temp_fig.tight_layout()
        self.humidity_fig.tight_layout()
        self.drone_fig.tight_layout()
        self.anomaly_fig.tight_layout()


    def _setup_log_tab(self):
        """Set up the log tab with a text area for logs"""
        # Configure grid
        self.log_tab.columnconfigure(0, weight=1)
        self.log_tab.rowconfigure(0, weight=1)

        # Create scrolled text widget for logs
        self.log_text = scrolledtext.ScrolledText(self.log_tab, wrap=tk.WORD, state='disabled', font=('Consolas', 9))
        self.log_text.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")

        # Add tags for coloring different log levels
        self.log_text.tag_config('info', foreground='black')
        self.log_text.tag_config('warning', foreground='orange')
        self.log_text.tag_config('error', foreground='red')


    def _setup_status_bar(self):
        """Set up status bar at the bottom of the window"""
        status_frame = ttk.Frame(self.root, style='TFrame')
        status_frame.pack(side="bottom", fill="x", padx=5, pady=2)

        # Server status
        self.server_status = ttk.Label(status_frame, text="Server: Initializing...", style='TLabel')
        self.server_status.pack(side="left", padx=10)

        # Connection count
        self.connection_count = ttk.Label(status_frame, text="Connections: 0", style='TLabel')
        self.connection_count.pack(side="left", padx=10)

        # Last updated
        self.last_updated = ttk.Label(status_frame, text="Last Updated: Never", style='TLabel')
        self.last_updated.pack(side="right", padx=10)


    def _apply_filter(self):
        """Apply filter to the data table based on selected criteria"""
        drone_id_filter = self.drone_filter.get()
        time_range_filter = self.time_filter.get()
        temp_min_filter = self.temp_min.get().strip()
        temp_max_filter = self.temp_max.get().strip()
        humid_min_filter = self.humid_min.get().strip()
        humid_max_filter = self.humid_max.get().strip()

        # Clear current data in the treeview
        for item in self.data_tree.get_children():
            self.data_tree.delete(item)

        # Get the time threshold based on the selected range
        now = datetime.datetime.now()
        time_delta = None
        if time_range_filter == "Last hour":
            time_delta = datetime.timedelta(hours=1)
        elif time_range_filter == "Last 6 hours":
            time_delta = datetime.timedelta(hours=6)
        elif time_range_filter == "Last 24 hours":
            time_delta = datetime.timedelta(hours=24)
        elif time_range_filter == "Last 7 days":
            time_delta = datetime.timedelta(days=7)

        time_threshold = now - time_delta if time_delta else None

        # Filter the data
        filtered_data = []
        # Iterate through all stored drone data
        for drone_id, data_list in self.drone_specific_data.items():
            if drone_id_filter != "All" and drone_id != drone_id_filter:
                continue # Skip if not the selected drone

            for entry in data_list:
                # Apply time filter
                try:
                    entry_time = datetime.datetime.strptime(entry["timestamp"], "%Y-%m-%dT%H:%M:%SZ")
                    if time_threshold and entry_time < time_threshold:
                        continue # Skip if outside the time range
                except ValueError:
                    self.log(f"Warning: Could not parse timestamp '{entry.get('timestamp')}' for filtering.", level='warning')
                    continue # Skip entry with invalid timestamp

                # Apply temperature filter
                try:
                    temp = entry.get("average_temperature")
                    if temp is not None:
                        if temp_min_filter and temp < float(temp_min_filter):
                            continue
                        if temp_max_filter and temp > float(temp_max_filter):
                            continue
                except ValueError:
                    self.log(f"Warning: Invalid temperature filter input: min='{temp_min_filter}', max='{temp_max_filter}'. Ignoring.", level='warning')
                    pass # Ignore invalid temperature filter input

                # Apply humidity filter
                try:
                    humidity = entry.get("average_humidity")
                    if humidity is not None:
                        if humid_min_filter and humidity < float(humid_min_min_filter):
                            continue
                        if humid_max_filter and humidity > float(humid_max_filter):
                            continue
                except ValueError:
                     self.log(f"Warning: Invalid humidity filter input: min='{humid_min_filter}', max='{humid_max_filter}'. Ignoring.", level='warning')
                     pass # Ignore invalid humidity filter input

                filtered_data.append(entry)

        # Sort filtered data by timestamp
        filtered_data.sort(key=lambda x: datetime.datetime.strptime(x["timestamp"], "%Y-%m-%dT%H:%M:%SZ") if "timestamp" in x else datetime.datetime.min)


        # Insert filtered data into the treeview
        for i, entry in enumerate(filtered_data):
             self.data_tree.insert("", "end", text=str(i+1),
                                    values=(entry.get("drone_id", "N/A"),
                                           entry.get("timestamp", "N/A"),
                                           f"{entry.get('average_temperature', 'N/A'):.2f}°C" if entry.get('average_temperature') is not None else 'N/A',
                                           f"{entry.get('average_humidity', 'N/A'):.2f}%" if entry.get('average_humidity') is not None else 'N/A',
                                           f"{entry.get('battery_level', 'N/A')}%" if entry.get('battery_level') is not None else 'N/A',
                                           entry.get("num_readings", "N/A")))

        self.log(f"Data filter applied: Drone='{drone_id_filter}', Time='{time_range_filter}', Temp='{temp_min_filter}-{temp_max_filter}', Humid='{humid_min_filter}-{humid_max_filter}'")


    def _reset_filter(self):
        """Reset data filter to default values and show all data"""
        self.drone_filter.current(0)
        self.time_filter.current(2) # Last 24 hours
        self.temp_min.delete(0, tk.END)
        self.temp_max.delete(0, tk.END)
        self.humid_min.delete(0, tk.END)
        self.humid_max.delete(0, tk.END)
        self._apply_filter() # Apply the reset filter
        self.log("Data filter reset.")


    def _export_data(self):
        """Export filtered data from the data table to a CSV file"""
        if not self.data_tree.get_children():
            messagebox.showinfo("Export Data", "No data to export.")
            return

        file_path = filedialog.asksaveasfilename(defaultextension=".csv",
                                                 filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                                                 title="Export Data")

        if not file_path:
            return # User cancelled

        try:
            with open(file_path, mode='w', newline='', encoding='utf-8') as file:
                writer = csv.writer(file)

                # Write header
                header = ["ID"] + [self.data_tree.heading(col, "text") for col in self.data_tree["columns"]]
                writer.writerow(header)

                # Write data rows
                for item_id in self.data_tree.get_children():
                    row_data = [self.data_tree.item(item_id, "text")] + list(self.data_tree.item(item_id, "values"))
                    writer.writerow(row_data)

            messagebox.showinfo("Export Data", f"Data successfully exported to:\n{file_path}")
            self.log(f"Data exported to {file_path}")

        except Exception as e:
            messagebox.showerror("Export Error", f"An error occurred during export:\n{e}")
            self.log(f"Error exporting data: {e}", level='error')


    def _apply_anomaly_filter(self):
        """Apply filter to the anomaly table"""
        # Clear the anomaly tree
        for item in self.anomaly_tree.get_children():
            self.anomaly_tree.delete(item)

        # Get filter values
        anomaly_type = self.anomaly_type_filter.get()
        drone_id = self.anomaly_drone_filter.get()
        time_range_filter = self.anomaly_time_filter.get()

        # Get the time threshold based on the selected range
        now = datetime.datetime.now()
        time_delta = None
        if time_range_filter == "Last hour":
            time_delta = datetime.timedelta(hours=1)
        elif time_range_filter == "Last 24 hours":
            time_delta = datetime.timedelta(hours=24)
        elif time_range_filter == "Last 7 days":
            time_delta = datetime.timedelta(days=7)

        time_threshold = now - time_delta if time_delta else None

        # Filter anomalies
        filtered_anomalies = []
        for anomaly in self.all_anomalies:
            # Apply type filter
            if anomaly_type != "All":
                # Map filter value to anomaly issue string
                filter_issue_map = {
                    "Temperature High": "temperature_too_high",
                    "Temperature Low": "temperature_too_low",
                    "Humidity High": "humidity_too_high",
                    "Humidity Low": "humidity_too_low",
                    "Battery Low": "battery_level_low",
                    "Connection Lost": "connection_lost" # Assuming this issue string
                }
                expected_issue = filter_issue_map.get(anomaly_type)

                if anomaly.get("issue") != expected_issue:
                    continue

            # Apply drone filter
            if drone_id != "All" and anomaly.get("drone_id") != drone_id:
                continue

            # Apply time filter
            try:
                anomaly_time_str = anomaly.get("timestamp")
                if anomaly_time_str:
                    anomaly_time = datetime.datetime.strptime(anomaly_time_str, "%Y-%m-%dT%H:%M:%SZ")
                    if time_threshold and anomaly_time < time_threshold:
                        continue
                elif time_threshold: # If no timestamp in anomaly, and time filter is active, skip
                     continue
            except ValueError:
                 self.log(f"Warning: Could not parse anomaly timestamp '{anomaly_time_str}' for filtering.", level='warning')
                 continue # Skip anomaly with invalid timestamp

            filtered_anomalies.append(anomaly)

        # Sort filtered anomalies by timestamp
        filtered_anomalies.sort(key=lambda x: datetime.datetime.strptime(x["timestamp"], "%Y-%m-%dT%H:%M:%SZ") if "timestamp" in x and x["timestamp"] else datetime.datetime.min)


        # Insert filtered anomalies
        for i, anomaly in enumerate(filtered_anomalies):
            self.anomaly_tree.insert("", "end", text=str(i+1),
                                    values=(anomaly.get("drone_id", "N/A"),
                                           anomaly.get("sensor_id", "N/A"),
                                           anomaly.get("issue", "N/A"),
                                           f"{anomaly.get('value', 'N/A'):.2f}" if isinstance(anomaly.get('value'), (int, float)) else anomaly.get('value', 'N/A'),
                                           f"{anomaly.get('threshold', 'N/A')}" if isinstance(anomaly.get('threshold'), (int, float)) else anomaly.get('threshold', 'N/A'),
                                           anomaly.get("timestamp", "N/A")))

        self.log(f"Anomaly filter applied: Type='{anomaly_type}', Drone='{drone_id}', Time='{time_range_filter}'")


    def _reset_anomaly_filter(self):
        """Reset anomaly filter to default values and show all anomalies"""
        self.anomaly_type_filter.current(0)
        self.anomaly_drone_filter.current(0)
        self.anomaly_time_filter.current(1) # Last 24 hours
        self._apply_anomaly_filter() # Apply the reset filter
        self.log("Anomaly filter reset.")


    def _export_anomalies(self):
        """Export filtered anomalies from the anomaly table to a CSV file"""
        if not self.anomaly_tree.get_children():
            messagebox.showinfo("Export Anomalies", "No anomalies to export.")
            return

        file_path = filedialog.asksaveasfilename(defaultextension=".csv",
                                                 filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                                                 title="Export Anomalies")

        if not file_path:
            return # User cancelled

        try:
            with open(file_path, mode='w', newline='', encoding='utf-8') as file:
                writer = csv.writer(file)

                # Write header
                header = ["ID"] + [self.anomaly_tree.heading(col, "text") for col in self.anomaly_tree["columns"]]
                writer.writerow(header)

                # Write data rows
                for item_id in self.anomaly_tree.get_children():
                    row_data = [self.anomaly_tree.item(item_id, "text")] + list(self.anomaly_tree.item(item_id, "values"))
                    writer.writerow(row_data)

            messagebox.showinfo("Export Anomalies", f"Anomalies successfully exported to:\n{file_path}")
            self.log(f"Anomalies exported to {file_path}")

        except Exception as e:
            messagebox.showerror("Export Error", f"An error occurred during export:\n{e}")
            self.log(f"Error exporting anomalies: {e}", level='error')


    def update_drone_status(self, drone_id, status, battery_level, temp, humidity):
        """Update the drone status in the UI and internal dictionary"""
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Update drone status dictionary
        if drone_id not in self.drone_statuses:
            self.drone_statuses[drone_id] = {
                "status": status,
                "battery": battery_level,
                "temp": temp,
                "humidity": humidity,
                "last_seen": current_time,
                "tree_id": None # Store the treeview item ID
            }

            # Add to filter dropdowns if not already present
            current_drones = list(self.drone_filter['values'])
            if drone_id not in current_drones:
                # Insert in sorted order (excluding "All")
                drones_without_all = sorted([d for d in current_drones if d != "All"] + [drone_id])
                self.drone_filter['values'] = ["All"] + drones_without_all
                self.anomaly_drone_filter['values'] = ["All"] + drones_without_all


            # Add to tree view
            tree_id = self.drone_status_tree.insert("", "end", text=drone_id,
                                                  values=(status, f"{battery_level:.0f}%", f"{temp:.1f}°C", f"{humidity:.1f}%", current_time))
            self.drone_statuses[drone_id]["tree_id"] = tree_id
            self.log(f"New drone status tracked for: {drone_id}")

        else:
            # Update existing entry in dictionary
            self.drone_statuses[drone_id]["status"] = status
            self.drone_statuses[drone_id]["battery"] = battery_level
            self.drone_statuses[drone_id]["temp"] = temp
            self.drone_statuses[drone_id]["humidity"] = humidity
            self.drone_statuses[drone_id]["last_seen"] = current_time

            # Update tree view
            tree_id = self.drone_statuses[drone_id]["tree_id"]
            if tree_id: # Ensure tree_id exists
                 self.drone_status_tree.item(tree_id, values=(status, f"{battery_level:.0f}%", f"{temp:.1f}°C", f"{humidity:.1f}%", current_time))


    def update_current_readings(self):
        """Calculate and update the system-wide average readings based on recent data"""
        total_temp = 0
        total_humidity = 0
        total_battery = 0
        active_drones_count = 0
        now = datetime.datetime.now()
        timeout_seconds = 30 # Consider drones active if seen in the last 30 seconds

        # Iterate through drone statuses to get the latest data
        # Create a list to track disconnected drones
        disconnected_drones = []

        for drone_id, status_data in list(self.drone_statuses.items()): # Use list to allow modification during iteration
            try:
                last_seen_time = datetime.datetime.strptime(status_data["last_seen"], "%Y-%m-%d %H:%M:%S")
                if (now - last_seen_time).total_seconds() < timeout_seconds:
                     total_temp += status_data["temp"]
                     total_humidity += status_data["humidity"]
                     total_battery += status_data["battery"]
                     active_drones_count += 1
                     # Update status in treeview if it was previously marked as disconnected
                     if status_data["status"] == "Disconnected":
                          self.update_drone_status(drone_id, "Connected", status_data["battery"], status_data["temp"], status_data["humidity"])
                else:
                    # Mark drone as disconnected if not seen recently
                    if status_data["status"] != "Disconnected":
                        self.update_drone_status(drone_id, "Disconnected", status_data["battery"], status_data["temp"], status_data["humidity"])
                        # Add a 'connection_lost' anomaly
                        self.add_anomalies(drone_id, [{
                            "issue": "connection_lost",
                            "value": (now - last_seen_time).total_seconds(),
                            "threshold": timeout_seconds,
                            "timestamp": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                            "sensor_id": "N/A" # Connection is not tied to a specific sensor
                        }])
                        self.log(f"Drone {drone_id} connection lost (last seen {status_data['last_seen']})", level='warning')


            except ValueError:
                self.log(f"Warning: Could not parse last_seen timestamp for drone {drone_id}: '{status_data.get('last_seen')}'", level='warning')
                # Treat as disconnected if timestamp is invalid
                if status_data["status"] != "Disconnected":
                    self.update_drone_status(drone_id, "Disconnected", status_data.get("battery", 0), status_data.get("temp", 0), status_data.get("humidity", 0))
                    self.log(f"Drone {drone_id} marked as disconnected due to invalid timestamp.", level='warning')


        if active_drones_count > 0:
            avg_temp = total_temp / active_drones_count
            avg_humidity = total_humidity / active_drones_count
            avg_battery = total_battery / active_drones_count
            self.current_temp.config(text=f"{avg_temp:.1f}°C")
            self.current_humidity.config(text=f"{avg_humidity:.1f}%")
            self.avg_battery.config(text=f"{avg_battery:.0f}%")
        else:
            self.current_temp.config(text="--.-°C")
            self.current_humidity.config(text="--.-%")
            self.avg_battery.config(text="--%")

        # Update connected drones count
        self.connected_drones.config(text=str(active_drones_count))


    def update_charts(self, event=None):
        """Update the temperature and humidity charts based on the selected time range"""
        time_range_filter = self.time_range_var.get()

        # Get the time threshold based on the selected range
        now = datetime.datetime.now()
        time_delta = None
        if time_range_filter == "Last 10 minutes":
            time_delta = datetime.timedelta(minutes=10)
        elif time_range_filter == "Last 30 minutes":
            time_delta = datetime.timedelta(minutes=30)
        elif time_range_filter == "Last 1 hour":
            time_delta = datetime.timedelta(hours=1)
        elif time_range_filter == "Last 24 hours":
            time_delta = datetime.timedelta(hours=24)
        elif time_range_filter == "All data":
             time_delta = None # No time limit

        time_threshold = now - time_delta if time_delta else None

        # Filter historical data based on time threshold
        filtered_times = []
        filtered_temps = []
        filtered_humidities = []

        # Use data from drone_specific_data for charts to have access to more history
        all_timestamps = []
        all_temps = []
        all_humidities = []

        for drone_id, data_list in self.drone_specific_data.items():
            for entry in data_list:
                try:
                    entry_time = datetime.datetime.strptime(entry["timestamp"], "%Y-%m-%dT%H:%M:%SZ")
                    if time_threshold and entry_time < time_threshold:
                        continue
                    all_timestamps.append(entry_time)
                    all_temps.append(entry["average_temperature"])
                    all_humidities.append(entry["average_humidity"])
                except ValueError:
                    self.log(f"Warning: Could not parse timestamp '{entry.get('timestamp')}' for chart filtering.", level='warning')
                    continue # Skip entry with invalid timestamp


        # Sort data by time
        # Combine and sort is more robust than relying on deque order for time range filtering
        combined_data = sorted(zip(all_timestamps, all_temps, all_humidities))
        filtered_times, filtered_temps, filtered_humidities = zip(*combined_data) if combined_data else ([], [], [])


        # Update temperature plot
        self.temp_line.set_data(filtered_times, filtered_temps)
        self.axes[0].relim()
        self.axes[0].autoscale_view()

        # Update humidity plot
        self.humidity_line.set_data(filtered_times, filtered_humidities)
        self.axes[1].relim()
        self.axes[1].autoscale_view()

        # Set x-axis limits
        if filtered_times:
            self.axes[0].set_xlim([min(filtered_times), max(filtered_times)])
            self.axes[1].set_xlim([min(filtered_times), max(filtered_times)])
        else:
             # Set a default small range if no data
             self.axes[0].set_xlim([now - datetime.timedelta(minutes=1), now])
             self.axes[1].set_xlim([now - datetime.timedelta(minutes=1), now])


        # Format x-axis with appropriate date formatter
        self.axes[0].xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
        self.axes[1].xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))

        # Rotate date labels for better readability
        self.fig.autofmt_xdate()

        self.fig.tight_layout()
        self.canvas.draw_idle() # Use draw_idle for better performance


    def update_analytics(self):
        """Update the analytics charts and statistics"""
        # Get all historical data for analytics
        all_temps = [entry['average_temperature'] for drone_data_list in self.drone_specific_data.values() for entry in drone_data_list if 'average_temperature' in entry and entry['average_temperature'] is not None]
        all_humidities = [entry['average_humidity'] for drone_data_list in self.drone_specific_data.values() for entry in drone_data_list if 'average_humidity' in entry and entry['average_humidity'] is not None]

        # Update Temperature Distribution Histogram
        self.temp_ax.clear()
        if all_temps:
            self.temp_ax.hist(all_temps, bins=20, color='#e74c3c', edgecolor='black')
        self.temp_ax.set_title('Temperature Distribution')
        self.temp_ax.set_xlabel('Temperature (°C)')
        self.temp_ax.set_ylabel('Frequency')
        self.temp_ax.grid(True, linestyle='--', alpha=0.7)
        self.temp_fig.tight_layout()
        self.temp_canvas.draw_idle()

        # Update Humidity Distribution Histogram
        self.humidity_ax.clear()
        if all_humidities:
            self.humidity_ax.hist(all_humidities, bins=20, color='#3498db', edgecolor='black')
        self.humidity_ax.set_title('Humidity Distribution')
        self.humidity_ax.set_xlabel('Humidity (%)')
        self.humidity_ax.set_ylabel('Frequency')
        self.humidity_ax.grid(True, linestyle='--', alpha=0.7)
        self.humidity_fig.tight_layout()
        self.humidity_canvas.draw_idle()

        # Update Drone Comparison (Average Temperature)
        self.drone_ax.clear()
        if self.drone_specific_data:
            drone_ids = []
            avg_temps = []
            for drone_id, data_list in self.drone_specific_data.items():
                valid_temps = [entry['average_temperature'] for entry in data_list if 'average_temperature' in entry and entry['average_temperature'] is not None]
                if valid_temps:
                    drone_ids.append(drone_id)
                    avg_temps.append(sum(valid_temps) / len(valid_temps))
            if drone_ids:
                # Sort by drone ID for consistent plotting
                sorted_drones = sorted(zip(drone_ids, avg_temps))
                sorted_drone_ids, sorted_avg_temps = zip(*sorted_drones)
                self.drone_ax.bar(sorted_drone_ids, sorted_avg_temps, color='#2ecc71')
                self.drone_ax.set_title('Average Temperature by Drone')
                self.drone_ax.set_xlabel('Drone ID')
                self.drone_ax.set_ylabel('Average Temperature (°C)')
                self.drone_ax.tick_params(axis='x', rotation=45)
        self.drone_ax.grid(True, linestyle='--', alpha=0.7, axis='y')
        self.drone_fig.tight_layout()
        self.drone_canvas.draw_idle()

        # Update Anomaly Distribution Pie Chart
        self.anomaly_ax.clear()
        if self.all_anomalies:
            anomaly_counts = {}
            for anomaly in self.all_anomalies:
                issue = anomaly.get("issue", "Unknown")
                anomaly_counts[issue] = anomaly_counts.get(issue, 0) + 1

            labels = anomaly_counts.keys()
            sizes = anomaly_counts.values()
            colors = ['#e74c3c', '#f39c12', '#3498db', '#9b59b6', '#f1c40f', '#1abc9c', '#7f8c8d'] # Example colors
            # Ensure number of colors matches number of labels
            pie_colors = colors[:len(labels)] + [plt.cm.viridis(i/len(labels)) for i in range(len(labels) - len(colors))] # Use viridis colormap for remaining
            self.anomaly_ax.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=90, colors=pie_colors)
            self.anomaly_ax.axis('equal')  # Equal aspect ratio ensures that pie is drawn as a circle.
        self.anomaly_ax.set_title('Anomaly Types Distribution')
        self.anomaly_fig.tight_layout()
        self.anomaly_canvas.draw_idle()

        self.log("Analytics updated.")


    def add_data_entry(self, drone_data):
        """Add a data entry to the internal data structures and update relevant counts"""
        drone_id = drone_data.get("drone_id")
        if not drone_id:
             self.log("Received data with no drone_id. Skipping.", level='warning')
             return

        timestamp_str = drone_data.get("timestamp")
        if not timestamp_str:
             self.log(f"Received data from {drone_id} with no timestamp. Skipping.", level='warning')
             return

        avg_temp = drone_data.get("average_temperature")
        avg_humidity = drone_data.get("average_humidity")
        battery_level = drone_data.get("battery_level")
        num_readings = drone_data.get("num_readings", 1) # Default to 1 if not provided

        # Store data in drone-specific structure
        if drone_id not in self.drone_specific_data:
            # Limit history per drone to prevent excessive memory usage
            self.drone_specific_data[drone_id] = deque(maxlen=5000)
        self.drone_specific_data[drone_id].append(drone_data)

        # Add to historical data for system-wide charts (limited size)
        # This deque is primarily for the dashboard charts' live view
        self.historical_data['timestamps'].append(timestamp_str)
        if avg_temp is not None:
             self.historical_data['temperatures'].append(avg_temp)
        else:
             self.historical_data['temperatures'].append(0) # Append a placeholder or handle None

        if avg_humidity is not None:
             self.historical_data['humidities'].append(avg_humidity)
        else:
             self.historical_data['humidities'].append(0) # Append a placeholder or handle None

        if battery_level is not None:
             self.historical_data['battery_levels'].append(battery_level)
        else:
             self.historical_data['battery_levels'].append(0) # Append a placeholder or handle None


        # Increment data points received
        self.data_points_received += num_readings
        self.data_points.config(text=str(self.data_points_received))

        # Update the 'Last Updated' timestamp
        self.last_updated.config(text=f"Last Updated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        # Update the drone's specific status in the dashboard table
        # Use received data for the status table display
        self.update_drone_status(drone_id, "Connected", battery_level if battery_level is not None else 0, avg_temp if avg_temp is not None else 0, avg_humidity if avg_humidity is not None else 0)


        # The data table and charts are updated by the auto_update timer
        # self.update_charts() # Moved to auto_update
        # self._apply_filter() # Moved to auto_update


    def add_anomalies(self, drone_id, anomalies):
        """Add anomalies to the internal list and update UI elements"""
        if not isinstance(anomalies, list):
             self.log(f"Received anomalies from {drone_id} in incorrect format (expected list). Skipping.", level='warning')
             return

        current_time_str = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
        anomalies_added_count = 0
        for anomaly in anomalies:
            if not isinstance(anomaly, dict):
                 self.log(f"Received anomaly from {drone_id} in incorrect format (expected dict). Skipping.", level='warning')
                 continue

            # Ensure essential keys exist or provide defaults
            anomaly["drone_id"] = drone_id
            anomaly["timestamp"] = anomaly.get("timestamp", current_time_str) # Use received timestamp if available, otherwise current
            anomaly["issue"] = anomaly.get("issue", "Unknown Anomaly")
            anomaly["value"] = anomaly.get("value", "N/A")
            anomaly["threshold"] = anomaly.get("threshold", "N/A")
            anomaly["sensor_id"] = anomaly.get("sensor_id", "N/A")

            self.all_anomalies.append(anomaly)
            anomalies_added_count += 1

        # Keep only the latest 5000 anomalies across all drones
        if len(self.all_anomalies) > 5000:
            self.all_anomalies = self.all_anomalies[-5000:] # Keep the most recent

        # Update the anomaly count
        self.anomalies_detected = len(self.all_anomalies)
        self.active_anomalies.config(text=str(self.anomalies_detected))

        # Reapply current filter to update the anomaly table
        self._apply_anomaly_filter()

        if anomalies_added_count > 0:
             self.log(f"Received and processed {anomalies_added_count} anomalies from {drone_id}", level='warning')


    def log(self, message, level='info'):
        """Add a message to the log panel with a timestamp and optional color tag"""
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {message}\n"

        self.log_text.configure(state='normal') # Enable editing
        self.log_text.insert(tk.END, log_entry, level) # Insert with tag
        self.log_text.configure(state='disabled') # Disable editing

        self.log_text.see(tk.END)  # Auto-scroll to the latest log


    def update_server_status(self, status, connections):
        """Update the server status bar and system status label"""
        self.server_status.config(text=f"Server: {status}")
        self.connection_count.config(text=f"Connections: {connections}")
        if status == "Running":
            self.system_status.config(text="Online", foreground="#2ecc71")
        elif status == "Stopped":
             self.system_status.config(text="Offline", foreground="#e74c3c")
        elif status == "Error":
             self.system_status.config(text="Error", foreground="#f39c12")


    def setup_auto_update(self):
        """Set up a timer to periodically update the GUI elements"""
        self.auto_update() # Run immediately on setup

    def auto_update(self):
        """Periodically update GUI elements like charts, data table, and uptime"""
        # Update uptime
        uptime_delta = datetime.datetime.now() - self.system_start_time
        hours, remainder = divmod(uptime_delta.total_seconds(), 3600)
        minutes, seconds = divmod(remainder, 60)
        self.uptime_label.config(text=f"{int(hours):02}:{int(minutes):02}:{int(seconds):02}")

        # Update current readings (averages)
        self.update_current_readings()

        # Update charts
        self.update_charts()

        # Update data table (reapply filter to show latest data)
        # Note: Reapplying the filter on every auto_update might be slow with very large datasets.
        # Consider optimizing this if performance becomes an issue.
        self._apply_filter()

        # Schedule the next update
        self.update_timer = self.root.after(self.auto_update_interval, self.auto_update)

    def on_closing(self):
        """Handle window closing event"""
        if messagebox.askokcancel("Quit", "Do you want to quit the server?"):
            # Stop the server (if CentralServer instance is available)
            if self.server_instance:
                self.server_instance.stop()
            else:
                self.root.destroy() # Just destroy the GUI if server instance is not linked


class CentralServer:
    """Central server that receives data from drones and displays it"""

    def __init__(self, listen_ip="127.0.0.1", listen_port=3500):
        # Initialize GUI
        self.root = tk.Tk()
        self.gui = ServerGUI(self.root)
        self.gui.server_instance = self # Link GUI back to server instance

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

