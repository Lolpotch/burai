import pandas as pd
import matplotlib.pyplot as plt
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler

# === ⿡ Load dataset (ganti path sesuai lokasi kamu)
csv_path = r"C:\Users\Fiyan\Downloads\OOP\ML\New\DataProsNew\CICIDS_Balanced_Cleaned.csv"
df = pd.read_csv(csv_path)

# === ⿢ Pastikan label biner (0: BENIGN, 1: SSH-Patator)
df['label'] = df['label'].map({'BENIGN': 0, 'SSH-Patator': 1})

# === ⿣ Pisahkan fitur dan target
X = df.drop(columns=['label'])
y = df['label']

# === ⿤ Normalisasi fitur
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)

# === ⿥ Training model Random Forest
rf = RandomForestClassifier(
    n_estimators=200,       # makin besar makin stabil importance-nya
    random_state=42,
    n_jobs=-1               # gunakan semua core CPU
)
rf.fit(X_scaled, y)

# === ⿦ Hitung feature importance
importance = pd.DataFrame({
    'feature': X.columns,
    'importance': rf.feature_importances_
}).sort_values(by='importance', ascending=False)

# === ⿧ Tampilkan x fitur teratas
top_n = 20
print("\n=== Top {} Fitur Paling Penting ===".format(top_n))
print(importance.head(top_n).to_string(index=False))

# === ⿨ Visualisasi hasil
plt.figure(figsize=(10,6))
plt.barh(
    importance.head(top_n)['feature'][::-1],
    importance.head(top_n)['importance'][::-1],
    color='steelblue'
)
plt.title('Top {} Feature Importance (SSH-Patator vs BENIGN)'.format(top_n))
plt.xlabel('Importance Score')
plt.ylabel('Feature')
plt.tight_layout()
plt.show()

# === ⿩ Simpan hasil ke CSV (opsional)
out_path = r"C:\Users\Fiyan\OneDrive\Dokumen\TUGAS KAMPUS\algoritma\OOP\ML\New\DataProsNew\fitur_penting.csv"
importance.to_csv(out_path, index=False)
print(f"\n📊 Hasil feature importance disimpan ke: {out_path}")