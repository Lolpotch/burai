#!/usr/bin/env python3
import subprocess
import json
import requests
from datetime import datetime

BOT_TOKEN = ""
CHAT_ID = ""
LOG_FILE = "/etc/fail2ban/scripts/banned_log.json"

def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": text}
    try:
        requests.post(url, data=data, timeout=10)
    except Exception as e:
        print(f"Telegram send error: {e}")

def get_banned_ips():
    try:
        result = subprocess.run(["fail2ban-client", "status", "sshd"], capture_output=True, text=True)
        lines = result.stdout.splitlines()
        for line in lines:
            if "Banned IP list:" in line:
                return line.split(":", 1)[1].strip().split()
    except Exception:
        pass
    return []

def load_previous_bans():
    try:
        with open(LOG_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_bans(bans):
    with open(LOG_FILE, "w") as f:
        json.dump(bans, f, indent=2)

def main():
    current_bans = get_banned_ips()
    saved_bans = load_previous_bans()

    new_bans = [ip for ip in current_bans if ip not in saved_bans]

    for ip in new_bans:
        saved_bans[ip] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    save_bans(saved_bans)

    # buat ringkasan
    if saved_bans:
        summary = "\n".join([f"{ip} — {t}" for ip, t in saved_bans.items()])
        send_telegram_message(f"📊 Fail2Ban Summary:\n{summary}")
    else:
        send_telegram_message("✅ Tidak ada IP yang diban saat ini.")

if __name__ == "__main__":
    main()
