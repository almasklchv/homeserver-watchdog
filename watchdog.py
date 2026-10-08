import os
import socket
import sys
import time

ROUTER_HOST = os.environ.get("ROUTER_HOST")
TARGET_MAC = os.environ.get("TARGET_MAC", "08:97:98:ce:f2:cb")
WAKE_PORTS_STR = os.environ.get("WAKE_PORTS", "443,59999,9")
CHECK_PORT = os.environ.get("CHECK_PORT")

if not ROUTER_HOST:
    print("ERROR: ROUTER_HOST environment variable not set.")
    sys.exit(1)

clean_mac = TARGET_MAC.replace(":", "").replace("-", "").replace(".", "").strip()
if len(clean_mac) != 12:
    print(f"ERROR: Invalid MAC address: {TARGET_MAC}")
    sys.exit(1)

mac_bytes = bytes.fromhex(clean_mac)
magic_packet = b"\xff" * 6 + mac_bytes * 16

print(f"Target Router: {ROUTER_HOST}, Target MAC: {TARGET_MAC}")

ports = [int(p.strip()) for p in WAKE_PORTS_STR.split(",") if p.strip()]

for port in ports:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        for i in range(5):
            s.sendto(magic_packet, (ROUTER_HOST, port))
            time.sleep(0.05)
        s.close()
        print(f"[WAKE] Sent 5x Magic Packets to {ROUTER_HOST}:{port} for MAC {TARGET_MAC}")
    except Exception as e:
        print(f"[ERROR] Failed to send to port {port}: {e}")

print("Watchdog check completed successfully.")
