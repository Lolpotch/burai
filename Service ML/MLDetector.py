#!/usr/bin/env python3
import os
import time
import datetime
import subprocess
import joblib
import pandas as pd
import requests
import sys
import shutil

# ============ KONFIGURASI ============
UFW_BIN = shutil.which("ufw") or "/usr/sbin/ufw"
MODEL_PATH = "/home/pros/model/rf_model_TOP_17.pkl"
SCALER_PATH = "/home/pros/model/scaler_TOP_17.pkl"
CACHE_CSV = "/home/pros/dataML/features_ML_fuel_TOP_17_ROUND_2.csv"
LOG_FILE = "/home/pros/dataML/log/testing.log"

# file epoch-prefix untuk parser otomatis
EPOCH_LOG = "/home/pros/dataML/log/ml_detector_epoch.log"
EVENTS_LOCAL_CSV = "/home/pros/dataML/log/events_local_ml.csv"

BOT_TOKEN = ""
CHAT_ID = ""

WHITELIST_IPS = ["192.168.67.14"]  # IP VM monitoring (skip ML)
BAN_DURATION = 5         # detik
CHECK_INTERVAL = 1       # detik
MAX_FEATURE_AGE = 300    # detik
THRESHOLD = 0.50         # prob threshold
# =====================================


# ============ LOGGING ============
def log(msg):
    now = time.time()
    ts = datetime.datetime.fromtimestamp(now).strftime("%Y-%m-%d %H:%M:%S.%f")
    epoch = f"{now:.6f}"
    text = f"[{epoch}][{ts}] {msg}"
    print(text)
    try:
        with open(LOG_FILE, "a") as f:
            f.write(text + "\n")
    except:
        pass

def write_epoch_log(epoch, msg):
    line = f"{int(epoch)} {msg}\n"
    try:
        with open(EPOCH_LOG, "a") as f:
            f.write(line)
    except:
        log("[WARN] gagal tulis epoch_log")

def append_events_local(epoch, ip, prob, label):
    try:
        new = not os.path.exists(EVENTS_LOCAL_CSV)
        with open(EVENTS_LOCAL_CSV, "a") as f:
            if new:
                f.write("epoch,src_ip,prob,label\n")
            f.write(f"{int(epoch)},{ip},{prob:.4f},{label}\n")
    except:
        pass

def send_telegram(message):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": CHAT_ID, "text": message})
    except:
        log("[WARN] gagal kirim telegram")


# ============ PREP ============
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
os.makedirs(os.path.dirname(EPOCH_LOG), exist_ok=True)
os.makedirs(os.path.dirname(EVENTS_LOCAL_CSV), exist_ok=True)

if not os.path.exists(MODEL_PATH) or not os.path.exists(SCALER_PATH):
    print("[ERROR] Model/scaler tidak ditemukan")
    sys.exit(1)

print("[INFO] Memuat model...")
model = joblib.load(MODEL_PATH)
scaler = joblib.load(SCALER_PATH)
print("[OK] Model dimuat")

send_telegram("🤖 ML Detector aktif!")

banned_ips = {}
_cache_df = None
_cache_mtime = 0

FEATURE_COLS = [
    "destination port",
    "flow bytes/s",
    "min packet length",
    "bwd packets/s",
    "bwd packet length min",
    "min_seg_size_forward",
    "bwd header length",
    "average packet size",
    "max packet length",
    "subflow fwd bytes",
    "bwd packet length mean",
    "packet length mean",
    "subflow bwd packets",
    "fwd header length.1",
    "total backward packets",
    "flow iat max",
    "down/up ratio"
]


# ============ CACHE HANDLING ============
def load_cache():
    global _cache_df, _cache_mtime
    try:
        mtime = os.path.getmtime(CACHE_CSV)
    except:
        return
    if _cache_df is None or mtime != _cache_mtime:
        try:
            _cache_df = pd.read_csv(CACHE_CSV)
            _cache_mtime = mtime
        except:
            log("[WARN] gagal baca cache")

def get_latest_features_for_ip(ip):
    load_cache()
    global _cache_df
    if _cache_df is None or _cache_df.empty:
        return None, None

    df_ip = _cache_df[
        (_cache_df["src_ip"] == ip) &
        (_cache_df.get("destination port", 0) == 22)
    ]

    if df_ip.empty:
        return None, None

    latest = df_ip.sort_values("timestamp", ascending=False).iloc[0]
    age = time.time() - float(latest["timestamp"])
    if age > MAX_FEATURE_AGE:
        return None, None

    feats = [float(latest[c]) if c in latest else 0.0 for c in FEATURE_COLS]
    return feats, FEATURE_COLS


# ============ FIREWALL ============
def ban_ip(ip, prob=0.0):
    now_epoch = int(time.time())
    msg = f"🚨 Diblokir IP {ip} selama {BAN_DURATION} detik (prob={prob:.2f})"

    write_epoch_log(now_epoch, f"ALERT ML {ip} prob={prob:.2f}")
    append_events_local(now_epoch, ip, prob, "SSH-Patator")

    if ip not in banned_ips:
        try:
            subprocess.run([UFW_BIN, "deny", "from", ip], check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            banned_ips[ip] = datetime.datetime.now() + datetime.timedelta(seconds=BAN_DURATION)
        except:
            log(f"[ERROR] gagal ban {ip}")

    log(msg)
    send_telegram(msg)

def unban_ip(ip):
    try:
        subprocess.run([UFW_BIN, "delete", "deny", "from", ip], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        msg = f"✅ IP {ip} telah di-unban."
        log(msg)
        send_telegram(msg)
    except:
        log(f"[ERROR] gagal unban {ip}")
    banned_ips.pop(ip, None)

def check_unban():
    now = datetime.datetime.now()
    for ip, exp in list(banned_ips.items()):
        if now >= exp:
            unban_ip(ip)


# ================== MAIN LOOP ==================
while True:
    try:
        load_cache()

        if _cache_df is not None and not _cache_df.empty:
            for ip in _cache_df["src_ip"].unique():

                # ========== WHITELIST — SKIP ML ==========
                if ip in WHITELIST_IPS:
                    log(f"[WHITELIST] Skipping ML for whitelisted IP {ip}")
                    write_epoch_log(int(time.time()), f"[WHITELIST] skip {ip}")
                    continue
                # ==========================================

                data = get_latest_features_for_ip(ip)
                if data[0] is None:
                    continue

                feats, cols = data
                X_df = pd.DataFrame([feats], columns=cols)
                X_scaled = scaler.transform(X_df)

                try:
                    idx = list(model.classes_).index("SSH-Patator")
                except:
                    idx = None

                if idx is None:
                    pred = model.predict(X_scaled)[0]
                    prob = 1.0 if pred == "SSH-Patator" else 0.0
                else:
                    prob = model.predict_proba(X_scaled)[0][idx]

                label = "SSH-Patator" if prob >= THRESHOLD else "BENIGN"

                now_epoch = int(time.time())

                log(f"[ML] {ip} => {label} (prob={prob:.2f})")
                write_epoch_log(now_epoch, f"[ML] {ip} => {label} (prob={prob:.2f})")
                append_events_local(now_epoch, ip, prob, label)

                if label == "SSH-Patator":
                    ban_ip(ip, prob)

        check_unban()
        time.sleep(CHECK_INTERVAL)

    except KeyboardInterrupt:
        log("[STOP] dihentikan user")
        send_telegram("🛑 ML Detector dimatikan")
        break
    except Exception as e:
        log(f"[ERROR] {e}")
        time.sleep(1)