import os
import socket
import sys

ROUTER_HOST = os.environ.get("ROUTER_HOST")
TARGET_MAC = os.environ.get("TARGET_MAC", "08:97:98:ce:f2:cb")

clean_mac = TARGET_MAC.replace(":", "").replace("-", "").replace(".", "").strip()
mac_bytes = bytes.fromhex(clean_mac)
magic_packet = b"\xff" * 6 + mac_bytes * 16

s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.sendto(magic_packet, (ROUTER_HOST, 9))
s.close()
print(f"TEST: Sent Magic Packet from GitHub Actions to {ROUTER_HOST}:9 for MAC {TARGET_MAC}")
