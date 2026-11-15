import pickle
import queue
import socket
import struct
import sys
import threading
import time
from pathlib import Path

"""
Explanation:
You instantiate the object and call .start()
And it will wait for telemetry-processor to be run and connect together
You submit data via .enqueue (coming from holoOcean.step())
That data is then converted into ROVData format (for telemetry-processor)
That data is converted into raw bytes (via pickle)
That is sent over the network to telemetry-processor (which needs to be running, obviously)

TODO: fully build out the build_rov_data function to properly convert the holoOcean dictionary to ROVData 
TODO: Actually submit this data in the test.py file
TODO: Add stuff to the run all script
"""

software_common_dir = (Path(__file__).resolve().parent.parent.parent / "team-bath-rov-software" / "common")
sys.path.insert(0, str(software_common_dir))

from common.data_interface.rov_data import ROVData
from common.data_interface.vector_data import Vector3

HOST = "0.0.0.0"
PORT = 52525


class TelemetrySender:
    def __init__(self, max_buffer=1000):
        self.buffer = queue.Queue(maxsize=max_buffer)
        self.running = False
        self.thread = None
        self.conn = None

        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind((HOST, PORT))

    def enqueue(self, data: dict):
        """Queue data to be sent. Non-blocking."""
        try:
            self.buffer.put_nowait({**data})
        except queue.Full:
            pass  # TODO: drop newest or drop oldest

    def build_rov_data(self, d: dict) -> ROVData:
        return ROVData(attitude=Vector3(100, -100, 50))

    def encode(self, rov_data: ROVData) -> bytes:
        payload = pickle.dumps(rov_data)
        return struct.pack("Q", len(payload)) + payload

    def wait_for_client(self):
        while self.running:
            try:
                conn, addr = self.socket.accept()
                conn.settimeout(None)
                return conn, addr
            except socket.timeout:
                continue
        return None, None

    def connect(self):
        self.socket.settimeout(0.5)
        self.socket.listen(1)
        print(f"Waiting for telemetry-processor on {PORT}...")
        try:
            conn, addr = self.wait_for_client()
        except KeyboardInterrupt:
            print("Interrupted while waiting for client")
            self.shutdown()
            return None

        if conn is None:
            self.shutdown()
            return None

        print(f"Connected: {addr}")
        return conn

    def send(self, packet: bytes):
        self.conn.sendall(packet)

    def send_loop(self):
        while self.running:
            try:
                message = self.buffer.get(timeout=0.1)
            except queue.Empty:
                continue
            packet = self.encode(self.build_rov_data(message))
            try:
                self.send(packet)
            except OSError as e:  # covers BrokenPipe / ConnectionReset
                print(f"Send failed: {e}")
                self.running = False

    def start(self) -> bool:
        self.running = True
        self.conn = self.connect()
        if self.conn is None:
            return False
        self.thread = threading.Thread(target=self.send_loop, daemon=True)
        self.thread.start()
        return True

    def shutdown(self):
        self.running = False
        print("Shutting down")
        if self.thread and self.thread is not threading.current_thread():
            self.thread.join(timeout=1.0)
        if self.conn:
            self.conn.close()
            self.conn = None
            print("Connection closed")
        self.socket.close()
        print("Socket closed")


if __name__ == "__main__":
    sender = TelemetrySender()
    if sender.start():
        try:
            while sender.running:
                sender.enqueue({})
                time.sleep(0.1)
        except KeyboardInterrupt:
            print("\nCtrl+C received")
        finally:
            sender.shutdown()
