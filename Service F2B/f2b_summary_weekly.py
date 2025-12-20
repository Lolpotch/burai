#!/usr/bin/env python3
import os
import re
import datetime
import requests
from collections import defaultdict

# ============ KONFIGURASI ============
LOG_FILE = "/var/log/fail2ban.log"
BOT_TOKEN = ""
CHAT_ID = ""
# =====================================

def send_telegram(message):
    """Kirim pesan ke Telegram"""
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": CHAT_ID, "text": message})
    except Exception as e:
        print(f"[WARN] Gagal kirim Telegram: {e}")

def parse_log():
    """Ambil data ban dari /var/log/fail2ban.log selama 7 hari terakhir"""
    if not os.path.exists(LOG_FILE):
        print(f"[ERROR] Log file tidak ditemukan: {LOG_FILE}")
        return {}, {}

    now = datetime.datetime.now()
    one_week_ago = now - datetime.timedelta(days=7)

    ip_counts = defaultdict(int)
    ip_last_seen = {}

    # Pola log Fail2Ban
    pattern = re.compile(r"Ban (\d+\.\d+\.\d+\.\d+)")

    with open(LOG_FILE, "r") as f:
        for line in f:
            match = pattern.search(line)
            if not match:
                continue
            ip = match.group(1)

            # Ambil timestamp dari awal baris log
            ts_str = line.split(",")[0].strip()
            try:
                ts = datetime.datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
            except Exception:
                continue

            if ts >= one_week_ago:
                ip_counts[ip] += 1
                ip_last_seen[ip] = ts

    return ip_counts, ip_last_seen

def generate_summary():
    """Buat ringkasan mingguan Fail2Ban"""
    ip_counts, ip_last_seen = parse_log()
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if not ip_counts:
        msg = f"📅 [Fail2Ban Weekly Summary]\n{now}\nTidak ada IP yang diblokir dalam 7 hari terakhir ✅"
        print(msg)
        send_telegram(msg)
        return

    summary = f"📅 [Fail2Ban Weekly Summary]\n{now}\n"
    summary += "Daftar IP yang diblokir dalam 7 hari terakhir:\n\n"

    # Urutkan IP berdasarkan jumlah ban terbanyak
    sorted_ips = sorted(ip_counts.items(), key=lambda x: x[1], reverse=True)
    for ip, count in sorted_ips:
        last_seen = ip_last_seen[ip].strftime("%Y-%m-%d %H:%M:%S")
        summary += f"• {ip} — {count}x diblokir (terakhir {last_seen})\n"

    print(summary)
    send_telegram(summary)

if __name__ == "__main__":
    generate_summary()
