import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, confusion_matrix
import joblib
import numpy as np

# ===== Konfigurasi =====
INPUT_FILE = r"C:\Users\Fiyan\OneDrive\Dokumen\TUGAS KAMPUS\algoritma\OOP\ML\New\Dataset Scaled\scaled_TOP_17_UPZ.csv"
MODEL_FILE = r"C:\Users\Fiyan\OneDrive\Dokumen\TUGAS KAMPUS\algoritma\OOP\ML\New\Model\rf_model_TOP_17_UPZ.pkl"
THRESHOLD = 0.652  # ubah nilai ini untuk uji threshold
# ========================

print("[INFO] Membaca data siap training...")
df = pd.read_csv(INPUT_FILE)

X = df.drop(columns=["label"])
y = df["label"]

# Split data 80:20
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)

print(f"[INFO] Data train: {X_train.shape}, Data test: {X_test.shape}")

# Buat dan latih model Random Forest
print("[INFO] Melatih model Random Forest...")
rf = RandomForestClassifier(
    n_estimators=100,
    max_depth=None,
    random_state=42,
    n_jobs=-1
)
rf.fit(X_train, y_train)

# === Gunakan predict_proba untuk threshold tuning ===
proba = rf.predict_proba(X_test)
classes = rf.classes_

# Ambil probabilitas untuk kelas attack (SSH-Patator)
attack_idx = np.where(classes == "SSH-Patator")[0][0]
attack_prob = proba[:, attack_idx]

# Terapkan threshold manual
y_pred_custom = np.where(attack_prob >= THRESHOLD, "SSH-Patator", "BENIGN")

print(f"\n=== Threshold Custom: {THRESHOLD} ===")
print(classification_report(y_test, y_pred_custom, digits=4))
print("\n=== Confusion Matrix ===")
print(confusion_matrix(y_test, y_pred_custom))

# Simpan model seperti biasa
joblib.dump(rf, MODEL_FILE)
print(f"[OK] Model berhasil disimpan ke: {MODEL_FILE}")
