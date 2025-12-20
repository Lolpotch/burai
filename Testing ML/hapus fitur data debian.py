import os
import pandas as pd

# ====== CONFIG ======
# Ganti ke path anda
INPUT_FILE = r"C:\Users\Fiyan\OneDrive\Dokumen\TUGAS KAMPUS\algoritma\OOP\ML\New\Data_REALLLL\features_ML_fuel_TOP_17.csv"
OUTPUT_FILE = r"C:\Users\Fiyan\OneDrive\Dokumen\TUGAS KAMPUS\algoritma\OOP\ML\New\Data_REALLLL\features_ML_fuel_TOP_17_REAL.csv"

DROP_COLS = [
    "init_win_bytes_backward", # big outlier
    "init_win_bytes_forward", # big outlier
    "fwd packet length min", # big deviation
    "src_ip", 
    "dst_ip",
    "timestamp",
]

def main():
    if not os.path.exists(INPUT_FILE):
        print(f"[ERROR] File input tidak ditemukan: {INPUT_FILE}")
        return

    try:
        df = pd.read_csv(INPUT_FILE, encoding='utf-8-sig')
    except Exception as e:
        print(f"[ERROR] Gagal membaca CSV: {e}")
        return

    print(f"[INFO] Kolom awal ({len(df.columns)}): {df.columns.tolist()}")

    # Hanya drop kolom yang ada
    present_cols = [c for c in DROP_COLS if c in df.columns]
    missing_cols = [c for c in DROP_COLS if c not in df.columns]

    if present_cols:
        df.drop(columns=present_cols, inplace=True)
        print(f"[INFO] Kolom dihapus: {present_cols}")
    if missing_cols:
        print(f"[WARN] Kolom tidak ditemukan (skip): {missing_cols}")

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)

    try:
        df.to_csv(OUTPUT_FILE, index=False, encoding='utf-8-sig')
        print(f"[OK] File berhasil disimpan: {OUTPUT_FILE}")
        print(f"[INFO] Kolom akhir ({len(df.columns)}): {df.columns.tolist()}")
    except Exception as e:
        print(f"[ERROR] Gagal menyimpan CSV: {e}")

if __name__ == "_main_":
    main()