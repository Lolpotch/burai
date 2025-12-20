# labelin dataset dari debian

import pandas as pd

# Path dataset sendiri
own_csv = r"C:\Users\Fiyan\OneDrive\Dokumen\TUGAS KAMPUS\algoritma\OOP\ML\New\Data_REALLLL (Debian)\features_ML_fuel_TOP_17_LOW_THREAD.csv"
# Path dataset CICIDS
cicids_csv = r"C:\Users\Fiyan\OneDrive\Dokumen\TUGAS KAMPUS\algoritma\OOP\ML\New\merge\Fitur_TOP_17.csv"

# Load dataset
own_df = pd.read_csv(own_csv)
cicids_df = pd.read_csv(cicids_csv)

# Aturan labeling
def assign_label(row):
    if (row['src_ip'], row['dst_ip']) in [('67.11', '67.12'), ('67.67', '67.12')]:
        return 'SSH-Patator'
    else:
        return 'BENIGN'

# Tambahkan kolom label huruf kecil
own_df['label'] = own_df.apply(assign_label, axis=1)

# Hapus kolom yang tidak dibutuhkan (kalau memang mau disamakan dengan CICIDS)
own_df = own_df.drop(columns=['src_ip', 'dst_ip', 'timestamp'], errors='ignore')

# Gabungkan dataset
merged_df = pd.concat([cicids_df, own_df], ignore_index=True)

# Simpan dataset gabungan
output_csv = r"C:\Users\Fiyan\OneDrive\Dokumen\TUGAS KAMPUS\algoritma\OOP\ML\New\merge\Fuel_PLUS_CICIDS_PLUS_UP.csv"
merged_df.to_csv(output_csv, index=False)

print(f"Dataset gabungan tersimpan di {output_csv}")
print("Jumlah total data:", merged_df.shape)
print("Kolom:", merged_df.columns.tolist())
print("Label unik:", merged_df['label'].unique())
