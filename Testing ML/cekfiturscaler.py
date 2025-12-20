import joblib

scaler_path = r"C:\Users\Fiyan\OneDrive\Dokumen\TUGAS KAMPUS\algoritma\OOP\ML\dataprosos\Model\CICIDS_scaler.pkl"
scaler = joblib.load(scaler_path)

print("Jumlah fitur di scaler:", scaler.n_features_in_)
