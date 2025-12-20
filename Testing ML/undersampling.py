import pandas as pd

# ==============================
# 1. Load dataset
# ==============================
data_path = r"C:\Users\Fiyan\OneDrive\Dokumen\TUGAS KAMPUS\algoritma\OOP\ML\dataprosos\CICIDS_merged_split.csv"
df = pd.read_csv(data_path)

print("Distribusi awal label:")
print(df['label'].value_counts())

# ==============================
# 2. Pisahkan data berdasarkan label
# ==============================
benign_label = "BENIGN"
attack_label = "SSH-Patator"

benign_df = df[df['label'] == benign_label]
attack_df = df[df['label'] == attack_label]

# ==============================
# 3. Undersampling benign
# ==============================
undersample_n = 6000  # jumlah data benign yang diambil
benign_sampled = benign_df.sample(n=undersample_n, random_state=42)

# ==============================
# 4. Gabungkan data dan shuffle
# ==============================
balanced_df = pd.concat([benign_sampled, attack_df])
balanced_df = balanced_df.sample(frac=1, random_state=42).reset_index(drop=True)

print("\nDistribusi setelah balancing:")
print(balanced_df['label'].value_counts())

# ==============================
# 5. Simpan dataset hasil balancing
# ==============================
output_path = r"C:\Users\Fiyan\OneDrive\Dokumen\TUGAS KAMPUS\algoritma\OOP\ML\dataprosos\CICIDS_Balanced.csv"
balanced_df.to_csv(output_path, index=False)

print(f"\nDataset balanced disimpan ke: {output_path}")
