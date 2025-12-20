#!/usr/bin/env python3
# PCAPWorker.py  -- robust pcap -> feature CSV worker with debug/logging
import os
import time
import traceback
from scapy.utils import PcapReader
from scapy.layers.inet import IP, TCP
from collections import defaultdict
import numpy as np
import pandas as pd

PCAP_DIR = "/home/pros/pcap/rotated"
OUT_CSV = "/home/pros/dataML/features_ML_fuel_TOP_20.csv"   # cache CSV used by ML detector
PROCESSED_LIST = "/home/pros/pcap/log/pcap_processed.list"
WORKER_LOG = "/home/pros/pcap/log/worker.log"

# Safety tuning
MIN_FILE_SIZE = 200        # bytes, skip files smaller than this
STALE_SECONDS = 1.0        # only process file if not modified in last N seconds
SLEEP_AFTER_DETECT = 0.5   # wait before reading new file (give tcpdump a moment)

# === Top20 feature order (must match training order) ===
FEATURE_ORDER = [
    "destination port",
    "flow bytes/s",
    "min packet length",
    "bwd packets/s",
    "bwd packet length min",
    "min_seg_size_forward",
    "bwd header length",
    "average packet size",
    "max packet length",
    "subflow fwd bytes",
    "bwd packet length mean",
    "packet length mean",
    "subflow bwd packets",
    "fwd header length.1",
    "total backward packets",
    "flow iat max",
    "down/up ratio",
    # bookkeeping
    "src_ip",
    "dst_ip",
    "timestamp"
]
# =======================================================

def log(msg):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    text = f"[{ts}] {msg}"
    print(text, flush=True)
    try:
        os.makedirs(os.path.dirname(WORKER_LOG), exist_ok=True)
        with open(WORKER_LOG, "a") as f:
            f.write(text + "\n")
    except Exception:
        pass

def safe_read_pcap(pcap_path):
    try:
        with PcapReader(pcap_path) as rdr:
            try:
                first = next(iter(rdr))
            except Exception:
                pass
    except Exception as e:
        log(f"[WARN] safe_read_pcap: cannot open {pcap_path}: {e}")
        return False
    return True

def process_pcap_file(pcap_path):
    flows = defaultdict(list)  # key=(client_ip, server_ip, server_port)
    try:
        with PcapReader(pcap_path) as rdr:
            for pkt in rdr:
                if IP in pkt and TCP in pkt:
                    sport = int(pkt[TCP].sport)
                    dport = int(pkt[TCP].dport)
                    if sport == 22 or dport == 22:
                        ts = float(pkt.time)
                        plen = int(len(pkt))
                        src = pkt[IP].src
                        dst = pkt[IP].dst
                        flags = int(pkt[TCP].flags)
                        tcp_win = int(getattr(pkt[TCP], "window", 0))
                        try:
                            tcp_hdr_len = int(pkt[TCP].dataofs) * 4
                        except Exception:
                            tcp_hdr_len = 0
                        try:
                            payload_len = len(bytes(pkt[TCP].payload))
                        except Exception:
                            ip_hdr_len = int(getattr(pkt[IP], "ihl", 0)) * 4 if hasattr(pkt[IP], "ihl") else 0
                            payload_len = max(0, plen - ip_hdr_len - tcp_hdr_len)
                        if dport == 22:
                            key = (src, dst, dport)
                            direction = 'fwd'
                        else:
                            key = (dst, src, sport)
                            direction = 'bwd'
                        flows[key].append((ts, plen, direction, flags, tcp_win, tcp_hdr_len, payload_len))
    except Exception as e:
        log(f"[ERROR] Error reading pcap: {pcap_path}: {e}")
        traceback.print_exc()
        return []

    rows = []
    now_ts = time.time()
    for key, items in flows.items():
        try:
            items.sort(key=lambda x: x[0])
            times = [t for (t,_,_,_,_,_,_) in items]
            lens  = [l for (_,l,_,_,_,_,_) in items]
            dirs  = [d for (_,_,d,_,_,_,_) in items]
            flags = [f for (_,_,_,f,_,_,_) in items]
            tcp_wins = [w for (_,_,_,_,w,_,_) in items]
            tcp_hdrs = [h for (_,_,_,_,_,h,_) in items]
            payloads = [p for (_,_,_,_,_,_,p) in items]

            duration = max(times) - min(times) if len(times) > 1 else 0.0
            total_bwd = sum(1 for d in dirs if d == 'bwd')
            total_fwd = sum(1 for d in dirs if d == 'fwd')
            sum_bytes = sum(lens)
            sum_fwd_bytes = sum(l for (l,dirc) in zip(lens, dirs) if dirc == 'fwd')
            sum_bwd_bytes = sum(l for (l,dirc) in zip(lens, dirs) if dirc == 'bwd')

            mean_len = float(np.mean(lens)) if lens else 0.0
            packet_len_min = int(np.min(lens)) if lens else 0
            packet_len_max = int(np.max(lens)) if lens else 0
            pps = float(len(items) / duration) if duration > 0 else float(len(items))
            bwd_pps = float(total_bwd / duration) if duration > 0 else float(total_bwd)

            fwd_times = [t for (t,_,d,_,_,_,_) in items if d == 'fwd']
            fwd_iat = float(np.mean(np.diff(sorted(fwd_times)))) if len(fwd_times) > 1 else 0.0

            iat_all = np.diff(sorted(times)) if len(times) > 1 else np.array([0.0])
            flow_iat_max = float(np.max(iat_all)) if len(iat_all) > 0 else 0.0

            syn_count = sum(1 for f in flags if (int(f) & 0x02) != 0)

            init_win_forward = 0
            init_win_backward = 0
            for (t,l,d,f,w,h,p) in items:
                if d == 'fwd' and init_win_forward == 0:
                    init_win_forward = w
                if d == 'bwd' and init_win_backward == 0:
                    init_win_backward = w
                if init_win_forward and init_win_backward:
                    break

            fwd_payloads = [p for (t,l,d,fl,w,h,p) in items if d == 'fwd']
            bwd_payloads = [p for (t,l,d,fl,w,h,p) in items if d == 'bwd']
            min_seg_size_forward = int(np.min(fwd_payloads)) if fwd_payloads else 0

            bwd_header_len = float(np.mean([h for (t,l,d,fl,w,h,p) in items if d=='bwd'])) if any(d=='bwd' for d in dirs) else 0.0
            fwd_header_len_1 = float(np.mean([h for (t,l,d,fl,w,h,p) in items if d=='fwd'])) if any(d=='fwd' for d in dirs) else 0.0

            fwd_lens = [l for (t,l,d,fl,w,h,p) in items if d == 'fwd']
            bwd_lens = [l for (t,l,d,fl,w,h,p) in items if d == 'bwd']
            fwd_pkt_len_min = int(np.min(fwd_lens)) if fwd_lens else 0
            bwd_pkt_len_min = int(np.min(bwd_lens)) if bwd_lens else 0
            bwd_pkt_len_mean = float(np.mean(bwd_lens)) if bwd_lens else 0.0

            average_pkt_size = mean_len
            subflow_fwd_bytes = int(sum_fwd_bytes)
            subflow_bwd_packets = int(total_bwd)
            down_up_ratio = float(sum_bwd_bytes / sum_fwd_bytes) if sum_fwd_bytes > 0 else 0.0

            client, server, srvport = key

            row = {
                "destination port": int(srvport),
                "flow bytes/s": float(sum_bytes / duration) if duration > 0 else float(sum_bytes),
                "min packet length": int(packet_len_min),
                "bwd packets/s": float(bwd_pps),
                "bwd packet length min": int(bwd_pkt_len_min),
                "min_seg_size_forward": int(min_seg_size_forward),
                "bwd header length": float(bwd_header_len),
                "average packet size": float(average_pkt_size),
                "max packet length": int(packet_len_max),
                "subflow fwd bytes": int(subflow_fwd_bytes),
                "bwd packet length mean": float(bwd_pkt_len_mean),
                "packet length mean": float(mean_len),
                "subflow bwd packets": int(subflow_bwd_packets),
                "fwd header length.1": float(fwd_header_len_1),
                "total backward packets": int(total_bwd),
                "flow iat max": float(flow_iat_max),
                "down/up ratio": float(down_up_ratio),
                "src_ip": client,
                "dst_ip": server,   
                "timestamp": now_ts
            }
            rows.append(row)
        except Exception as e:
            log(f"[ERROR] processing flow {key} in {pcap_path}: {e}")
            traceback.print_exc()
            continue

    return rows

def append_rows_to_csv(rows, out_csv=OUT_CSV):
    if not rows:
        return
    df = pd.DataFrame(rows)
    # pastikan urutan kolom sesuai FEATURE_ORDER
    cols = [c for c in FEATURE_ORDER if c in df.columns]
    df = df[cols]
    header = not os.path.exists(out_csv)
    try:
        df.to_csv(out_csv, mode='a', header=header, index=False)
        log(f"[worker] appended {len(df)} rows to {out_csv}")
    except Exception as e:
        log(f"[ERROR] CSV append failed: {e}")
        try:
            tmp = out_csv + ".tmp"
            df.to_csv(tmp, index=False)
            log(f"[worker] wrote to temp CSV {tmp} (manual inspect needed)")
        except Exception as e2:
            log(f"[ERROR] fallback temp write also failed: {e2}")

def load_processed_set():
    if not os.path.exists(PROCESSED_LIST):
        return set()
    try:
        with open(PROCESSED_LIST, "r") as f:
            return set(line.strip() for line in f if line.strip())
    except Exception as e:
        log(f"[WARN] cannot read processed list: {e}")
        return set()

def add_to_processed(fname):
    try:
        with open(PROCESSED_LIST, "a") as f:
            f.write(fname + "\n")
    except Exception as e:
        log(f"[WARN] failed to add to processed list {fname}: {e}")

def watch_and_process():
    seen = load_processed_set()
    log(f"[INFO] watching {PCAP_DIR} (seen {len(seen)} entries)")
    while True:
        try:
            files = sorted([os.path.join(PCAP_DIR, f) for f in os.listdir(PCAP_DIR) if f.endswith(".pcap")])
            log(f"[debug] found {len(files)} .pcap files")
            for f in files:
                try:
                    if f in seen:
                        continue
                    size = os.path.getsize(f)
                    mtime = os.path.getmtime(f)
                    if size < MIN_FILE_SIZE:
                        log(f"[debug] skipping small file {f} size={size}")
                        add_to_processed(f)
                        seen.add(f)
                        continue
                    age = time.time() - mtime
                    if age < STALE_SECONDS:
                        log(f"[debug] skipping {f} because recently modified ({age:.2f}s)")
                        continue
                    time.sleep(SLEEP_AFTER_DETECT)
                    log(f"[debug] processing file {f} (size={size} age={age:.1f}s)")
                    rows = process_pcap_file(f)
                    log(f"[debug] extracted {len(rows)} rows from {f}")
                    if rows:
                        append_rows_to_csv(rows)
                    add_to_processed(f)
                    seen.add(f)
                except Exception as e:
                    log(f"[ERROR] inner loop error for {f}: {e}")
                    traceback.print_exc()
                    continue
            time.sleep(1)
        except KeyboardInterrupt:
            log("[worker] stopped by user")
            break
        except Exception as e:
            log(f"[worker] loop error: {e}")
            traceback.print_exc()
            time.sleep(2)

if __name__ == "__main__":
    watch_and_process()
