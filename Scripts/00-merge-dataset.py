import pandas as pd
import glob
import os

# Path ke folder dataset
data_path = r"YOUR_PATH_TO_DATASET_FOLDER"

# Pastikan ada slash/ backslash
all_files = glob.glob(os.path.join(data_path, "*.csv"))

if not all_files:
    print("⚠️ Tidak ada file CSV ditemukan di folder:", data_path)
else:
    # Gabungkan semua file CSV
    df_list = [pd.read_csv(f) for f in all_files]
    merged_df = pd.concat(df_list, ignore_index=True)

    # Simpan hasil gabungan
    output_path = r"YOUR_PATH_TO_OUTPUT_FILE"
    merged_df.to_csv(output_path, index=False)

    print("Jumlah total data:", merged_df.shape)
    print("Label unik:", merged_df['Label'].unique())
