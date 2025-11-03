import pandas as pd
import numpy as np

# ===== Konfigurasi =====
INPUT_FILE = r"C:\Users\Fiyan\OneDrive\Dokumen\TUGAS KAMPUS\algoritma\OOP\ML\dataprosos\CICIDS_Balanced_Cleaned.csv"
OUTPUT_FILE = r"C:\Users\Fiyan\OneDrive\Dokumen\TUGAS KAMPUS\algoritma\OOP\ML\New\DataProsNew\features_extracted.csv"

FEATURES = [
    "destination port",
    "flow duration",
    "total backward packets",
    "packet length mean",
    "flow packets/s",
    "fwd iat mean",
    "syn flag count",
    "label"
]

# ========================

print("[INFO] Membaca dataset mentah...")
df = pd.read_csv(INPUT_FILE)

# Ambil hanya 2 label penting
df = df[df["label"].isin(["BENIGN", "SSH-Patator"])].copy()

# Cek apakah semua fitur tersedia
missing = [c for c in FEATURES if c not in df.columns]
if missing:
    raise SystemExit(f"[ERROR] Kolom hilang: {missing}")

# Pilih fitur yang diperlukan
df = df[FEATURES]

# Bersihkan nilai inf dan NaN
df.replace([np.inf, -np.inf], np.nan, inplace=True)
df.dropna(inplace=True)

# Simpan hasil bersih
df.to_csv(OUTPUT_FILE, index=False)

print(f"[OK] Fitur berhasil diekstrak & disimpan ke: {OUTPUT_FILE}")
print("\n[INFO] Jumlah data per label:")
print(df["label"].value_counts())
print(f"[INFO] Total data: {len(df)} baris")
print(df.head())
