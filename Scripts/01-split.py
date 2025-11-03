import pandas as pd

# Load dataset hasil filter sebelumnya
data_path = r"YOUR_PATH\merged-dataset.csv"
df = pd.read_csv(data_path)


df.columns = df.columns.str.strip()      # hapus spasi depan/belakang
df.columns = df.columns.str.lower()      # jadi huruf kecil semua

print(df.columns.tolist())  # cek ulang

# Ambil hanya data BENIGN dan SSH-Patator
df_attack = df[df['label'].isin(['BENIGN', 'SSH-Patator'])]

print("Jumlah data serangan SSH-Patator:", len(df_attack))
print(df_attack['label'].value_counts())

# Simpan ke file baru
output_path = r"YOUR_PATH\split-dataset.csv"
df_attack.to_csv(output_path, index=False)

print("Dataset tersimpan di:", output_path)
