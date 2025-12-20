#!/usr/bin/env python3
import subprocess
import re
import requests
import datetime

# ======== KONFIGURASI ========
BOT_TOKEN = ""
CHAT_ID = ""
UFW_BIN = "/usr/sbin/ufw"
# =============================

def send_telegram(msg):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": CHAT_ID, "text": msg})
    except Exception as e:
        print(f"[WARN] Gagal kirim Telegram: {e}")

def get_banned_ips():
    """Ambil daftar IP yang saat ini diblok oleh UFW"""
    try:
        result = subprocess.run([UFW_BIN, "status"], capture_output=True, text=True)
        output = result.stdout
        # regex cari IP yang terblok
        ips = re.findall(r"DENY\s+(\d+\.\d+\.\d+\.\d+)", output)
        return ips
    except Exception as e:
        print(f"[ERROR] Gagal ambil daftar UFW: {e}")
        return []

def main():
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ips = get_banned_ips()

    if not ips:
        msg = f"📊 [ML Detector Summary]\n{now}\nTidak ada IP yang diblokir saat ini ✅"
        print(msg)
        send_telegram(msg)
        return

    summary = f"📊 [ML Detector Summary]\n{now}\n"
    summary += "Daftar IP yang sedang diblokir oleh ML Detector:\n"
    for ip in ips:
        summary += f"• {ip}\n"

    print(summary)
    send_telegram(summary)

if __name__ == "__main__":
    main()
