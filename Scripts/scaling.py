import pandas as pd
from sklearn.preprocessing import StandardScaler
import joblib

# ===== Konfigurasi =====
INPUT_FILE = r"C:\Users\Fiyan\OneDrive\Dokumen\TUGAS KAMPUS\algoritma\OOP\ML\New\DataProsNew\features_extracted.csv"
OUTPUT_FILE = r"C:\Users\Fiyan\OneDrive\Dokumen\TUGAS KAMPUS\algoritma\OOP\ML\New\DataProsNew\scaled_features.csv"
SCALER_FILE = r"C:\Users\Fiyan\OneDrive\Dokumen\TUGAS KAMPUS\algoritma\OOP\ML\New\DataProsNew\scaler_7features.pkl"

# ========================
print("[INFO] Membaca data fitur...")
df = pd.read_csv(INPUT_FILE)

# Pisahkan fitur dan label
X = df.drop(columns=["label"])
y = df["label"]

print(f"[INFO] Jumlah fitur: {X.shape[1]} | Jumlah data: {X.shape[0]}")

# Scaling
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)

# Simpan hasil scaling
scaled_df = pd.DataFrame(X_scaled, columns=X.columns)
scaled_df["label"] = y.values

scaled_df.to_csv(OUTPUT_FILE, index=False)
joblib.dump(scaler, SCALER_FILE)

print(f"[OK] Data berhasil dinormalisasi & disimpan ke: {OUTPUT_FILE}")
print(f"[OK] Scaler disimpan ke: {SCALER_FILE}")
print(scaled_df.head())
