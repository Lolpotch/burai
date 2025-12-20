import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.metrics import confusion_matrix
import joblib

# === Konfigurasi ===
MODEL_FILE = r"C:\Users\Fiyan\OneDrive\Dokumen\TUGAS KAMPUS\algoritma\OOP\ML\New\Model\17 Fitur\rf_model_TOP_17_UPZ.pkl"
INPUT_FILE = r"C:\Users\Fiyan\OneDrive\Dokumen\TUGAS KAMPUS\algoritma\OOP\ML\New\Dataset Scaled\scaled_TOP_17_UPZ.csv"

# === Load model dan data ===
print("[INFO] Memuat model dan data...")
model = joblib.load(MODEL_FILE)
df = pd.read_csv(INPUT_FILE)

X = df.drop(columns=["label"])
y = df["label"]

# Konversi label ke biner (BENIGN = 0, SSH-Patator = 1)
y_bin = (y == "SSH-Patator").astype(int)

# Ambil probabilitas prediksi
probs = model.predict_proba(X)[:, 1]

# === Uji berbagai threshold ===
thresholds = np.linspace(0.4, 0.8, 20)
fp_rates = []
fn_rates = []

for t in thresholds:
    preds = (probs >= t).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_bin, preds).ravel()
    fp_rate = fp / (fp + tn)
    fn_rate = fn / (fn + tp)
    fp_rates.append(fp_rate)
    fn_rates.append(fn_rate)

# === Plot hasil ===
plt.figure(figsize=(8,5))
plt.plot(thresholds, fp_rates, marker='o', label="False Positive Rate", color='red')
plt.plot(thresholds, fn_rates, marker='o', label="False Negative Rate", color='blue')
plt.axvline(0.652, color='green', linestyle='--', label="Chosen Threshold = 0.652")
plt.title("Perbandingan FP dan FN terhadap Threshold")
plt.xlabel("Threshold")
plt.ylabel("Rate")
plt.legend()
plt.grid(True)
plt.tight_layout()
plt.show()