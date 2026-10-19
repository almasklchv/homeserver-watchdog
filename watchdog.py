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

# Number of 2-minute ticks per workflow run (15 * 120s = 30 minutes per chain link)
LOOP_ITERATIONS = int(os.environ.get("LOOP_ITERATIONS", "15"))
LOOP_SLEEP_SEC = int(os.environ.get("LOOP_SLEEP_SEC", "120"))


def gh_api_request(method: str, path: str, payload: dict | None = None) -> dict | None:
    if not GH_PAT:
        return None
    url = f"https://api.github.com/repos/{GH_REPO}/{path.lstrip('/')}"
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {
        "Authorization": f"Bearer {GH_PAT}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "homeserver-cloud-watchdog",
    }
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=12) as resp:
        raw = resp.read().decode("utf-8")
        return json.loads(raw) if raw.strip() else {}


def get_gh_variable(name: str, fallback: str = "") -> str:
    try:
        res = gh_api_request("GET", f"actions/variables/{name}")
        if res and "value" in res:
            return str(res["value"]).strip()
    except Exception as e:
        print(f"[GH] Warning: could not fetch variable {name} via API: {e}")
    return os.environ.get(name, fallback).strip()


def set_gh_variable(name: str, value: str) -> None:
    try:
        gh_api_request("PATCH", f"actions/variables/{name}", {"name": name, "value": value})
        os.environ[name] = value
        print(f"[GH] Updated variable {name}={value}")
    except Exception as e:
        print(f"[GH] Failed to update variable {name}: {e}")


def dispatch_next_workflow_run() -> None:
    if not GH_PAT:
        print("[CHAIN] Missing GH_PAT; cannot self-dispatch next workflow run.")
        return
    try:
        gh_api_request("POST", "actions/workflows/watchdog.yml/dispatches", {"ref": "main"})
        print("[CHAIN] Successfully dispatched next watchdog.yml workflow run!")
    except Exception as e:
        print(f"[CHAIN] Failed to dispatch next workflow run: {e}")


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


def check_heartbeat_and_alert() -> None:
    heartbeat = get_gh_variable("SERVER_HEARTBEAT", "")
    alert_state = get_gh_variable("SERVER_ALERT_STATE", "ONLINE")

    if not heartbeat:
        print("[HB] No SERVER_HEARTBEAT variable found yet.")
        return

    parts = heartbeat.split("|")
    try:
        hb_ts = int(parts[0])
    except ValueError:
        print(f"[HB] Invalid timestamp in SERVER_HEARTBEAT: {heartbeat}")
        return

    hb_human = parts[1] if len(parts) > 1 else "неизвестно"
    hb_ip = parts[2] if len(parts) > 2 else "неизвестно"
    hb_bat = parts[3] if len(parts) > 3 else "100%"

    now_ts = int(time.time())
    elapsed = now_ts - hb_ts
    mins_ago = max(1, elapsed // 60)

    print(f"[HB] Last server heartbeat: {hb_human} ({elapsed}s ago), bat={hb_bat}, state={alert_state}", flush=True)

    # Server pushes heartbeat every 2 minutes (120s). If > 6 minutes (360s) have elapsed without a heartbeat:
    if elapsed > 360 and alert_state != "OFFLINE":
        msg = (
            "🚨🕯 <b>СЕРВЕР ПЕРЕСТАЛ ВЫХОДИТЬ НА СВЯЗЬ (ВОЗМОЖНО ОТКЛЮЧИЛИ СВЕТ)!</b>\n"
            f"• <b>Последний сигнал:</b> <code>{hb_human}</code> (~{mins_ago} мин назад)\n"
            f"• <b>Заряд батареи перед обрывом:</b> <code>{hb_bat}</code>\n"
            f"• <b>Последний IP:</b> <code>{hb_ip}</code>\n"
            "• <b>Причина:</b> Вероятно, в квартире отключили электричество (роутер обесточен) или пропал интернет провайдера.\n"
            "• <b>Что делает сервер:</b> Автоматически перешёл на батарею (буфер 3 мин → усыпление контейнеров → режим глубокого сна S3 RTC).\n\n"
            "⏳ <b>В ту же секунду, как дадут свет и загрузится роутер, сервер сам пришлёт уведомление!</b>"
        )
        if send_telegram(msg):
            print("[TG] Outage alert sent to Telegram! Marking SERVER_ALERT_STATE=OFFLINE.", flush=True)
            set_gh_variable("SERVER_ALERT_STATE", "OFFLINE")


def send_wol_packets() -> None:
    clean_mac = TARGET_MAC.replace(":", "").replace("-", "").replace(".", "").strip()
    if len(clean_mac) != 12:
        print(f"ERROR: Invalid MAC address: {TARGET_MAC}")
        return

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
                print(f"[WAKE] Sent 5x Magic Packets to {host}:{port} for MAC {TARGET_MAC}", flush=True)
            except Exception as e:
                print(f"[ERROR] Failed to send to {host}:{port}: {e}", flush=True)


def main() -> None:
    loop_mode = "--loop" in sys.argv
    iterations = LOOP_ITERATIONS if loop_mode else 1

    try:
        for i in range(1, iterations + 1):
            print(f"\n--- [Tick {i}/{iterations}] {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())} ---", flush=True)
            check_heartbeat_and_alert()
            send_wol_packets()
            if i < iterations:
                time.sleep(LOOP_SLEEP_SEC)
    finally:
        if loop_mode:
            dispatch_next_workflow_run()


if __name__ == "__main__":
    main()
