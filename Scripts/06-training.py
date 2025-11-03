import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, confusion_matrix
import joblib

# ===== Konfigurasi =====
INPUT_FILE = r"YOUR_PATH\scaled-dataset.csv"
MODEL_FILE = r"YOUR_PATH\rf_model.pkl"

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

# Evaluasi
y_pred = rf.predict(X_test)
print("\n=== Classification Report ===")
print(classification_report(y_test, y_pred, digits=4))

print("\n=== Confusion Matrix ===")
print(confusion_matrix(y_test, y_pred))

# Simpan model
joblib.dump(rf, MODEL_FILE)
print(f"[OK] Model berhasil disimpan ke: {MODEL_FILE}")
