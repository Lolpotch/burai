#!/usr/bin/env python3
"""
Optimized Monitoring Script (ML & Fail2Ban)
- Mengukur Latency, Jitter, PacketLoss, Throughput, CPU, Memory
- Sinkronisasi antar metrik agar data satu waktu lebih akurat
- Menjalankan iperf3 TCP + UDP secara paralel
- Logging CSV, GUI, dan Snapshot Telegram otomatis
"""

import os, time, json, re, threading, subprocess, csv, glob
from datetime import datetime
import paramiko, requests
import matplotlib
from matplotlib.ticker import MaxNLocator

# ==================== CONFIG ====================
ML_IP = "192.168.67.12"
F2B_IP = "192.168.67.13"
SSH_USER = "root"

INTERVAL = 20         # dinaikkan agar pengambilan metrik stabil
HISTORY_LEN = 600
SAVE_INTERVAL = 30

SSH_KEY_PATH = "/root/.ssh/id_rsa"
SSH_KEY_PASSPHRASE = "pros"
SSH_PASSWORD = "1234"

TG_BOT_TOKEN = ""
TG_CHAT_ID   = ""

OUT_DIR = "/home/pros/monitor_out"
os.makedirs(OUT_DIR, exist_ok=True)
CSV_LOG = os.path.join(OUT_DIR, "monitor_log.csv")
# =================================================

if os.environ.get("DISPLAY"):
    try: matplotlib.use("TkAgg")
    except Exception: matplotlib.use("Agg")
else:
    matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec

# Shared history
history = {
    "time": [],
    "ml_throughput": [], "f2b_throughput": [],
    "ml_latency": [], "f2b_latency": [],
    "ml_jitter": [], "f2b_jitter": [],
    "ml_loss": [], "f2b_loss": [],
    "ml_cpu": [], "f2b_cpu": [],
    "ml_mem": [], "f2b_mem": []
}
history_lock = threading.Lock()

# ---------------- SSH Helper ----------------
def _maybe_fix_key_path(path):
    if path.endswith(".pub"):
        c = path[:-4]
        if os.path.exists(c): return c
    return path

def _load_pkey(path, passphrase=None):
    path = _maybe_fix_key_path(path)
    loaders = [
        paramiko.RSAKey.from_private_key_file,
        paramiko.ECDSAKey.from_private_key_file,
        getattr(paramiko, "Ed25519Key", paramiko.RSAKey).from_private_key_file
    ]
    for loader in loaders:
        try:
            return loader(path, password=passphrase) if passphrase else loader(path)
        except Exception:
            continue
    raise RuntimeError(f"Cannot load key {path}")

def run_ssh_command(ip, cmd, timeout=8):
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        kw = {"hostname": ip, "username": SSH_USER, "timeout": 6}
        try:
            if SSH_KEY_PATH: kw["pkey"] = _load_pkey(SSH_KEY_PATH, SSH_KEY_PASSPHRASE)
        except Exception as e:
            print(f"[SSH KEY ERROR] {e}")
        if SSH_PASSWORD: kw["password"] = SSH_PASSWORD
        client.connect(**kw)
        stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
        out, err = stdout.read().decode(), stderr.read().decode()
        client.close()
        if err.strip(): print(f"[SSH STDERR] {ip}: {err.strip()}")
        return out
    except Exception as e:
        print(f"[SSH ERROR] {ip}: {e}")
        return ""

# ---------------- Metric Collectors ----------------
def get_cpu_usage(ip):
    # Baca /proc/stat untuk akurasi tinggi
    out = run_ssh_command(ip, "cat /proc/stat | grep '^cpu '")
    try:
        parts = out.split()
        total = sum(map(int, parts[1:]))
        idle = int(parts[4])
        time.sleep(0.5)
        out2 = run_ssh_command(ip, "cat /proc/stat | grep '^cpu '")
        parts2 = out2.split()
        total2 = sum(map(int, parts2[1:]))
        idle2 = int(parts2[4])
        cpu_usage = 100 * (1 - (idle2 - idle) / (total2 - total))
        return round(cpu_usage, 2)
    except:
        return 0.0

def get_mem_usage(ip):
    out = run_ssh_command(ip, "cat /proc/meminfo | grep -E 'MemTotal|MemAvailable'")
    try:
        lines = out.strip().splitlines()
        total = int(re.findall(r'\d+', lines[0])[0])
        avail = int(re.findall(r'\d+', lines[1])[0])
        used_percent = 100 * (1 - avail / total)
        return round(used_percent, 2)
    except:
        return 0.0

def run_subprocess(cmd, duration):
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=duration+10)
        return proc.stdout
    except Exception as e:
        print(f"[subprocess error] {cmd[0]}: {e}")
        return ""

def get_iperf_throughput(ip, duration=5, port=None):
    cmd = ["iperf3", "-c", ip, "-t", str(duration), "-J"]
    if port: cmd += ["-p", str(port)]
    out = run_subprocess(cmd, duration)
    try:
        data = json.loads(out or "{}")
        end = data.get("end", {})
        bps = end.get("sum_received", {}).get("bits_per_second") or end.get("sum_sent", {}).get("bits_per_second")
        return round(float(bps)/1e6,2) if bps else 0.0
    except:
        return 0.0

def get_udp_jitter_loss(ip, duration=5, port=5202):
    cmd = ["iperf3","-c",ip,"-u","-b","10M","-t",str(duration),"-p",str(port),"-J"]
    out = run_subprocess(cmd, duration)
    try:
        data = json.loads(out or "{}")
        end = data.get("end", {}).get("sum", {})
        jitter = end.get("jitter_ms", 0.0)
        loss = end.get("lost_percent", 0.0)
        return round(jitter,3), round(loss,3)
    except:
        return 0.0, 0.0

def _parse_ping_output(out):
    loss, avg, mdev = 100.0, 0.0, 0.0
    for line in out.splitlines():
        if "packet loss" in line:
            m = re.search(r"(\d+(?:\.\d+)?)% packet loss", line)
            if m: loss = float(m.group(1))
        if "rtt min/avg/max" in line or "rtt min/avg/max/mdev" in line:
            m = re.search(r"=\s*([\d\.]+)/([\d\.]+)/([\d\.]+)/([\d\.]+)", line)
            if m:
                avg = float(m.group(2)); mdev = float(m.group(4))
    return avg, mdev, loss

def get_ping_stats(ip, count=5):
    cmd = ["ping", "-c", str(count), "-W", "2", ip]
    out = run_subprocess(cmd, count)
    return _parse_ping_output(out)

# ---------------- Telegram ----------------
def send_photo_to_telegram(img_path, caption=""):
    if not TG_BOT_TOKEN or not TG_CHAT_ID: return
    if not os.path.exists(img_path): return
    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendPhoto"
    try:
        with open(img_path,"rb") as fh:
            r = requests.post(url,data={"chat_id":TG_CHAT_ID,"caption":caption},files={"photo":fh},timeout=20)
        print(f"[TG] Sent to Telegram ({r.status_code})")
    except Exception as e:
        print(f"[TG error] {e}")

# ---------------- Collector ----------------
def collect_metrics(ip_label, ip):
    """Kumpulkan metrik paralel untuk satu VM"""
    results = {}
    threads = []

    def _wrap(name, func, *args):
        try:
            results[name] = func(*args)
        except Exception as e:
            print(f"[ERROR] {ip_label} {name}: {e}")
            results[name] = 0

    # Jalankan paralel
    threads.append(threading.Thread(target=_wrap, args=("ping", get_ping_stats, ip)))
    threads.append(threading.Thread(target=_wrap, args=("iperf", get_iperf_throughput, ip)))
    threads.append(threading.Thread(target=_wrap, args=("udp", get_udp_jitter_loss, ip)))
    threads.append(threading.Thread(target=_wrap, args=("cpu", get_cpu_usage, ip)))
    threads.append(threading.Thread(target=_wrap, args=("mem", get_mem_usage, ip)))

    for t in threads: t.start()
    for t in threads: t.join()

    latency, jitter, loss, throughput, cpu, mem = 0, 0, 0, 0, 0, 0
    if "ping" in results: latency, _, _ = results["ping"]
    if "udp" in results: jitter, loss = results["udp"]
    if "iperf" in results: throughput = results["iperf"]
    if "cpu" in results: cpu = results["cpu"]
    if "mem" in results: mem = results["mem"]

    return latency, jitter, loss, throughput, cpu, mem

def collect_once():
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now}] Collecting metrics...")

    # Jalankan paralel untuk ML dan F2B
    res = {}
    threads = [
        threading.Thread(target=lambda: res.update({"ml": collect_metrics("ML", ML_IP)})),
        threading.Thread(target=lambda: res.update({"f2b": collect_metrics("F2B", F2B_IP)}))
    ]
    for t in threads: t.start()
    for t in threads: t.join()

    (ml_lat, ml_jit, ml_loss, ml_tput, ml_cpu, ml_mem) = res.get("ml", [0]*6)
    (f2b_lat, f2b_jit, f2b_loss, f2b_tput, f2b_cpu, f2b_mem) = res.get("f2b", [0]*6)

    with history_lock:
        for k,v in {
            "time":now,
            "ml_throughput":ml_tput,"f2b_throughput":f2b_tput,
            "ml_latency":ml_lat,"f2b_latency":f2b_lat,
            "ml_jitter":ml_jit,"f2b_jitter":f2b_jit,
            "ml_loss":ml_loss,"f2b_loss":f2b_loss,
            "ml_cpu":ml_cpu,"f2b_cpu":f2b_cpu,
            "ml_mem":ml_mem,"f2b_mem":f2b_mem
        }.items():
            history[k].append(v)
            if len(history[k])>HISTORY_LEN: history[k].pop(0)

    log_to_csv(now, ml_tput, f2b_tput, ml_lat, f2b_lat, ml_jit, f2b_jit, ml_loss, f2b_loss, ml_cpu, f2b_cpu, ml_mem, f2b_mem)

def log_to_csv(*values):
    header = ["time","ml_throughput","f2b_throughput","ml_latency","f2b_latency",
              "ml_jitter","f2b_jitter","ml_loss","f2b_loss","ml_cpu","f2b_cpu","ml_mem","f2b_mem"]
    file_exists = os.path.exists(CSV_LOG)
    with open(CSV_LOG, "a", newline="") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(header)
        writer.writerow(values)

# ---------------- Plot  ----------------
def save_plot_png(path):
    with history_lock:
        if not history["time"]:
            return
        t = [datetime.strptime(x, "%Y-%m-%d %H:%M:%S").strftime("%H:%M:%S") for x in history["time"]]

        ml_t, f2b_t = list(history["ml_throughput"]), list(history["f2b_throughput"])
        ml_l, f2b_l = list(history["ml_latency"]), list(history["f2b_latency"])
        ml_c, f2b_c = list(history["ml_cpu"]), list(history["f2b_cpu"])
        ml_m, f2b_m = list(history["ml_mem"]), list(history["f2b_mem"])
        ml_j, f2b_j = list(history["ml_jitter"]), list(history["f2b_jitter"])
        ml_loss, f2b_loss = list(history["ml_loss"]), list(history["f2b_loss"])

    fig = plt.figure(figsize=(16,9))
    gs = gridspec.GridSpec(3,2, height_ratios=[1,1,1.3], hspace=0.5, wspace=0.3)

    ax1 = fig.add_subplot(gs[0,0]); ax1.plot(t, ml_t,label="ML"); ax1.plot(t,f2b_t,label="F2B"); ax1.set_title("Throughput (Mbps)"); ax1.legend(); ax1.grid(True)
    ax2 = fig.add_subplot(gs[0,1]); ax2.plot(t, ml_l,label="ML"); ax2.plot(t,f2b_l,label="F2B"); ax2.set_title("Latency (ms)"); ax2.legend(); ax2.grid(True)
    ax3 = fig.add_subplot(gs[1,0]); ax3.plot(t, ml_c,label="ML"); ax3.plot(t,f2b_c,label="F2B"); ax3.set_title("CPU Usage (%)"); ax3.legend(); ax3.grid(True)
    ax4 = fig.add_subplot(gs[1,1]); ax4.plot(t, ml_m,label="ML"); ax4.plot(t,f2b_m,label="F2B"); ax4.set_title("Memory Usage (%)"); ax4.legend(); ax4.grid(True)
    ax5 = fig.add_subplot(gs[2,0]); ax5.plot(t, ml_j,label="ML"); ax5.plot(t,f2b_j,label="F2B"); ax5.set_title("Jitter (ms)"); ax5.legend(); ax5.grid(True)
    ax6 = fig.add_subplot(gs[2,1]); ax6.plot(t, ml_loss,label="ML"); ax6.plot(t,f2b_loss,label="F2B"); ax6.set_title("Packet Loss (%)"); ax6.legend(); ax6.grid(True)

    for ax in [ax1,ax2,ax3,ax4,ax5,ax6]:
        ax.xaxis.set_major_locator(MaxNLocator(nbins=12))
        ax.tick_params(axis='x', labelsize=8)
        for label in ax.get_xticklabels():
            label.set_rotation(45)
            label.set_horizontalalignment('right')

    fig.suptitle(f"MONITORING VM ML & F2B\nTanggal: {datetime.now().strftime('%Y-%m-%d')}", fontsize=16, fontweight="bold", y=0.98)
    fig.tight_layout(rect=[0,0,1,0.95])
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"[SAVE_PLOT] saved {path}")
    cleanup_old_plots()

def cleanup_old_plots(max_files=50):
    files = sorted(glob.glob(os.path.join(OUT_DIR, "monitor_*.png")))
    if len(files)>max_files:
        for f in files[:-max_files]:
            try: os.remove(f)
            except: pass

# ---------------- Threads ----------------
def collector_thread():
    while True:
        try: collect_once()
        except Exception as e: print("[COLLECT ERROR]", e)
        time.sleep(INTERVAL)

def saver_thread():
    while True:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        img = os.path.join(OUT_DIR, f"monitor_{ts}.png")  
        save_plot_png(img)
        threading.Thread(target=send_photo_to_telegram,args=(img,f"Snapshot {ts}"),daemon=True).start()
        time.sleep(SAVE_INTERVAL)

# ---------------- Time Sync ----------------
def sync_time_with_chrony():
    print("[TIME] Menjalankan sinkronisasi waktu dengan chrony...")
    try:
        subprocess.run(["chronyc", "tracking"], check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        subprocess.run(["chronyc", "makestep"], check=False)
        subprocess.run(["chronyc", "sourcestats"], check=False)
        print("[TIME] Sinkronisasi Chrony selesai ✅")
    except Exception as e:
        print(f"[TIME ERROR] Gagal menjalankan chronyc: {e}")
# ---------------- Main ----------------

if __name__ == "__main__":
    sync_time_with_chrony()
    threading.Thread(target=collector_thread,daemon=True).start()
    threading.Thread(target=saver_thread,daemon=True).start()

    if os.environ.get("DISPLAY"):
        from tkinter import Tk, BOTH
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        import matplotlib.animation as animation

        root = Tk()
        root.title("MONITORING VM ML & F2B")

        fig = plt.Figure(figsize=(16,9))
        canvas = FigureCanvasTkAgg(fig, master=root)
        canvas.get_tk_widget().pack(fill=BOTH, expand=True)

        gs = gridspec.GridSpec(3,2,figure=fig, height_ratios=[1,1,1.3], hspace=0.5, wspace=0.3)
        axes = [fig.add_subplot(gs[0,0]),fig.add_subplot(gs[0,1]),fig.add_subplot(gs[1,0]),
                fig.add_subplot(gs[1,1]),fig.add_subplot(gs[2,0]),fig.add_subplot(gs[2,1])]

        def _animate(i):
            with history_lock:
                if not history["time"]: return
                t = [datetime.strptime(x,"%Y-%m-%d %H:%M:%S").strftime("%H:%M:%S") for x in history["time"]]

                for ax in axes: ax.clear()

                axes[0].plot(t, history["ml_throughput"], label="ML"); axes[0].plot(t, history["f2b_throughput"], label="F2B"); axes[0].set_title("Throughput (Mbps)"); axes[0].legend(); axes[0].grid(True)
                axes[1].plot(t, history["ml_latency"], label="ML"); axes[1].plot(t, history["f2b_latency"], label="F2B"); axes[1].set_title("Latency (ms)"); axes[1].legend(); axes[1].grid(True)
                axes[2].plot(t, history["ml_cpu"], label="ML"); axes[2].plot(t, history["f2b_cpu"], label="F2B"); axes[2].set_title("CPU Usage (%)"); axes[2].legend(); axes[2].grid(True)
                axes[3].plot(t, history["ml_mem"], label="ML"); axes[3].plot(t, history["f2b_mem"], label="F2B"); axes[3].set_title("Memory Usage (%)"); axes[3].legend(); axes[3].grid(True)
                axes[4].plot(t, history["ml_jitter"], label="ML"); axes[4].plot(t, history["f2b_jitter"], label="F2B"); axes[4].set_title("Jitter (ms)"); axes[4].legend(); axes[4].grid(True)
                axes[5].plot(t, history["ml_loss"], label="ML"); axes[5].plot(t, history["f2b_loss"], label="F2B"); axes[5].set_title("Packet Loss (%)"); axes[5].legend(); axes[5].grid(True)

                for ax in axes:
                    ax.xaxis.set_major_locator(MaxNLocator(nbins=12))
                    ax.tick_params(axis='x', labelsize=8)
                    for label in ax.get_xticklabels():
                        label.set_rotation(45)
                        label.set_horizontalalignment('right')

                fig.suptitle(f"MONITORING VM ML & F2B\nTanggal: {datetime.now().strftime('%Y-%m-%d')}", fontsize=16, fontweight="bold", y=0.98)
                fig.tight_layout(rect=[0,0,1,0.95])
                canvas.draw_idle()

        ani = animation.FuncAnimation(fig, _animate, interval=INTERVAL*1000)
        root.mainloop()

    else:
        print("[MODE] Headless — running background save & Telegram.")
        while True: time.sleep(60)
