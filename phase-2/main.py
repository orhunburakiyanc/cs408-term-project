#!/usr/bin/env python3
"""
Main launcher script for the environmental monitoring system.
This script can launch the drone server and multiple sensor nodes.
"""

import argparse
import subprocess
import time
import os
import signal
import sys

# Default configuration
DEFAULT_DRONE_IP = "127.0.0.1"
DEFAULT_DRONE_PORT = 3400
DEFAULT_SERVER_IP = "127.0.0.1"
DEFAULT_SERVER_PORT = 3500
DEFAULT_NUM_SENSORS = 5
DEFAULT_DATA_INTERVAL = 5  # seconds between sensor readings

# Keep track of all processes
processes = []

def signal_handler(sig, frame):
    """Handle Ctrl+C to gracefully terminate all child processes"""
    print("\nShutting down all processes...")
    for process in processes:
        if process.poll() is None:  # If process is still running
            try:
                # Send SIGINT (equivalent to Ctrl+C)
                if os.name == 'nt':  # Windows
                    process.terminate()
                else:  # Unix/Linux/Mac
                    os.kill(process.pid, signal.SIGINT)
                print(f"Sent termination signal to process {process.pid}")
            except:
                pass
    
    print("Exiting...")
    sys.exit(0)

def start_drone_server(drone_ip, drone_port, server_ip, server_port):
    """Start the drone server process"""
    print(f"Starting drone server on {drone_ip}:{drone_port}, connecting to central server at {server_ip}:{server_port}")
    
    # The command assumes DroneServer.py is in the current directory
    cmd = [
        sys.executable,  # Use the current Python interpreter
        "drone_server.py",
        "--listen-ip", drone_ip,
        "--listen-port", str(drone_port),
        "--server-ip", server_ip,
        "--server-port", str(server_port)
    ]
    
    process = subprocess.Popen(cmd)
    processes.append(process)
    return process

def start_sensor_node(sensor_id, drone_ip, drone_port, interval):
    """Start a sensor node process"""
    print(f"Starting sensor node {sensor_id}, connecting to drone at {drone_ip}:{drone_port}")
    
    # The command assumes SensorNode.py is in the current directory
    cmd = [
        sys.executable,  # Use the current Python interpreter
        "nodes.py",
        "--id", f"sensor_{sensor_id:02d}",
        "--ip", drone_ip,
        "--port", str(drone_port),
        "--interval", str(interval)
    ]
    
    process = subprocess.Popen(cmd)
    processes.append(process)
    return process

def main():
    parser = argparse.ArgumentParser(description='Start the environmental monitoring system')
    
    # System configuration
    parser.add_argument('--mode', choices=['all', 'drone', 'sensors'], default='all',
                        help='Components to start: all, drone only, or sensors only')
    
    # Drone server configuration
    parser.add_argument('--drone-ip', default=DEFAULT_DRONE_IP,
                        help=f'IP address for the drone server to listen on (default: {DEFAULT_DRONE_IP})')
    parser.add_argument('--drone-port', type=int, default=DEFAULT_DRONE_PORT,
                        help=f'Port for the drone server to listen on (default: {DEFAULT_DRONE_PORT})')
    
    # Central server configuration
    parser.add_argument('--server-ip', default=DEFAULT_SERVER_IP,
                        help=f'IP address of the central server (default: {DEFAULT_SERVER_IP})')
    parser.add_argument('--server-port', type=int, default=DEFAULT_SERVER_PORT,
                        help=f'Port of the central server (default: {DEFAULT_SERVER_PORT})')
    
    # Sensor nodes configuration
    parser.add_argument('--num-sensors', type=int, default=DEFAULT_NUM_SENSORS,
                        help=f'Number of sensor nodes to start (default: {DEFAULT_NUM_SENSORS})')
    parser.add_argument('--interval', type=int, default=DEFAULT_DATA_INTERVAL,
                        help=f'Interval between sensor readings in seconds (default: {DEFAULT_DATA_INTERVAL})')
    
    args = parser.parse_args()
    
    # Register signal handler for Ctrl+C
    signal.signal(signal.SIGINT, signal_handler)
    
    # Start drone server if requested
    if args.mode in ['all', 'drone']:
        drone_process = start_drone_server(
            args.drone_ip, args.drone_port, args.server_ip, args.server_port)
        
        # Give the drone server time to initialize before starting sensors
        if args.mode == 'all':
            print("Waiting for drone server to initialize...")
            time.sleep(3)
    
    # Start sensor nodes if requested
    if args.mode in ['all', 'sensors']:
        for i in range(1, args.num_sensors + 1):
            sensor_process = start_sensor_node(
                i, args.drone_ip, args.drone_port, args.interval)
            # Small delay between starting sensors to avoid race conditions
            time.sleep(0.5)
    
    print("\nAll components started. Press Ctrl+C to shutdown.")
    
    # Keep the main process running until Ctrl+C
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        signal_handler(signal.SIGINT, None)

if __name__ == "__main__":
    main()