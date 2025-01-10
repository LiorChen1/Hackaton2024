import threading
import socket
import struct
import time

MAGIC_COOKIE = 0xabcddcba
OFFER_TYPE = 0x2
REQUEST_TYPE = 0x3
PAYLOAD_TYPE = 0x4


def listen_for_offers():
    """Listen for server broadcast offers."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp_socket:
        udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        udp_socket.bind(("", 13117))
        print("Client started, listening for offer requests...")
        while True:
            data, address = udp_socket.recvfrom(1024)
            magic_cookie, message_type, udp_port, tcp_port = struct.unpack('!IBHH', data)
            if magic_cookie == MAGIC_COOKIE and message_type == OFFER_TYPE:
                print(f"Received offer from {address[0]}")
                handle_offer(address[0], tcp_port, udp_port)


def handle_offer(server_ip, tcp_port, udp_port):
    """Handle offer by initiating speed tests."""
    file_size = 1024 * 1024 * 1024  # Example: 1GB
    tcp_threads = 1
    udp_threads = 2

    threads = []
    for _ in range(tcp_threads):
        t = threading.Thread(target=tcp_test, args=(server_ip, tcp_port, file_size))
        threads.append(t)
        t.start()

    for _ in range(udp_threads):
        t = threading.Thread(target=udp_test, args=(server_ip, udp_port, file_size))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()
    print("All transfers complete, listening to offer requests")


def tcp_test(server_ip, tcp_port, file_size):
    """Perform a TCP speed test."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as tcp_socket:
            tcp_socket.connect((server_ip, tcp_port))
            tcp_socket.sendall(str(file_size).encode() + b"\n")
            start_time = time.time()
            data = tcp_socket.recv(file_size)
            end_time = time.time()
            print(f"TCP transfer finished, total time: {end_time - start_time} seconds")
    except Exception as e:
        print(f"TCP test error: {e}")


def udp_test(server_ip, udp_port, file_size):
    """Perform a UDP speed test."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp_socket:
            request_packet = struct.pack('!IBQ', MAGIC_COOKIE, REQUEST_TYPE, file_size)
            udp_socket.sendto(request_packet, (server_ip, udp_port))
            start_time = time.time()
            received_segments = set()
            expected_segments = file_size // 1024  # Assuming 1KB per packet
            udp_socket.settimeout(1)  # Timeout to detect end of transmission

            while True:
                try:
                    data, _ = udp_socket.recvfrom(2048)
                    magic_cookie, message_type, total_segments, current_segment = struct.unpack('!IBQQ', data[:20])
                    if magic_cookie == MAGIC_COOKIE and message_type == PAYLOAD_TYPE:
                        received_segments.add(current_segment)
                except socket.timeout:
                    break

            end_time = time.time()
            success_rate = (len(received_segments) / expected_segments) * 100 if expected_segments > 0 else 0
            print(f"UDP transfer finished, total time: {end_time - start_time} seconds, "
                  f"success rate: {success_rate:.2f}%")
    except Exception as e:
        print(f"UDP test error: {e}")


if __name__ == "__main__":
    listen_for_offers()
