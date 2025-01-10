import socket
import threading
import struct
import time

MAGIC_COOKIE = 0xabcddcba
OFFER_TYPE = 0x2
REQUEST_TYPE = 0x3
PAYLOAD_TYPE = 0x4


def broadcast_offers(server_ip, udp_port, tcp_port):
    """Send periodic UDP offer broadcasts."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP) as udp_socket:
        udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        offer_packet = struct.pack('!IBHH', MAGIC_COOKIE, OFFER_TYPE, udp_port, tcp_port)
        while True:
            udp_socket.sendto(offer_packet, ('<broadcast>', 13117))
            time.sleep(1)


def handle_client(client_socket, address, is_tcp):
    """Handle individual client connections for TCP or UDP."""
    try:
        if is_tcp:
            requested_size = int(client_socket.recv(1024).decode().strip())
            client_socket.sendall(b'A' * requested_size)
            print(f"Completed TCP transfer for {address}")
        else:
            # UDP handling can go here
            pass
    except Exception as e:
        print(f"Error with client {address}: {e}")
    finally:
        client_socket.close()


def tcp_server_handler(tcp_port):
    """Handle incoming TCP connections."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as tcp_socket:
        tcp_socket.bind(("", tcp_port))
        tcp_socket.listen(5)
        print(f"TCP Server started on port {tcp_port}")
        while True:
            client_socket, address = tcp_socket.accept()
            threading.Thread(target=handle_client, args=(client_socket, address, True)).start()


def udp_server_handler(udp_port):
    """Handle incoming UDP connections."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp_socket:
        udp_socket.bind(("", udp_port))
        print(f"UDP Server started on port {udp_port}")
        while True:
            try:
                data, address = udp_socket.recvfrom(1024)
                magic_cookie, message_type, file_size = struct.unpack('!IBQ', data)
                if magic_cookie == MAGIC_COOKIE and message_type == REQUEST_TYPE:
                    print(f"Received UDP request from {address}, file size: {file_size}")
                    total_segments = file_size // 1024  # Assume 1KB packets
                    for segment in range(total_segments):
                        try:
                            payload = struct.pack('!IBQQ', MAGIC_COOKIE, PAYLOAD_TYPE, total_segments, segment) + b'A' * 1024
                            udp_socket.sendto(payload, address)
                        except Exception as e:
                            print(f"Error sending to {address}: {e}")
                            break
                    print(f"Completed UDP transfer to {address}")
            except Exception as e:
                print(f"UDP server error: {e}")


def start_server():
    """Start the server application."""
    server_ip = socket.gethostbyname(socket.gethostname())
    udp_port = 12345
    tcp_port = 54321

    print(f"Server started, listening on IP address {server_ip}")

    threading.Thread(target=broadcast_offers, args=(server_ip, udp_port, tcp_port)).start()
    threading.Thread(target=tcp_server_handler, args=(tcp_port,)).start()
    threading.Thread(target=udp_server_handler, args=(udp_port,)).start()


if __name__ == "__main__":
    start_server()
