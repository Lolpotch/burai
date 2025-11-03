#!/usr/bin/env python3
import os, time, traceback
from scapy.utils import PcapReader
from scapy.layers.inet import IP, TCP
from collections import defaultdict
import numpy as np
import pandas as pd

PCAP_DIR = "/home/pros/pcap"
OUT_CSV = "/home/pros/dataML/features_ML_fuel.csv"   # cache CSV used by ML detector
PROCESSED_LIST = "/home/pros/pcap/log/pcap_processed.list"

def process_pcap_file(pcap_path):
    flows = defaultdict(list)  # key=(client_ip, server_ip, server_port)
    try:
        with PcapReader(pcap_path) as rdr:
            for pkt in rdr:
                if IP in pkt and TCP in pkt:
                    sport = int(pkt[TCP].sport); dport = int(pkt[TCP].dport)
                    # filter SSH traffic (both directions)
                    if sport == 22 or dport == 22:
                        ts = float(pkt.time)
                        plen = int(len(pkt))
                        src = pkt[IP].src; dst = pkt[IP].dst
                        flags = int(pkt[TCP].flags)
                        # define flow key: client -> server (server has port 22)
                        if dport == 22:
                            key = (src, dst, dport); direction = 'fwd'
                        else:
                            key = (dst, src, sport); direction = 'bwd'
                        flows[key].append((ts, plen, direction, flags))
    except Exception as e:
        print("Error reading pcap:", pcap_path, e)
        traceback.print_exc()
        return []

    rows = []
    now_ts = time.time()
    for key, items in flows.items():
        items.sort(key=lambda x: x[0])
        times = [t for (t,_,_,_) in items]
        lens  = [l for (_,l,_,_) in items]
        dirs  = [d for (_,_,d,_) in items]
        flags = [f for (_,_,_,f) in items]

        duration = max(times) - min(times) if len(times) > 1 else 0.0
        total_bwd = sum(1 for d in dirs if d == 'bwd')
        mean_len = float(np.mean(lens)) if lens else 0.0
        pps = float(len(items) / duration) if duration > 0 else float(len(items))
        fwd_times = [t for (t,_,d,_) in items if d == 'fwd']
        fwd_iat = float(np.mean(np.diff(sorted(fwd_times)))) if len(fwd_times) > 1 else 0.0
        syn_count = sum(1 for f in flags if (int(f) & 0x02) != 0)

        client, server, srvport = key
        rows.append({
            "destination port": int(srvport),
            "flow duration": float(duration),
            "total backward packets": int(total_bwd),
            "packet length mean": float(mean_len),
            "flow packets/s": float(pps),
            "fwd iat mean": float(fwd_iat),
            "syn flag count": int(syn_count),
            "src_ip": client,
            "dst_ip": server,
            "timestamp": now_ts
        })
    return rows

def append_rows_to_csv(rows, out_csv=OUT_CSV):
    if not rows:
        return
    df = pd.DataFrame(rows)
    header = not os.path.exists(out_csv)
    df.to_csv(out_csv, mode='a', header=header, index=False)
    print(f"[worker] appended {len(rows)} rows to {out_csv}")

def load_processed_set():
    if not os.path.exists(PROCESSED_LIST):
        return set()
    with open(PROCESSED_LIST, "r") as f:
        return set(line.strip() for line in f if line.strip())

def add_to_processed(fname):
    with open(PROCESSED_LIST, "a") as f:
        f.write(fname + "\n")

def watch_and_process():
    seen = load_processed_set()
    print("[worker] watching", PCAP_DIR)
    while True:
        try:
            files = sorted([os.path.join(PCAP_DIR, f) for f in os.listdir(PCAP_DIR) if f.endswith(".pcap")])
            for f in files:
                if f in seen:
                    continue
                # wait briefly to ensure tcpdump finished writing
                time.sleep(0.5)
                rows = process_pcap_file(f)
                append_rows_to_csv(rows)
                add_to_processed(f)
                seen.add(f)
            time.sleep(1)
        except KeyboardInterrupt:
            print("[worker] stopped by user")
            break
        except Exception as e:
            print("Worker error:", e)
            time.sleep(2)

if __name__ == "__main__":
    watch_and_process()
