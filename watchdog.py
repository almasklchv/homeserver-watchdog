import os
import socket
import sys

ROUTER_HOST = os.environ.get("ROUTER_HOST")
TARGET_MAC = os.environ.get("TARGET_MAC", "08:97:98:ce:f2:cb")
CHECK_PORT = int(os.environ.get("CHECK_PORT", "2222"))

if not ROUTER_HOST:
    print("ERROR: ROUTER_HOST environment variable is not set.")
    sys.exit(1)

def is_port_open(host, port, timeout=4):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        res = s.connect_ex((host, port))
        s.close()
        return res == 0
    except Exception as e:
        print(f"Error checking {host}:{port} -> {e}")
        return False

def send_wol(host, port, mac_str):
    clean_mac = mac_str.replace(":", "").replace("-", "").replace(".", "").strip()
    mac_bytes = bytes.fromhex(clean_mac)
    magic_packet = b"\xff" * 6 + mac_bytes * 16
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.sendto(magic_packet, (host, port))
    s.close()
    print(f"🚀 Sent Wake-on-LAN Magic Packet to {host}:{port} for MAC {mac_str}")

print("=== Homeserver Cloud Watchdog ===")
print(f"Checking router at {ROUTER_HOST}:80 ...")
router_alive = is_port_open(ROUTER_HOST, 80)

if not router_alive:
    print(f"❌ Router at {ROUTER_HOST}:80 is UNREACHABLE. Apartment is likely without power. Sleeping.")
    sys.exit(0)

print(f"✅ Router is ONLINE! Power in apartment is ACTIVE.")
print(f"Checking homeserver availability at {ROUTER_HOST}:{CHECK_PORT} ...")

server_alive = is_port_open(ROUTER_HOST, CHECK_PORT)

if server_alive:
    print(f"✅ Homeserver is ONLINE and responsive on port {CHECK_PORT}. All good!")
    sys.exit(0)

print(f"⚠️ ALERT: Router is ONLINE, but homeserver is OFFLINE! Triggering Wake-on-LAN...")
send_wol(ROUTER_HOST, 9, TARGET_MAC)
print("Done. Homeserver will boot up in ~30 seconds.")
