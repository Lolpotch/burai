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
MODEL_PATH = "YOUR_PATH/rf_model.pkl"
SCALER_PATH = "YOUR_PATH/scaler.pkl"
CACHE_CSV = "YOUR_PATH/features_ML_fuel.csv"
LOG_FILE = "YOUR_PATH/log/ml_detector.log"

BOT_TOKEN = "YOUR_BOT_TOKEN_HERE" # EXAMPLE : "123456789:avaDSAFVSbiukjBIbCHAjil"
CHAT_ID = "CHAT_ID_HERE" # EXAMPLE: "126548932"

BAN_DURATION = 5          # detik
CHECK_INTERVAL = 1        # detik
MAX_FEATURE_AGE = 30      # detik (maks umur fitur dalam cache)
# =====================================


def log(msg):
    """Catat log ke file dan tampilkan di console."""
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    text = f"[{ts}] {msg}"
    print(text)
    with open(LOG_FILE, "a") as f:
        f.write(text + "\n")


def send_telegram(message):
    """Kirim pesan Telegram ke grup."""
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": CHAT_ID, "text": message})
    except Exception as e:
        log(f"[WARN] Gagal kirim Telegram: {e}")


# ============ PREPARASI AWAL ============

# Pastikan direktori log ada
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

# Pastikan model dan scaler tersedia
if not os.path.exists(MODEL_PATH) or not os.path.exists(SCALER_PATH):
    print("[ERROR] File model atau scaler tidak ditemukan!")
    sys.exit(1)

# Load model dan scaler
print("[INFO] Memuat model & scaler...")
try:
    model = joblib.load(MODEL_PATH)
    scaler = joblib.load(SCALER_PATH)
except Exception as e:
    print(f"[ERROR] Gagal memuat model atau scaler: {e}")
    sys.exit(1)

print("[OK] Model dan scaler dimuat.")

# Kirim pesan startup Telegram
send_telegram("🤖 *ML Detector aktif!* Siap memantau potensi SSH brute-force attack 🚀")

# =======================================

banned_ips = {}
_cache_df = None
_cache_mtime = 0


def load_cache():
    global _cache_df, _cache_mtime
    try:
        mtime = os.path.getmtime(CACHE_CSV)
    except FileNotFoundError:
        return
    if _cache_df is None or mtime != _cache_mtime:
        try:
            # read with error handling
            df = pd.read_csv(CACHE_CSV)
            ...
        except (pd.errors.EmptyDataError, IOError) as e:
            log(f"[WARN] cache file unreadable (maybe writing): {e}")
            return
    if _cache_df is None or mtime != _cache_mtime:
        try:
            df = pd.read_csv(CACHE_CSV)
            expected_cols = [
                "destination port",
                "flow duration",
                "total backward packets",
                "packet length mean",
                "flow packets/s",
                "fwd iat mean",
                "syn flag count",
                "src_ip",
                "dst_ip",
                "timestamp",
            ]
            df = df[[c for c in expected_cols if c in df.columns]]
            _cache_df = df
            _cache_mtime = mtime
        except Exception as e:
            log(f"[ERROR] Gagal memuat cache: {e}")

def get_latest_features_for_ip(ip):
    """Ambil fitur terbaru untuk IP dari cache."""
    load_cache()
    global _cache_df
    if _cache_df is None or _cache_df.empty:
        return None

    df_ip = _cache_df[_cache_df["src_ip"] == ip]
    if df_ip.empty:
        return None

    latest = df_ip.sort_values("timestamp", ascending=False).iloc[0]
    age = time.time() - latest["timestamp"]

    if age > MAX_FEATURE_AGE:
        # <- taruh debug log di sini
        log(f"[DEBUG] no recent features for {ip} (skipping), age={age:.1f}s")
        return None

    return [
        latest["destination port"],
        latest["flow duration"],
        latest["total backward packets"],
        latest["packet length mean"],
        latest["flow packets/s"],
        latest["fwd iat mean"],
        latest["syn flag count"],
    ]

def ban_ip(ip):
    """Blokir IP sementara."""
    if ip in banned_ips:
        return
    try:
        subprocess.run([UFW_BIN, "deny", "from", ip], check=True, stdout=subprocess.DEVNULL)
        banned_ips[ip] = datetime.datetime.now() + datetime.timedelta(seconds=BAN_DURATION)
        msg = f"🚨 Diblokir IP {ip} selama {BAN_DURATION} detik (SSH brute-force terdeteksi)"
        log(msg)
        send_telegram(msg)
    except subprocess.CalledProcessError as e:
        log(f"[ERROR] Gagal memblokir IP {ip}: {e}")

def unban_ip(ip):
    """Unban IP setelah durasi habis."""
    try:
        subprocess.run([UFW_BIN, "delete", "deny", "from", ip], check=True, stdout=subprocess.DEVNULL)
        banned_ips.pop(ip, None)
        msg = f"✅ IP {ip} telah di-unban."
        log(msg)
        send_telegram(msg)
    except subprocess.CalledProcessError as e:
        log(f"[ERROR] Gagal menghapus aturan untuk {ip}: {e}")


def check_unban():
    """Cek IP yang waktunya sudah habis untuk di-unban."""
    now = datetime.datetime.now()
    for ip, expiry in list(banned_ips.items()):
        if now >= expiry:
            unban_ip(ip)


# ================== LOOP MONITORING ==================

log("[INFO] ML Detector aktif. Memantau IP dari cache...")

while True:
    try:
        load_cache()
        if _cache_df is not None and not _cache_df.empty:
            for ip in _cache_df["src_ip"].unique():
                feats = get_latest_features_for_ip(ip)
                if feats is None:
                    continue
                try:
                    # --- convert to pandas DataFrame with column names to avoid sklearn warning ---
                    cols = [
                        "destination port",
                        "flow duration",
                        "total backward packets",
                        "packet length mean",
                        "flow packets/s",
                        "fwd iat mean",
                        "syn flag count",
                    ]
                    # buat DataFrame dari list fitur; pastikan urutan 'feats' sesuai dengan 'cols'
                    X_df = pd.DataFrame([feats], columns=cols)

                    # transform & predict
                    X_scaled = scaler.transform(X_df)
                    pred = model.predict(X_scaled)[0]
                    # ---------------------------------------------------------------------------
                except Exception as e:
                    log(f"[ERROR] Gagal prediksi untuk IP {ip}: {e}")
                    continue

                if pred == "SSH-Patator":
                    ban_ip(ip)

        check_unban()
        time.sleep(CHECK_INTERVAL)

    except KeyboardInterrupt:
        log("[STOP] Dihentikan oleh user.")
        send_telegram("🛑 ML Detector dimatikan oleh user.")
        break
    except Exception as e:
        log(f"[ERROR] {e}")
        time.sleep(2)
