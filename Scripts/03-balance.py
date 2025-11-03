#!/usr/bin/env python3
import pandas as pd
from sklearn.utils import resample

INPUT_FILE = r"YOUR_PATH\extracted-features-dataset.csv"
OUTPUT_FILE = r"YOUR_PATH\balanced-dataset.csv"
RANDOM_STATE = 42

print("[INFO] Membaca data fitur...")
df = pd.read_csv(INPUT_FILE)

# Pisahkan dua kelas
df_attack = df[df["label"] == "SSH-Patator"]
df_benign = df[df["label"] == "BENIGN"]

print(f"[INFO] Jumlah BENIGN: {len(df_benign)}, SSH-Patator: {len(df_attack)}")

# Undersample BENIGN
df_b_down = resample(
    df_benign,
    replace=False,
    n_samples=len(df_attack),
    random_state=RANDOM_STATE
)

# Gabungkan dan acak
df_balanced = pd.concat([df_attack, df_b_down]).sample(frac=1, random_state=RANDOM_STATE)
df_balanced.to_csv(OUTPUT_FILE, index=False)

print(f"[OK] Dataset seimbang disimpan ke: {OUTPUT_FILE}")
print(df_balanced["label"].value_counts())
