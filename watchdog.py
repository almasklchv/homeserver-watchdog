import os
import socket
import sys
import time
import subprocess

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

# Check if homeserver is already online (if CHECK_PORT is provided and reachable)
if CHECK_PORT:
    try:
        port_num = int(CHECK_PORT)
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(3.0)
        s.connect((ROUTER_HOST, port_num))
        s.close()
        print(f"[STATUS] Homeserver is ONLINE and responsive on port {port_num}. No wake packet needed.")
        sys.exit(0)
    except Exception as e:
        print(f"[STATUS] Server port {CHECK_PORT} not reachable ({e}). Proceeding with wake routine.")

# Check if router is reachable (power outage verification)
print(f"[CHECK] Pinging router at {ROUTER_HOST}...")
res = subprocess.run(["ping", "-c", "2", "-W", "3", ROUTER_HOST], capture_output=True)
if res.returncode != 0:
    print(f"[OFFLINE] Router {ROUTER_HOST} is unreachable (power is likely still off in the apartment). Skipping.")
    sys.exit(0)

print(f"[ONLINE] Router {ROUTER_HOST} is reachable! Power is ON in the apartment.")

ports = [int(p.strip()) for p in WAKE_PORTS_STR.split(",") if p.strip()]

for port in ports:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        for _ in range(3):
            s.sendto(magic_packet, (ROUTER_HOST, port))
            time.sleep(0.05)
        s.close()
        print(f"[WAKE] Sent 3x Magic Packets to {ROUTER_HOST}:{port} for MAC {TARGET_MAC}")
    except Exception as e:
        print(f"[ERROR] Failed to send to port {port}: {e}")
