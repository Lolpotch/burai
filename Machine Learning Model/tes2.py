import joblib

MODEL_PATH = r"C:\Users\Fiyan\OneDrive\Dokumen\TUGAS KAMPUS\algoritma\OOP\ML\New\Model\rf_model_TOP_20.pkl"

model = joblib.load(MODEL_PATH)

if hasattr(model, "feature_names_in_"):
    print("Fitur model (feature_names_in_):")
    print(list(model.feature_names_in_))
else:
    print("Model tidak menyimpan nama kolom secara eksplisit.")
    if hasattr(model, "n_features_in_"):
        print(f"Jumlah fitur: {model.n_features_in_}")