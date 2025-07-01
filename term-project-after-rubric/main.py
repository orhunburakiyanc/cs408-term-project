#!/usr/bin/env python3
"""
Main launcher script for the environmental monitoring system using threads.
This script launches the central server, drone server, and multiple sensor nodes using subprocesses and threading.
"""

import argparse
import subprocess
import time
import os
import signal
import sys
import threading

# Default configuration
DEFAULT_DRONE_IP = "127.0.0.1"
DEFAULT_DRONE_PORT = 3400
DEFAULT_CENTRAL_IP = "127.0.0.1"
DEFAULT_CENTRAL_PORT = 3500
DEFAULT_NUM_SENSORS = 5
DEFAULT_MIN_DATA_INTERVAL = 4
DEFAULT_MAX_DATA_INTERVAL = 6

# Global list to keep track of subprocesses
processes = []
process_lock = threading.Lock()


def signal_handler(sig, frame):
    #Handle Ctrl+C to gracefully terminate all child processes
    print("\nShutting down all processes...")
    with process_lock:
        for process in processes:
            if process.poll() is None:
                try:
                    if os.name == 'nt':
                        process.terminate()
                    else:
                        os.kill(process.pid, signal.SIGINT)
                    print(f"Sent termination signal to process {process.pid}")
                except ProcessLookupError:
                    pass
                except Exception as e:
                    print(f"Error sending termination signal to process {process.pid}: {e}")
        time.sleep(1)
        for process in processes:
            if process.poll() is None:
                try:
                    process.kill()
                    print(f"Force killed process {process.pid}")
                except ProcessLookupError:
                    pass
                except Exception as e:
                    print(f"Error force killing process {process.pid}: {e}")
    print("Exiting main launcher.")
    sys.exit(0)


def launch_process(cmd, label):
    #Generic function to launch a subprocess and track it
    try:
        process = subprocess.Popen(cmd)
        with process_lock:
            processes.append(process)
        print(f"{label} started with PID: {process.pid}")
        return process
    except FileNotFoundError:
        print(f"Error: {cmd[1]} not found. Ensure it's in the same directory.")
        sys.exit(1)
    except Exception as e:
        print(f"Error starting {label}: {e}")
        sys.exit(1)


def start_central_server(ip, port):
    cmd = [sys.executable, "central_server.py", "--ip", ip, "--port", str(port)]
    return launch_process(cmd, "Central server")


def start_drone_server(drone_ip, drone_port, server_ip, server_port):
    cmd = [sys.executable, "drone_server.py", "--listen-ip", drone_ip, "--listen-port", str(drone_port),
           "--server-ip", server_ip, "--server-port", str(server_port)]
    return launch_process(cmd, "Drone server")

def start_sensor_node(sensor_id, drone_ip, drone_port, min_interval, max_interval):
    cmd = [sys.executable, "nodes.py", "--id", f"sensor_{sensor_id:02d}", "--ip", drone_ip,
           "--port", str(drone_port), "--min-interval", str(min_interval), "--max-interval", str(max_interval)]
    return launch_process(cmd, f"Sensor node {sensor_id:02d}")


def threaded_launcher(target, args=()):
    t = threading.Thread(target=target, args=args)
    t.start()
    return t


def main():
    parser = argparse.ArgumentParser(description='Start the environmental monitoring system')

    parser.add_argument('--mode', choices=['all', 'central', 'drone', 'sensors'], default='all',help='Components to start: all, central server only, drone only, or sensors only')
    parser.add_argument('--central-ip', default=DEFAULT_CENTRAL_IP)
    parser.add_argument('--central-port', type=int, default=DEFAULT_CENTRAL_PORT)
    parser.add_argument('--drone-ip', default=DEFAULT_DRONE_IP)
    parser.add_argument('--drone-port', type=int, default=DEFAULT_DRONE_PORT)
    parser.add_argument('--num-sensors', type=int, default=DEFAULT_NUM_SENSORS)
    parser.add_argument('--min-interval', type=float, default=DEFAULT_MIN_DATA_INTERVAL, help='Minimum sensor data interval')
    parser.add_argument('--max-interval', type=float, default=DEFAULT_MAX_DATA_INTERVAL, help='Maximum sensor data interval')

    args = parser.parse_args()
    signal.signal(signal.SIGINT, signal_handler)

    threads = []

    if args.mode in ['all', 'central']:
        threads.append(threaded_launcher(start_central_server, (args.central_ip, args.central_port)))
        time.sleep(2)

    if args.mode in ['all', 'drone']:
        threads.append(threaded_launcher(start_drone_server, (args.drone_ip, args.drone_port,
                                                              args.central_ip, args.central_port)))
        if args.mode == 'all' or args.mode == 'sensors':
            time.sleep(2)

    if args.mode in ['all', 'sensors']:
        for i in range(1, args.num_sensors + 1):
            if i <= 2:
                min_iv, max_iv = 2, 3  # hızlı sensörler
            else:
                min_iv, max_iv = 5, 8  # yavaş sensörler

            threads.append(threaded_launcher(
                start_sensor_node,
                (i, args.drone_ip, args.drone_port, min_iv, max_iv)
            ))
            time.sleep(1)


    print("\nAll requested components started. Press Ctrl+C to shut down.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        signal_handler(None, None)


if __name__ == "__main__":
    main()