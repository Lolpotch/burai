import joblib

# Ganti path sesuai model kamu
model_path = r"C:\Users\Fiyan\OneDrive\Dokumen\TUGAS KAMPUS\algoritma\OOP\ML\dataprosos\Model\Mahcine_Learning_REAL.pkl"
model = joblib.load(model_path)

# Cek apakah model punya atribut 'feature_names_in_'
if hasattr(model, "feature_names_in_"):
    print("=== Daftar fitur yang digunakan model ===")
    for i, f in enumerate(model.feature_names_in_):
        print(f"{i+1:02d}. {f}")
else:
    print("Model tidak menyimpan nama fitur (mungkin dilatih dari array numpy).")

print("Jumlah fitur yang digunakan:", model.n_features_in_)
