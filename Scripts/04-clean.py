import pandas as pd
import numpy as np

# Path ke file input & output
input_path = r"YOUR_PATH_TO_BALANCED_CSV_FILE"
output_path = r"CLEANED_CSV_FILE_OUTPUT_LOCATION"

# 1️⃣ Baca file CSV
print("Membaca dataset...")
df = pd.read_csv(input_path)

# 2️⃣ Ganti semua nilai inf / -inf jadi NaN
df.replace([np.inf, -np.inf], np.nan, inplace=True)

# 3️⃣ Hapus baris yang masih ada NaN
rows_before = df.shape[0]
df.dropna(inplace=True)
rows_after = df.shape[0]

# 4️⃣ Simpan hasil yang sudah dibersihkan
df.to_csv(output_path, index=False)

print(f"\n✅ Dataset berhasil dibersihkan dan disimpan sebagai:")
print(f"{output_path}")
print(f"Jumlah baris sebelum dibersihkan: {rows_before}")
print(f"Jumlah baris setelah dibersihkan: {rows_after}")
print(f"Total baris yang dihapus: {rows_before - rows_after}")
