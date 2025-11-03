import pandas as pd

path = r"C:\Users\Fiyan\OneDrive\Dokumen\TUGAS KAMPUS\algoritma\OOP\ML\dataprosos\CICIDS_merged_split.csv"
df = pd.read_csv(path, nrows=2)
print(list(df.columns))
