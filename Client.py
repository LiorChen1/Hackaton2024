import threading
import socket
import struct
import time

MAGIC_COOKIE = 0xabcddcba
OFFER_MSG_TYPE = 0x2
REQUEST_MSG_TYPE = 0x3
PAYLOAD_MSG_TYPE = 0x4


def parse_offer_packet(packet):
    """Parse an offer packet and extract UDP and TCP port numbers."""
    try:
        magic, msg_type, udp_port, tcp_port = struct.unpack('!IBHH', packet)
        if magic != MAGIC_COOKIE or msg_type != OFFER_MSG_TYPE:
            raise ValueError("Invalid offer packet")
        return udp_port, tcp_port
    except struct.error:
        raise ValueError("Malformed offer packet")


def parse_payload_packet(packet, expected_file_size):
    """Parse a payload packet and validate payload size."""
    try:
        header_size = struct.calcsize('!IBQQ')
        magic, msg_type, total_segments, current_segment = struct.unpack('!IBQQ', packet[:header_size])

        if magic != MAGIC_COOKIE or msg_type != PAYLOAD_MSG_TYPE:
            raise ValueError("Invalid payload packet")

        payload = packet[header_size:]
        payload_size = len(payload)
        return total_segments, current_segment, payload, payload_size
    except struct.error:
        raise ValueError("Malformed payload packet")


class SpeedTestClient:
    """Client for performing UDP and TCP speed tests."""

    def __init__(self, udp_port):
        self.udp_port = udp_port
        self.running = True
        self.looking_for_server = True
        self.file_size = 1024 * 1024   # 100MB
        self.tcp_connections = int(input("enter tcp amount:"))
        self.udp_connections = int(input("enter udp amount"))

    def start(self):
        """Start listening for server offers."""
        while self.running:
            self._listen_for_offers()

    @staticmethod
    def clear_udp_buffer(udp_socket):
        """Clear the UDP socket buffer."""
        udp_socket.setblocking(False)
        try:
            while True:
                udp_socket.recvfrom(1024)  # Discard data
        except BlockingIOError:
            pass  # No more data in the buffer
        finally:
            udp_socket.setblocking(True)

    def _listen_for_offers(self):
        """Listen for server offer messages."""
        udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        udp_socket.bind(('', self.udp_port))
        print(f"Client started, listening for offer requests on UDP port {self.udp_port}...")

        while self.looking_for_server:
            try:
                self.clear_udp_buffer(udp_socket)
                print("Waiting for broadcast...")
                data, addr = udp_socket.recvfrom(1024)
                server_ip = addr[0]
                udp_port, tcp_port = parse_offer_packet(data)
                print(f"Received offer from {server_ip} - UDP: {udp_port}, TCP: {tcp_port}")
                self.speed_test(server_ip, udp_port, tcp_port)
            except Exception as e:
                print(f"Error receiving offer: {e}")

    def speed_test(self, server_ip, udp_port, tcp_port):
        """Run speed tests over both TCP and UDP connections."""
        tcp_threads = [threading.Thread(target=self._handle_tcp_connection, args=(server_ip, tcp_port, i + 1)) for i in
                       range(self.tcp_connections)]
        udp_threads = [
            threading.Thread(target=self._handle_udp_connection, args=(server_ip, udp_port, self.file_size, i + 1)) for
            i in range(self.udp_connections)]

        for thread in tcp_threads + udp_threads:
            thread.start()
        for thread in tcp_threads + udp_threads:
            thread.join()

        print("All transfers complete, listening for new offer requests\n\n")

    def _handle_udp_connection(self, server_ip, udp_port, file_size, id):
        """Handle a UDP connection for data transfer."""
        try:
            udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            udp_socket.settimeout(1)
            request_packet = struct.pack('!IBQ', MAGIC_COOKIE, REQUEST_MSG_TYPE, file_size)
            udp_socket.sendto(request_packet, (server_ip, udp_port))
            print(f"Sent UDP request to {server_ip}:{udp_port} for {file_size} bytes.")

            start_time = time.time()
            total_data = 0
            received_segments = set()
            total_segments = None

            while True:
                try:
                    data, _ = udp_socket.recvfrom(1024)
                    total_segments, current_segment, payload, payload_size = parse_payload_packet(data, file_size)
                    total_data += payload_size
                    received_segments.add(current_segment)
                    if total_segments == current_segment + 1:
                        break
                except socket.timeout:
                    break

            end_time = time.time()
            transfer_time = end_time - start_time
            transfer_speed = total_data * 8 / transfer_time if transfer_time > 0 else 0
            received_percentage = (len(received_segments) / total_segments) * 100 if total_segments else 0

            print(
                f"UDP transfer #{id} finished in {transfer_time:.2f}s, speed: {transfer_speed:.2f} bps, received: {received_percentage:.2f}%\n")
        except Exception as e:
            print(f"Error during UDP transfer: {e}")
        finally:
            udp_socket.close()

    def _handle_tcp_connection(self, server_ip, tcp_port, id):
        """Handle a TCP connection for data transfer."""
        try:
            tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            tcp_socket.connect((server_ip, tcp_port))
            request_packet = struct.pack('!IBQ', MAGIC_COOKIE, REQUEST_MSG_TYPE, self.file_size)
            tcp_socket.sendall(request_packet)
            print(f"Sent TCP request to {server_ip}:{tcp_port} for {self.file_size} bytes.")

            start_time = time.time()
            received_data = b""
            while len(received_data) < self.file_size:
                chunk = tcp_socket.recv(min(1024, self.file_size - len(received_data)))
                if not chunk:
                    raise ConnectionError("Connection closed prematurely by server.")
                received_data += chunk

            end_time = time.time()
            transfer_time = end_time - start_time
            transfer_speed = len(received_data) * 8 / transfer_time if transfer_time > 0 else 0

            print(f"TCP transfer #{id} finished in {transfer_time:.2f}s, speed: {transfer_speed:.2f} bps\n")
        except Exception as e:
            print(f"Error in TCP connection: {e}")
        finally:
            tcp_socket.close()

    def stop(self):
        """Stop the client."""
        self.running = False
def main():
    udp_port = 11111

    client = SpeedTestClient(udp_port)
    try:
        client.start()
        print("Client running. Press Ctrl+C to stop.")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Shutting down client...")
        client.stop()
if __name__ == "__main__":
    main()