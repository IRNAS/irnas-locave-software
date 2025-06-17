import argparse
import re
import signal
import threading
import time

import requests
import serial
from flask import Flask, jsonify, request, send_from_directory
from sliplib.slip import Driver
from telegram.error import InvalidToken

from telegram_bot.bot import LoCaveTelegramBot

printable = re.compile(r"[^\x20-\x7E]")


class ProtocolSerialBridge:
    """A serial communication bridge for LoCave communication system.

    A serial communication bridge for managing a custom network protocol over UART,
    integrating node communication, BLE data, and Telegram bot support.

    This class handles encoding/decoding of messages, managing node status, processing
    BLE scan data, broadcasting messages, and relaying data to/from a Telegram bot. It
    supports periodic weather data broadcasting, node pinging, and message sequencing
    with SLIP framing and CRC8 verification.
    """

    def __init__(self, port, baud_rate=115200):
        """Initialize the ProtocolSerialBridge for serial communication and messaging.

        This constructor sets up a serial connection, configures internal constants
        for protocol operation, initializes state tracking (messages, BLE scans,
        status), and launches background threads for data reception, weather updates,
        Telegram bot handling, and periodic broadcast pings.

        Args:
            port (str): Serial port to which the bridge hardware is connected.
            baud_rate (int, optional): Baud rate for serial communication. Defaults to 115200.
        """
        self.send_port = port
        self.baud_rate = baud_rate
        self.ser_send = serial.Serial(port, baud_rate)
        self.running = True

        # Message types
        self.BROADCAST_ADDRESS = 255
        self.TELEGRAM_ADDRESS = 254

        self.DATA_TYPE = 0
        self.ACK_TYPE = 1
        self.HELLO_TYPE = 2
        self.PING_RESPONSE_TYPE = 254
        self.PING_TYPE = 255
        self.STATUS_TYPE = 3
        self.BLE_SCAN_RESULT_TYPE = 4
        self.BASE_CONFIRM_TYPE = 5

        # Interface types
        self.INTERFACE_NAMES = {
            0: "CAVE",
            1: "EXIT",
            2: "RF",
            3: "ALL",
        }

        self._load_sequence()

        # Initialize SLIP driver
        self.driver = Driver()

        # Add ping response tracking
        self.ping_responses = {}
        self.ping_lock = threading.Lock()  # Thread-safe access to ping_responses

        # Add message history
        self.messages = []
        self.messages_lock = threading.Lock()
        self.MAX_MESSAGES = 200

        # add ble mac list - for each node: dict{node:dict{device_id:last_seen_timestamp}}
        self.ble_id_list = {}

        self.BUFFER_SIZE = 100
        self.HEADER_SIZE = 8

        # Add neighbor status tracking
        self.status = {}

        # Start receive thread
        self.receive_thread = threading.Thread(target=self._receive_loop)
        self.receive_thread.daemon = True
        self.receive_thread.start()

        # Add ping sweep thread
        # self.ping_sweep_thread = threading.Thread(target=self._ping_sweep_loop)
        # self.ping_sweep_thread.daemon = True
        # self.ping_sweep_thread.start()

        # Add broadcast ping thread
        self.broadcast_ping_thread = threading.Thread(
            target=self._broadcast_ping_loop,
        )
        self.broadcast_ping_thread.daemon = True
        self.broadcast_ping_thread.start()

        self.weather_thread = threading.Thread(target=self._send_weather_data)
        self.weather_thread.daemon = True
        self.weather_thread.start()

        # add telegram bot
        self.bot = LoCaveTelegramBot()

        self.forward_from_telegram_thread = threading.Thread(
            target=self._forward_from_telegram
        )
        self.forward_from_telegram_thread.daemon = True
        self.forward_from_telegram_thread.start()

    def crc8(self, data):
        """Calculate crc8 checksum for data."""
        crc = 0x00
        for byte in data:
            extract = byte
            for _ in range(8):
                sum = (crc ^ extract) & 0x01
                crc >>= 1
                if sum:
                    crc ^= 0x8C
                extract >>= 1
        return crc

    # Read sequence number
    def _load_sequence(self, file_path=".sequence"):
        try:
            with open(file_path, "r") as f:
                self.sequence_number = int(f.read().strip())
        except (FileNotFoundError, ValueError):
            self.sequence_number = 0

    # Save sequence number
    def _save_sequence(self, file_path=".sequence"):
        with open(file_path, "w+") as f:
            f.write(str(self.sequence_number))

    def _receive_loop(self):
        while self.running:
            try:
                if not self.ser_send or not self.ser_send.is_open:
                    self._reconnect_serial()
                    time.sleep(1)
                    continue
                while self.ser_send.in_waiting:
                    while (message := self.driver.get(block=False)) is None:
                        data = self.ser_send.read(1)
                        # print("data: ", data)
                        self.driver.receive(data)
                    if message == b"":
                        pass
                    elif len(message) < self.HEADER_SIZE:
                        pass
                    else:
                        # split message into header and payload
                        # print("message: ", message)
                        header = message[: self.HEADER_SIZE]
                        payload = message[self.HEADER_SIZE :]
                        l2_crc, l2_sender, source, dest, ttl, seq, msg_type, length = (
                            header
                        )
                        if self.crc8(message[1:]) != l2_crc:
                            print("CRC error")
                            continue
                        self._process_message(
                            l2_sender, l2_crc, source, dest, ttl, seq, msg_type, payload
                        )
            except (serial.SerialException, OSError) as e:
                print(f"[Serial Error] Lost connection: {e}")
                self.ser_send.close()
                time.sleep(1)
            except Exception as e:
                print(f"[Receive Loop Error] {e}")
            time.sleep(0.01)

    def _reconnect_serial(self):
        while self.running:
            try:
                print(f"Attempting to reconnect to {self.send_port}...")
                self.ser_send = serial.Serial(self.send_port, self.baud_rate, timeout=1)
                print("Serial reconnected successfully.")
                return
            except (serial.SerialException, OSError) as e:
                print(f"Reconnect failed: {e}")
                time.sleep(2)  # wait before retrying

    def _process_message(
        self,
        l2_sender,
        l2_reserved,
        source,
        dest,
        ttl,
        seq,
        msg_type,
        data,
    ):
        print(
            f"RX: source={source}, "
            f"l2_sender={l2_sender}, "
            f"dest={dest}, ttl={ttl}, "
            f"seq={seq}, type={msg_type}, "
            f"length={len(data)}, "
            f"payload={printable.sub('', data.decode(errors='replace'))}"
        )

        # update last seen on anz message, not just ping lock
        with self.ping_lock:
            self.ping_responses[source] = {"last_seen": time.time(), "ttl": ttl}
        if msg_type == self.PING_RESPONSE_TYPE:
            pass
            # print(f"Received ping response from node {source}")
        elif msg_type == self.DATA_TYPE:
            with self.messages_lock:
                self.messages.append(
                    {
                        "timestamp": time.time(),
                        "source": source,
                        "dest": dest,
                        "type": "received",
                        "content": printable.sub("", data.decode()),
                    }
                )
                # Keep only last 100 messages
                if len(self.messages) > self.MAX_MESSAGES:
                    self.messages.pop(0)
            print(f"Received data from node {source}: {data.decode()}")
            self.bot.send_to_telegram(f"{source}: {data.decode()}")
            self._send_message(
                dest=source,
                msg_type=self.BASE_CONFIRM_TYPE,
                payload=str(seq),
            )
        elif msg_type == self.BLE_SCAN_RESULT_TYPE:
            print(f"received BLE scan results from{source}")
            if source not in self.ble_id_list:
                self.ble_id_list[source] = {}
            now = time.time()
            for i in range(1, len(data), 2):
                id = (data[i - 1] << 8) + data[i]
                self.ble_id_list[source][id] = now
            self.ble_id_list[source]
        elif msg_type == self.STATUS_TYPE:
            # print(f"Received status from node {source}")
            neighbors = []
            # Parse neighbor data in format: "interface:node:ttl:rssi,interface:node:ttl:rssi"
            msg_data = data.decode().strip().split(";")
            weather_data = None
            neighbor_data = msg_data[0]
            if len(msg_data) > 1:
                weather_data = msg_data[1].split(",")  # temp, humidity
            neighbor_entries = neighbor_data.split(",")
            for entry in neighbor_entries:
                if not entry:
                    continue
                try:
                    node_id, interface, rssi = entry.split(":")
                    interface_num = int(interface)
                    interface_name = self.INTERFACE_NAMES.get(
                        interface_num, f"UNKNOWN_{interface_num}"
                    )
                    neighbors.append([int(node_id), interface_name, int(rssi)])
                except (ValueError, IndexError) as e:
                    print(f"Error parsing neighbor entry '{entry}': {e}")
                    continue

            if self.status.get(source) is None:
                self.status[source] = {}

            self.status[source].update(
                {
                    "timestamp": time.time(),
                    "neighbors": neighbors,
                }
            )
            if weather_data is not None:
                self.status[source]["weather"] = weather_data
            # print(f"Node {source} neighbors: {neighbors}")

    def _send_message(self, dest, msg_type, payload="", ttl=25, source=0):
        # increment sequence number
        self.sequence_number = (self.sequence_number + 1) % 256  # Wrap around at 256
        self._save_sequence()

        # Create message structure matching the Arduino implementation
        message = bytearray(
            [
                0,  # l2 crc
                0,  # l2 sender is 0 for bridge
                source,
                dest,
                ttl,
                self.sequence_number,  # Use current sequence number
                msg_type,
                len(payload),
            ]
        )
        message.extend(payload.encode())
        message[0] = self.crc8(message[1:])

        packet = self.driver.send(message)
        try:
            if self.ser_send and self.ser_send.is_open:
                self.ser_send.write(packet)
        except (serial.SerialException, OSError) as e:
            print(f"[Serial Write Error] {e}")
            try:
                self.ser_send.close()
            except Exception as e:
                print("Serial send error!")

        # Store sent messages (only for DATA_TYPE)
        if msg_type == self.DATA_TYPE:
            with self.messages_lock:
                self.messages.append(
                    {
                        "timestamp": time.time(),
                        "source": source,  # Bridge is always 0
                        "dest": dest,
                        "type": "sent" if source == 0 else "received",
                        "content": payload,
                    }
                )
                if len(self.messages) > self.MAX_MESSAGES:
                    self.messages.pop(0)

    def ping(self, destination):
        """Ping destination node."""
        self._send_message(destination, self.HELLO_TYPE)

    def broadcast(self, message):
        """Broadcast message to all nodes in network."""
        self.bot.send_to_telegram(f"0 : {message}")
        self._send_message(self.BROADCAST_ADDRESS, self.DATA_TYPE, message)

    def get_ble_results(self, node):
        """Retrieve BLE scan results for specified node."""
        # Initialize empty list if node doesn't exist
        if node not in self.ble_id_list:
            self.ble_id_list[node] = {}

        temp_array = []
        now = time.time()
        for id, t in sorted(self.ble_id_list[node].items()):
            temp_array.append({"id": id, "timestamp": int(now - t)})
        return temp_array

    def _send_weather_data(self):
        interval = 300  # total wait time in seconds
        check_interval = 1  # check every 1 second
        waited = 0

        while self.running:
            try:
                r = requests.get(
                    "https://api.open-meteo.com/v1/forecast?latitude=52.52&longitude=13.41&current=temperature_2m,wind_speed_10m&hourly=temperature_2m,relative_humidity_2m,wind_speed_10m"
                )
                data = r.json()
                self.broadcast(str(data["current"]))
            except Exception as e:
                print("weather data error:", e)

            waited = 0
            while self.running and waited < interval:
                time.sleep(check_interval)
                waited += check_interval

    def _forward_from_telegram(self):
        while True:
            while not self.bot.rx_empty():
                msg = str(self.bot.pop_rx())
                self._send_message(
                    self.BROADCAST_ADDRESS,
                    self.DATA_TYPE,
                    msg,
                    source=self.TELEGRAM_ADDRESS,
                )
                time.sleep(0.1)
            time.sleep(1)

    def _ping_sweep_loop(self):
        while self.running:
            for node in range(1, 101):  # Ping nodes 1-100
                if not self.running:  # Check if we should stop
                    break
                self.ping(node)
                time.sleep(0.01)  # 10ms delay between pings
            time.sleep(10)  # Wait 10 seconds before next sweep

    def _broadcast_ping_loop(self):
        while self.running:
            # Send ping to broadcast address (255)
            self.ping(self.BROADCAST_ADDRESS)
            time.sleep(5)  # Wait 10 seconds before next broadcast ping

    def close(self):
        """Gracefully shutdown the ProtocolSerialBridge."""
        self.running = False
        try:
            self.bot.stop()
        except:  # noqa: E722
            pass
        self.receive_thread.join()
        self.weather_thread.join()
        if hasattr(self, "ping_sweep_thread"):
            self.ping_sweep_thread.join()
        self.broadcast_ping_thread.join()
        self.ser_send.close()


# Flask REST API
app = Flask(__name__, static_folder="flash-ui/out", static_url_path="")
bridge = None


@app.route("/")
def serve_ui():
    """Serve WEB UI."""
    return send_from_directory(app.static_folder, "index.html")


@app.route("/ping/<int:dest>", methods=["POST"])
def ping_node(dest):
    """Ping the specified node."""
    bridge.ping(dest)
    return jsonify({"status": "success", "message": f"Ping sent to node {dest}"})


@app.route("/broadcast", methods=["POST"])
def broadcast_message():
    """Broadcast message to all nodes in network."""
    message = request.json.get("message", "")
    bridge.broadcast(message)
    return jsonify({"status": "success", "message": "Broadcast sent"})


@app.route("/ble_results/<int:node>", methods=["GET"])
def get_ble_results(node):
    """Get ble results for specified node."""
    return jsonify(bridge.get_ble_results(node))


@app.route("/nodes", methods=["GET"])
def get_nodes():
    """Get a list of all nodes."""
    current_time = time.time()
    with bridge.ping_lock:
        nodes = {
            node: {
                "last_seen": data["last_seen"],
                "seconds_ago": int(current_time - data["last_seen"]),
                "ttl": data["ttl"],
            }
            for node, data in bridge.ping_responses.items()
        }
    return jsonify(nodes)


@app.route("/messages", methods=["GET"])
def get_messages():
    """Get all messages currently stored on base.

    Returns json array:
    [
        {
            "timestamp": msg["timestamp"],
            "seconds_ago": int(current_time - msg["timestamp"]),
            "source": msg["source"],
            "dest": msg["dest"],
            "type": msg["type"],
            "content": msg["content"],
        }
    ]
    """
    current_time = time.time()
    with bridge.messages_lock:
        messages = [
            {
                "timestamp": msg["timestamp"],
                "seconds_ago": int(current_time - msg["timestamp"]),
                "source": msg["source"],
                "dest": msg["dest"],
                "type": msg["type"],
                "content": msg["content"],
            }
            for msg in bridge.messages
        ]
    return jsonify(messages)


@app.route("/topology", methods=["GET"])
def get_topology():
    """Get all topology data for all nodes."""
    current_time = time.time()
    topology = {
        node: {
            "timestamp": data["timestamp"],
            "seconds_ago": int(current_time - data["timestamp"]),
            "neighbors": data["neighbors"],
            "weather": data.get("weather"),
        }
        for node, data in bridge.status.items()
        # Only return data from last 600s
        if current_time - data["timestamp"] < 600
    }
    return jsonify(topology)


@app.route("/bot/set_token", methods=["POST"])
def set_bot_token():
    """Set a new API token for the Telegram bot.

    This endpoint allows the user to update the Telegram bot token, typically obtained from
    `@BotFather`. The token is expected to be sent in a JSON payload with a key named "token".

    If a bot instance is already running, it will be stopped before updating the token.
    The bot is expected to restart with the new token.

    Request JSON:
        {
            "token": "<new-telegram-bot-token>"
        }

    Returns:
        200 OK:
            {
                "status": "Token updated bot should restart soon!"
            }

        400 Bad Request:
            {
                "error": "Missing 'token' field"
            }

        500 Internal Server Error:
            {
                "error": "<error message>"
            }
    """
    try:
        data = request.get_json()
        token = data.get("token")

        if not token:
            return jsonify({"error": "Missing 'token' field"}), 400

        # Stop current bot if running
        if hasattr(bridge, "bot") and bridge.bot:
            bridge.bot.set_token(token)
            if bridge.bot.application is not None and bridge.bot.application.running:
                bridge.bot.stop()

        return jsonify({"status": "Token updated bot should restart soon!"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/bot/status", methods=["get"])
def get_bot_status():
    """Get the current status of the Telegram bot.

    This endpoint returns whether the Telegram bot is currently running or not.
    The response is returned in JSON format with the status set to either "online" or "offline".

    Returns:
        200 OK:
            {
                "status": "online" | "offline"
            }
    """
    if hasattr(bridge, "bot") and bridge.bot.application is not None:
        return jsonify(
            {"status": str("online" if bridge.bot.application.running else "offline")}
        )
    else:
        return jsonify({"status": "offline"})


@app.route("/bot/get_info", methods=["get"])
def get_bot_info():
    """Retrieve basic information about the Telegram bot.

    This endpoint returns details about the bot, including its username, display name,
    and password (if available). If the bot information is not initialized, an error is returned.

    Returns:
        200 OK:
            {
                "username": "<bot_username>",
                "name": "<bot_display_name>",
                "password": "<bot_one_time_password>"
            }

        500 Internal Server Error:
            {
                "error": "No bot info"
            }
    """
    if bridge.bot.info is not None:
        return jsonify(
            {
                "username": bridge.bot.info.username,
                "name": bridge.bot.info.first_name,
                "password": bridge.bot.password,
            }
        )
    else:
        return jsonify({"error": "No bot info"}), 500


@app.route("/bot/restart", methods=["GET"])
def restart_bot():
    """Restart telegram bot."""
    try:
        bridge.bot.stop()
        timeout = 10
        start_time = time.time()

        while bridge.bot.application is not None and bridge.bot.application.running:
            if time.time() - start_time > timeout:
                return jsonify({"error": "bot stop timeout reached!"}), 500
            time.sleep(0.1)

    except Exception as e:
        return jsonify({"error": f"could not stop bot: {str(e)}"}), 500

    return jsonify({"success": "Telegram bot stopped and should restart soon!"})


def start_api_server(host="0.0.0.0", port=8080):
    """Start API server."""
    import logging

    log = logging.getLogger("werkzeug")
    log.setLevel(logging.ERROR)
    app.run(host=host, port=port, debug=False)


def start_cli(bridge: ProtocolSerialBridge):
    """Start command line interface for bridge."""
    try:
        while True:
            cmd = input("> ").strip().split()
            if not cmd:
                continue

            if cmd[0] == "ping" and len(cmd) == 2:
                bridge.ping(int(cmd[1]))
            elif cmd[0] == "broadcast" and len(cmd) > 1:
                bridge.broadcast(" ".join(cmd[1:]))
            elif cmd[0] == "test" and len(cmd) > 1:
                for i in range(int(cmd[1]), int(cmd[2])):
                    bridge.broadcast("test " + str(i))
                    time.sleep(1)
            elif cmd[0] == "exit":
                if bridge.running:
                    bridge.close()
                break
            else:
                print("Invalid command. Available commands:")
                print("  ping <node>")
                print("  broadcast <message>")
                print("  exit")
    except KeyboardInterrupt:
        print("\nCLI thread interrupted.")


def handle_sigterm(sig, frame):
    """SIGTERM handler."""
    print("Received SIGTERM, exiting...")
    if bridge is ProtocolSerialBridge:
        bridge.close()


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, handle_sigterm)
    # Set up command line argument parsing
    parser = argparse.ArgumentParser(description="Linear Protocol Serial Bridge")
    parser.add_argument("--port", help="Serial port to send data (e.g., /dev/ttyUSB0)")
    parser.add_argument(
        "--baud", type=int, default=115200, help="Baud rate (default: 115200)"
    )
    parser.add_argument(
        "--api-port", type=int, default=8080, help="REST API port (default: 8080)"
    )
    parser.add_argument(
        "--service", action="store_true", help="No cli, used when ran as a service"
    )
    args = parser.parse_args()

    # Initialize bridge
    if not args.port:
        parser.error("--port is required when not in mock mode")
    bridge = ProtocolSerialBridge(args.port, args.baud)

    # Start API server in a separate thread
    api_thread = threading.Thread(
        target=start_api_server, kwargs={"port": args.api_port}
    )
    api_thread.daemon = True
    api_thread.start()

    if not args.service:
        cli_thread = threading.Thread(target=start_cli, args=(bridge,))
        cli_thread.daemon = True
        cli_thread.start()

    try:
        while True:
            if not bridge.running:
                break
            try:
                bridge.bot.init()

                if bridge.bot.application is not None:
                    try:
                        bridge.bot.run()
                    except Exception as e:
                        print("Bot run error:", e)
            except InvalidToken:
                print("invalid token!")
            except Exception as e:
                print("Unknown error:", e)

            time.sleep(5)
    except KeyboardInterrupt:
        if bridge.running:
            bridge.close()
        print("\nShutting down...")
