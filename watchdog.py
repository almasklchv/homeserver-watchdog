import json
import os
import socket
import sys
import time
import urllib.parse
import urllib.request

ROUTER_HOST = os.environ.get("ROUTER_HOST", "").strip()
DUCKDNS_HOST = "almas-homeserver.duckdns.org"
TARGET_MAC = os.environ.get("TARGET_MAC", "08:97:98:ce:f2:cb")
WAKE_PORTS_STR = os.environ.get("WAKE_PORTS", "443,59999,9")

TG_BOT_TOKEN = os.environ.get("TG_BOT_TOKEN", "").strip()
TG_CHAT_ID = os.environ.get("TG_CHAT_ID", "").strip()
GH_PAT = os.environ.get("GH_PAT", "").strip()
GH_REPO = os.environ.get("GITHUB_REPOSITORY", "almasklchv/homeserver-watchdog")

SERVER_HEARTBEAT = os.environ.get("SERVER_HEARTBEAT", "").strip()
SERVER_ALERT_STATE = os.environ.get("SERVER_ALERT_STATE", "ONLINE").strip()


def send_telegram(html_text: str) -> bool:
    if not TG_BOT_TOKEN or not TG_CHAT_ID:
        print("[TG] Missing TG_BOT_TOKEN or TG_CHAT_ID; skipping alert.")
        return False
    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id": TG_CHAT_ID,
        "parse_mode": "HTML",
        "disable_web_page_preview": "true",
        "text": html_text,
    }).encode("utf-8")
    try:
        req = urllib.request.Request(url, data=data, method="POST")
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            return bool(body.get("ok"))
    except Exception as e:
        print(f"[TG] Failed to send Telegram alert: {e}")
        return False


def set_gh_variable(name: str, value: str) -> None:
    if not GH_PAT:
        print(f"[GH] Missing GH_PAT; cannot update variable {name}.")
        return
    url = f"https://api.github.com/repos/{GH_REPO}/actions/variables/{name}"
    payload = json.dumps({"name": name, "value": value}).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {GH_PAT}",
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    try:
        req = urllib.request.Request(url, data=payload, headers=headers, method="PATCH")
        with urllib.request.urlopen(req, timeout=10) as resp:
            print(f"[GH] Updated variable {name}={value} (HTTP {resp.status})")
    except Exception as e:
        print(f"[GH] Failed to update variable {name}: {e}")


def check_heartbeat_and_alert() -> None:
    if not SERVER_HEARTBEAT:
        print("[HB] No SERVER_HEARTBEAT variable found yet.")
        return

    parts = SERVER_HEARTBEAT.split("|")
    try:
        hb_ts = int(parts[0])
    except ValueError:
        print(f"[HB] Invalid timestamp in SERVER_HEARTBEAT: {SERVER_HEARTBEAT}")
        return

    hb_human = parts[1] if len(parts) > 1 else "неизвестно"
    hb_ip = parts[2] if len(parts) > 2 else "неизвестно"
    hb_bat = parts[3] if len(parts) > 3 else "100%"

    now_ts = int(time.time())
    elapsed = now_ts - hb_ts
    mins_ago = max(1, elapsed // 60)

    print(f"[HB] Last server heartbeat: {hb_human} ({elapsed}s ago), state={SERVER_ALERT_STATE}")

    # Server sends heartbeat every 2 minutes. If > 7 minutes (420s) have elapsed without a heartbeat:
    if elapsed > 420 and SERVER_ALERT_STATE != "OFFLINE":
        msg = (
            "🚨🕯 <b>СЕРВЕР ПЕРЕСТАЛ ВЫХОДИТЬ НА СВЯЗЬ (ВОЗМОЖНО ОТКЛЮЧИЛИ СВЕТ)!</b>\n"
            f"• <b>Последний сигнал:</b> <code>{hb_human}</code> (~{mins_ago} мин назад)\n"
            f"• <b>Заряд батареи перед обрывом:</b> <code>{hb_bat}</code>\n"
            f"• <b>Последний IP:</b> <code>{hb_ip}</code>\n"
            "• <b>Причина:</b> Вероятно, в квартире отключили электричество (роутер обесточен) или пропал интернет провайдера.\n"
            "• <b>Что делает сервер:</b> Автоматически перешёл на батарею (буфер 5 мин → усыпление контейнеров → режим глубокого сна RTC).\n\n"
            "⏳ <b>В ту же секунду, как дадут свет и загрузится роутер, сервер сам пришлёт уведомление!</b>"
        )
        if send_telegram(msg):
            print("[TG] Outage alert sent to Telegram! Marking SERVER_ALERT_STATE=OFFLINE.")
            set_gh_variable("SERVER_ALERT_STATE", "OFFLINE")


def send_wol_packets() -> None:
    clean_mac = TARGET_MAC.replace(":", "").replace("-", "").replace(".", "").strip()
    if len(clean_mac) != 12:
        print(f"ERROR: Invalid MAC address: {TARGET_MAC}")
        sys.exit(1)

    mac_bytes = bytes.fromhex(clean_mac)
    magic_packet = b"\xff" * 6 + mac_bytes * 16
    ports = [int(p.strip()) for p in WAKE_PORTS_STR.split(",") if p.strip()]

    targets = []
    if ROUTER_HOST:
        targets.append(ROUTER_HOST)
    if DUCKDNS_HOST not in targets:
        targets.append(DUCKDNS_HOST)

    for host in targets:
        for port in ports:
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.settimeout(3.0)
                for _ in range(5):
                    s.sendto(magic_packet, (host, port))
                    time.sleep(0.05)
                s.close()
                print(f"[WAKE] Sent 5x Magic Packets to {host}:{port} for MAC {TARGET_MAC}")
            except Exception as e:
                print(f"[ERROR] Failed to send to {host}:{port}: {e}")


if __name__ == "__main__":
    check_heartbeat_and_alert()
    send_wol_packets()
    print("Watchdog check completed successfully.")
