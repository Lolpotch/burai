# eksperimen 3 Label

import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, confusion_matrix
import joblib
import numpy as np
import os

# ===== Konfigurasi =====
INPUT_FILE = r"C:\Users\Fiyan\OneDrive\Dokumen\TUGAS KAMPUS\algoritma\OOP\ML\New\Dataset Scaled\scaled_TOP_17_UPS.csv"
MODEL_FILE = r"C:\Users\Fiyan\OneDrive\Dokumen\TUGAS KAMPUS\algoritma\OOP\ML\New\Model\rf_model_TOP_17_UPS.pkl"
SCALER_FILE = r"C:\Users\Fiyan\OneDrive\Dokumen\TUGAS KAMPUS\algoritma\OOP\ML\New\Model\scaler_TOP_17_UPS.pkl"
TEST_SIZE = 0.2
THRESHOLD = 0.65  # threshold opsional (hanya digunakan jika ingin binary scoring)
# ========================

print("[INFO] Membaca data siap training...")
df = pd.read_csv(INPUT_FILE)

# Pastikan kolom label ada
if "label" not in df.columns:
    raise ValueError("Kolom 'label' tidak ditemukan di dataset!")

# Pisahkan fitur dan label
X = df.drop(columns=["label"])
y = df["label"]

# Cek label unik
print(f"[INFO] Label unik yang ditemukan: {y.unique().tolist()}")

# Split data
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=TEST_SIZE, random_state=42, stratify=y
)
print(f"[INFO] Data train: {X_train.shape}, Data test: {X_test.shape}")

# Standarisasi fitur (optional tapi direkomendasikan)
scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train)
X_test_scaled = scaler.transform(X_test)

# Latih model Random Forest
print("[INFO] Melatih model Random Forest untuk 3 kelas...")
rf = RandomForestClassifier(
    n_estimators=150,
    max_depth=None,
    random_state=42,
    n_jobs=-1,
    class_weight="balanced_subsample"
)
rf.fit(X_train_scaled, y_train)

# Prediksi di data uji
y_pred = rf.predict(X_test_scaled)
proba = rf.predict_proba(X_test_scaled)

# === Evaluasi multi-class ===
print("\n=== HASIL EVALUASI (3 KELAS) ===")
print(classification_report(y_test, y_pred, digits=4))
print("\n=== CONFUSION MATRIX ===")
print(pd.DataFrame(confusion_matrix(y_test, y_pred), 
                   index=rf.classes_, columns=rf.classes_))

# === Opsi thresholding khusus untuk SSH-Patator ===
if "SSH-Patator" in rf.classes_:
    ssh_idx = list(rf.classes_).index("SSH-Patator")
    ssh_prob = proba[:, ssh_idx]
    y_pred_thresh = []
    for p, pred in zip(ssh_prob, y_pred):
        if p >= THRESHOLD:
            y_pred_thresh.append("SSH-Patator")
        else:
            y_pred_thresh.append(pred)
    print(f"\n=== Evaluasi dengan Threshold Custom ({THRESHOLD}) untuk SSH-Patator ===")
    print(classification_report(y_test, y_pred_thresh, digits=4))

# === Simpan model & scaler ===
os.makedirs(os.path.dirname(MODEL_FILE), exist_ok=True)
joblib.dump(rf, MODEL_FILE)
joblib.dump(scaler, SCALER_FILE)
print(f"\n[OK] Model berhasil disimpan ke: {MODEL_FILE}")
print(f"[OK] Scaler berhasil disimpan ke: {SCALER_FILE}")