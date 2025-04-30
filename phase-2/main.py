#!/usr/bin/env python3
"""
Main launcher script for the environmental monitoring system.
This script can launch the central server, drone server, and multiple sensor nodes.
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
DEFAULT_CENTRAL_IP = "127.0.0.1"
DEFAULT_CENTRAL_PORT = 3500
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
                    process.terminate() # Use terminate for Windows
                else:  # Unix/Linux/Mac
                    os.kill(process.pid, signal.SIGINT) # Use os.kill for Unix-like systems
                print(f"Sent termination signal to process {process.pid}")
            except ProcessLookupError:
                 # Process already exited
                 pass
            except Exception as e:
                print(f"Error sending termination signal to process {process.pid}: {e}")

    # Give processes a moment to shut down
    time.sleep(1)

    # Force kill any processes that didn't respond to SIGINT/terminate
    for process in processes:
         if process.poll() is None:
             try:
                 process.kill()
                 print(f"Force killed process {process.pid}")
             except ProcessLookupError:
                  pass # Process already exited
             except Exception as e:
                  print(f"Error force killing process {process.pid}: {e}")

    print("Exiting main launcher.")
    sys.exit(0)


def start_central_server(server_ip, server_port):
    """Start the central server process"""
    print(f"Starting central server on {server_ip}:{server_port}")

    # Command to run central_server.py
    # Using --ip and --port as defined in central_server.py's argparse
    cmd = [
        sys.executable,  # Use the current Python interpreter
        "central_server.py",
        "--ip", server_ip,
        "--port", str(server_port)
    ]

    try:
        process = subprocess.Popen(cmd)
        processes.append(process)
        print(f"Central server process started with PID: {process.pid}")
        return process
    except FileNotFoundError:
        print(f"Error: central_server.py not found. Ensure it's in the same directory.")
        sys.exit(1)
    except Exception as e:
        print(f"Error starting central server process: {e}")
        sys.exit(1)


def start_drone_server(drone_ip, drone_port, server_ip, server_port):
    """Start the drone server process"""
    print(f"Starting drone server on {drone_ip}:{drone_port}, connecting to central server at {server_ip}:{server_port}")

    # Command to run drone_server.py
    # Assuming drone_server.py accepts these arguments
    cmd = [
        sys.executable,  # Use the current Python interpreter
        "drone_server.py",
        "--listen-ip", drone_ip,
        "--listen-port", str(drone_port),
        "--server-ip", server_ip,
        "--server-port", str(server_port)
    ]

    try:
        process = subprocess.Popen(cmd)
        processes.append(process)
        print(f"Drone server process started with PID: {process.pid}")
        return process
    except FileNotFoundError:
        print(f"Error: drone_server.py not found. Ensure it's in the same directory.")
        sys.exit(1)
    except Exception as e:
        print(f"Error starting drone server process: {e}")
        sys.exit(1)


def start_sensor_node(sensor_id, drone_ip, drone_port, interval):
    """Start a sensor node process"""
    print(f"Starting sensor node {sensor_id}, connecting to drone at {drone_ip}:{drone_port}")

    # Command to run nodes.py
    # Assuming nodes.py accepts these arguments
    cmd = [
        sys.executable,  # Use the current Python interpreter
        "nodes.py",
        "--id", f"sensor_{sensor_id:02d}",
        "--ip", drone_ip,
        "--port", str(drone_port),
        "--interval", str(interval)
    ]

    try:
        process = subprocess.Popen(cmd)
        processes.append(process)
        print(f"Sensor node process sensor_{sensor_id:02d} started with PID: {process.pid}")
        return process
    except FileNotFoundError:
        print(f"Error: nodes.py not found. Ensure it's in the same directory.")
        sys.exit(1)
    except Exception as e:
        print(f"Error starting sensor node process sensor_{sensor_id:02d}: {e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description='Start the environmental monitoring system')

    # System configuration
    parser.add_argument('--mode', choices=['all', 'central', 'drone', 'sensors'], default='all',
                        help='Components to start: all, central server only, drone only, or sensors only')

    # Central server configuration
    parser.add_argument('--central-ip', default=DEFAULT_CENTRAL_IP,
                        help=f'IP address for the central server to listen on (default: {DEFAULT_CENTRAL_IP})')
    parser.add_argument('--central-port', type=int, default=DEFAULT_CENTRAL_PORT,
                        help=f'Port for the central server to listen on (default: {DEFAULT_CENTRAL_PORT})')

    # Drone server configuration
    parser.add_argument('--drone-ip', default=DEFAULT_DRONE_IP,
                        help=f'IP address for the drone server to listen on (default: {DEFAULT_DRONE_IP})')
    parser.add_argument('--drone-port', type=int, default=DEFAULT_DRONE_PORT,
                        help=f'Port for the drone server to listen on (default: {DEFAULT_DRONE_PORT})')

    # Sensor nodes configuration
    parser.add_argument('--num-sensors', type=int, default=DEFAULT_NUM_SENSORS,
                        help=f'Number of sensor nodes to start (default: {DEFAULT_NUM_SENSORS})')
    parser.add_argument('--interval', type=int, default=DEFAULT_DATA_INTERVAL,
                        help=f'Interval between sensor readings in seconds (default: {DEFAULT_DATA_INTERVAL})')

    args = parser.parse_args()

    # Register signal handler for Ctrl+C
    signal.signal(signal.SIGINT, signal_handler)

    # Start central server if requested
    if args.mode in ['all', 'central']:
        central_process = start_central_server(args.central_ip, args.central_port)

        # Give the central server time to initialize before starting drone server
        print("Waiting for central server to initialize...")
        time.sleep(2)

    # Start drone server if requested
    if args.mode in ['all', 'drone']:
        drone_process = start_drone_server(
            args.drone_ip, args.drone_port, args.central_ip, args.central_port)

        # Give the drone server time to initialize before starting sensors
        # Only wait if we are also starting sensors in this run
        if args.mode == 'all' or args.mode == 'sensors':
            print("Waiting for drone server to initialize...")
            time.sleep(2)

    # Start sensor nodes if requested
    if args.mode in ['all', 'sensors']:
        for i in range(1, args.num_sensors + 1):
            sensor_process = start_sensor_node(
                i, args.drone_ip, args.drone_port, args.interval)
            # Small delay between starting sensors to avoid race conditions
            time.sleep(0.5)

    print("\nAll requested components started. Press Ctrl+C to shutdown.")

    # Keep the main process running until Ctrl+C
    # The signal handler will take care of exiting
    while True:
        time.sleep(1)


if __name__ == "__main__":
    main()
