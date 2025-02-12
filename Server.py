import socket
import threading
import struct
import time

# Constants
MAGIC_COOKIE = 0xabcddcba
OFFER_MSG_TYPE = 0x2
REQUEST_MSG_TYPE = 0x3
PAYLOAD_MSG_TYPE = 0x4


def find_free_port(start_port=20000, max_attempts=1000):
    """Find a free port starting from the given port."""
    for port in range(start_port, start_port + max_attempts):
        try:
            test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            test_socket.bind(("0.0.0.0", port))
            test_socket.close()
            return port
        except OSError:
            continue
    raise Exception("Could not find a free port.")


def get_local_ip():
    """Retrieve the local machine's IP address."""
    try:
        temp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        temp_socket.connect(("8.8.8.8", 80))
        ip = temp_socket.getsockname()[0]
        temp_socket.close()
        return ip
    except Exception:
        return "127.0.0.1"


# Helper Functions
def create_offer_packet(udp_port, tcp_port):
    """Create an offer packet for broadcasting."""
    return struct.pack('!IBHH', MAGIC_COOKIE, OFFER_MSG_TYPE, udp_port, tcp_port)


def parse_request_packet(packet):
    """Parse a client request packet."""
    try:
        magic, msg_type, file_size = struct.unpack('!IBQ', packet)
        if magic != MAGIC_COOKIE or msg_type != REQUEST_MSG_TYPE or file_size > 2 ** 64 - 1:
            return None
        return file_size
    except struct.error:
        return None


# Server Class
class SpeedTestServer:
    """Server for handling speed test requests via UDP and TCP."""

    def __init__(self, udp_port, tcp_port):
        self.ip = None
        self.udp_port = udp_port
        self.tcp_port = tcp_port
        self.running = True

        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

        self.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    def start(self):
        """Start the server."""
        self.ip = get_local_ip()
        print(f"Server started, listening on IP {self.ip}")
        threading.Thread(target=self._udp_server_and_broadcast, daemon=True).start()
        threading.Thread(target=self._start_tcp_server, daemon=True).start()

    def _udp_server_and_broadcast(self):
        """Handle UDP broadcasts and incoming client requests."""
        self.udp_socket.bind(('0.0.0.0', self.udp_port))
        print(f"UDP server listening on port {self.udp_port}")

        offer_packet = create_offer_packet(self.udp_port, self.tcp_port)

        while self.running:
            try:
                self.udp_socket.sendto(offer_packet, ('<broadcast>', self.udp_port))
                self.udp_socket.settimeout(1)

                while True:
                    try:
                        data, addr = self.udp_socket.recvfrom(13)
                        if addr[0] == self.ip:
                            continue
                        file_size = parse_request_packet(data)
                        if file_size:
                            print(f"Received request from {addr} for file size: {file_size}")
                            threading.Thread(target=self._handle_udp_request, args=(file_size, addr)).start()
                    except socket.timeout:
                        break
            except socket.timeout:
                continue

    def _handle_udp_request(self, file_size, addr):
        """Handle an individual UDP client request."""
        try:
            segment_size = 1024 - 21
            total_segments = (file_size + segment_size - 1) // segment_size

            for segment_number in range(total_segments):
                payload_size = min(segment_size, file_size - (segment_number * segment_size))
                payload_data = b'a' * payload_size

                payload_packet = struct.pack('!IBQQ', MAGIC_COOKIE, PAYLOAD_MSG_TYPE, total_segments,
                                             segment_number) + payload_data
                self.udp_socket.sendto(payload_packet, addr)

            print(f"Sent {file_size} bytes to {addr} over UDP")
        except Exception as e:
            print(f"Error handling UDP request from {addr}: {e}")

    def _start_tcp_server(self):
        """Start the TCP server to accept client connections."""
        self.tcp_socket.bind(('0.0.0.0', self.tcp_port))
        self.tcp_socket.listen()
        print(f"TCP server listening on port {self.tcp_port}")

        while self.running:
            conn, addr = self.tcp_socket.accept()
            print(f"Accepted connection from {addr}")
            threading.Thread(target=self._handle_tcp_client, args=(conn,)).start()

    def _handle_tcp_client(self, conn):
        """Handle a single TCP client connection."""
        try:
            request_data = conn.recv(13)
            file_size = parse_request_packet(request_data)

            if not file_size:
                raise ValueError("Invalid request.")
            print(f"Received valid request for file size: {file_size} bytes")

            chunk_size = 1024
            bytes_sent = 0

            while bytes_sent < file_size:
                remaining = file_size - bytes_sent
                conn.sendall(b'a' * min(chunk_size, remaining))
                bytes_sent += min(chunk_size, remaining)

            print(f"Sent {file_size} bytes to client.")
        except Exception as e:
            print(f"Error handling TCP client: {e}")
        finally:
            conn.close()

    def stop(self):
        """Stop the server."""
        self.running = False
        self.udp_socket.close()
        self.tcp_socket.close()


# Main Function for Server
def main():
    udp_port = 11111
    tcp_port = 22222

    server = SpeedTestServer(udp_port, tcp_port)
    try:
        server.start()
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Shutting down server...")
        server.stop()


if __name__ == "__main__":
    main()
