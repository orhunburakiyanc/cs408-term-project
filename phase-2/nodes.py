import json
import socket
import time
import random
import datetime
import logging
from threading import Thread, Timer

class SensorNode:
    """
    Sensor Node class that simulates environmental data collection and transmits
    to a drone via TCP connection. Includes simulation of random failures and self-healing.
    """

    def __init__(self, sensor_id, drone_ip, drone_port,
                 failure_probability=0.005, repair_time=5, min_interval=1, max_interval=2):
        """
        Initialize the SensorNode with configuration parameters.

        Args:
            sensor_id (str): Unique identifier for this sensor
            drone_ip (str): IP address of the drone to connect to
            drone_port (int): Port number for the drone connection
            failure_probability (float): Probability of a failure occurring per cycle (0-1)
            repair_time (int): Fixed repair time in seconds
            min_interval (int): Minimum data send interval in seconds
            max_interval (int): Maximum data send interval in seconds
        """
        self.sensor_id = sensor_id
        self.drone_ip = drone_ip
        self.drone_port = drone_port        
        self.send_interval = random.uniform(min_interval, max_interval)
        self.socket = None
        self.connected = False
        self.running = False

        # Failure simulation parameters
        self.failure_probability = failure_probability
        self.repair_time = repair_time
        self.is_broken = False
        self.repair_timer = None

        # Configure logging
        logging.basicConfig(
            level=logging.INFO,
            format=f'[{self.sensor_id}] %(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(self.sensor_id)

    def connect_to_drone(self):
        """
        Establish TCP connection with the drone server.

        Returns:
            bool: True if connection was successful, False otherwise
        """
        if self.is_broken:
            self.logger.warning("Cannot connect: sensor is currently broken")
            return False

        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.drone_ip, self.drone_port))
            self.connected = True
            self.logger.info(f"Connected to drone at {self.drone_ip}:{self.drone_port}")
            return True
        except socket.error as e:
            self.connected = False
            self.logger.error(f"Failed to connect to drone: {e}")
            return False

    def collect_environmental_data(self):
        """
        Simulate collecting temperature and humidity data.

        Returns:
            dict: JSON-compatible dictionary with sensor readings
        """
        if self.is_broken:
            self.logger.warning("Cannot collect data: sensor is currently broken")
            return None

        # Simulate temperature data (20-30°C with occasional anomalies)
        temperature = random.uniform(20.0, 30.0)

        # Occasionally generate anomalous temperature readings (1% chance)
        if random.random() < 0.05:
            temperature = random.uniform(90.0, 1000.0)  # Anomalously high temperature

        humidity = random.uniform(30.0, 60.0)
        # Simulate humidity data (30-60%)

        # Occasionally generate anomalous humidity readings (1% chance)
        if random.random() < 0.01:
            humidity = random.uniform(80.0, 1000.0)  # Anomalously high humidity

        # Create timestamp in ISO 8601 format
        timestamp = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")

        data = {
            "sensor_id": self.sensor_id,
            "timestamp": timestamp,
            "temperature": round(temperature, 1),
            "humidity": round(humidity, 1)
        }

        self.logger.debug(f"Collected data: {data}")
        return data

    def send_data(self, data):
        """
        Send the collected data to the drone.

        Args:
            data (dict): Sensor data to send

        Returns:
            bool: True if data was sent successfully, False otherwise
        """
        if self.is_broken:
            self.logger.warning("Cannot send data: sensor is currently broken")
            return False

        if not self.connected:
            self.logger.warning("Not connected to drone. Cannot send data.")
            return False

        try:
            json_data = json.dumps(data)
            self.socket.sendall((json_data + "\n").encode('utf-8'))
            self.logger.info(f"Sent data: Temperature={data['temperature']}°C, Humidity={data['humidity']}%")
            return True
        except socket.error as e:
            self.connected = False
            self.logger.error(f"Error sending data: {e}")
            return False

    def handle_reconnection(self):
        """
        Handle reconnection attempts when connection to the drone is lost.

        Returns:
            bool: True if reconnection was successful, False otherwise
        """
        if self.is_broken:
            self.logger.warning("Cannot reconnect: sensor is currently broken")
            return False

        self.logger.info("Attempting to reconnect to drone...")

        # Close the current socket if it exists
        if self.socket:
            try:
                self.socket.close()
            except:
                pass

        # Attempt to reconnect
        max_attempts = 5
        current_attempt = 0

        while current_attempt < max_attempts and self.running and not self.is_broken:
            current_attempt += 1
            self.logger.info(f"Reconnection attempt {current_attempt}/{max_attempts}")

            if self.connect_to_drone():
                self.logger.info("Reconnection successful")
                return True

            # Wait before next attempt with exponential backoff
            wait_time = 2 ** current_attempt
            self.logger.info(f"Waiting {wait_time} seconds before next attempt...")
            time.sleep(wait_time)

        self.logger.error("Failed to reconnect after multiple attempts")
        return False

    def simulate_failure(self):
        """
        Simulate a random sensor failure with a fixed repair time.
        """
        if not self.is_broken and random.random() < self.failure_probability:
            self.is_broken = True

            # Close connection if any
            if self.socket:
                try:
                    self.socket.close()
                    self.connected = False
                except:
                    pass

            self.logger.error(f"SENSOR FAILURE: Node has broken down! Will be offline for {self.repair_time} seconds")

            # Schedule the repair after the repair time
            self.repair_timer = Timer(self.repair_time, self.repair_sensor)
            self.repair_timer.daemon = True
            self.repair_timer.start()

    def repair_sensor(self):
        """
        Simulate the sensor being repaired.
        """
        if self.is_broken:
            self.is_broken = False
            self.logger.info("SENSOR REPAIRED: Node is now functional again")

    def run(self):
        """
        Main loop for the sensor node operation.
        """
        self.running = True

        if not self.connect_to_drone():
            self.logger.error("Initial connection failed. Attempting reconnection...")
            if not self.handle_reconnection():
                self.logger.error("Could not establish connection. Exiting.")
                return

        try:
            while self.running:
                # Check if sensor should randomly fail
                self.simulate_failure()


                if not self.connected and not self.handle_reconnection():
                    time.sleep(10)  # Wait before trying again
                    continue

                data = self.collect_environmental_data()
                if data and not self.send_data(data):
                    continue  # Will trigger reconnection on next loop

                time.sleep(self.send_interval)

        except KeyboardInterrupt:
            self.logger.info("Keyboard interrupt received. Shutting down...")
        finally:
            self.stop()

    def stop(self):
        """
        Stop the sensor node and clean up resources.
        """
        self.running = False
        if self.repair_timer:
            self.repair_timer.cancel()
        if self.socket:
            try:
                self.socket.close()
                self.logger.info("Socket closed")
            except:
                pass
        self.logger.info("Sensor node stopped")


def main():
    """
    Main function to run when the script is executed directly.
    """
    import argparse

    parser = argparse.ArgumentParser(description='Start a sensor node')
    parser.add_argument('--id', type=str, default='sensor_01', help='Sensor ID')
    parser.add_argument('--ip', type=str, default='127.0.0.1', help='Drone IP address')
    parser.add_argument('--port', type=int, default=3400, help='Drone port')    
    parser.add_argument('--failure-rate', type=float, default=0.005,
                        help='Probability of failure per cycle (0-1)')
    parser.add_argument('--repair-time', type=int, default=5,
                        help='Fixed repair time in seconds')
    parser.add_argument('--min-interval', type=float, default=1,
                        help='Minimum data sending interval in seconds')
    parser.add_argument('--max-interval', type=float, default=2,
                        help='Maximum data sending interval in seconds')

    args = parser.parse_args()

    sensor = SensorNode(
        args.id,
        args.ip,
        args.port,
        args.failure_rate,
        args.repair_time,
        args.min_interval,
        args.max_interval
    )

    print(f"Starting sensor node {args.id}...")
    print(f"Connecting to drone at {args.ip}:{args.port}")
    print(f"Data sending interval: will be random between {args.min_interval} and {args.max_interval} seconds")
    print(f"Failure simulation: {args.failure_rate*100}% chance per cycle")
    print(f"Fixed repair time: {args.repair_time} seconds")
    print("Press Ctrl+C to stop")

    sensor.run()


if __name__ == "__main__":
    main()