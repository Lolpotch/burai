import pandas as pd

# --- Ubah path CSV sesuai lokasi file kamu ---
data_path = r"C:\Users\Fiyan\OneDrive\Dokumen\TUGAS KAMPUS\algoritma\OOP\ML\New\merge\Fuel_Merged_PROS.csv"

print("Membaca file dataset...")
df = pd.read_csv(data_path)

# cari kolom label (kadang 'label', kadang 'Label')
label_col = None
for cand in ["label", "Label", " Label", "LABEL", " Label "]:
    if cand in df.columns:
        label_col = cand
        break

if not label_col:
    raise ValueError("Kolom label tidak ditemukan! Cek header CSV.")

print(f"Kolom label yang digunakan: {label_col}")
print("Label unik:", df[label_col].unique())

# ambil hanya label BENIGN dan SSH-Patator
df_filtered = df[df[label_col].isin(["BENIGN", "SSH-Patator"])]

# hitung jumlah masing-masing label
label_counts = df_filtered[label_col].value_counts()
print("\nDistribusi label (hanya BENIGN dan SSH-Patator):")
print(label_counts)

# simpan hasil filter ke file baru
output_path = r"C:\Users\Fiyan\OneDrive\Dokumen\TUGAS KAMPUS\algoritma\OOP\ML\datapros\CICIDS_SSH_ONLY(1).csv"
df_filtered.to_csv(output_path, index=False)

print(f"\n✅ Data berhasil difilter dan disimpan ke:\n{output_path}")
print(f"Total baris: {len(df_filtered)}")
