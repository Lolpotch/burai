#!/usr/bin/env python3
"""
Monitoring with Full Recovery Detection + GUI (All Metrics)
===========================================================
• Mengecek recovery berdasarkan semua metrik utama
• Baseline dibaca dari file JSON
• Auto-stop opsional bila sistem sudah recover
• GUI realtime (TkAgg/X11) + snapshot & notifikasi Telegram
• Tidak ada warning tight_layout/thread
"""

import os, time, json, threading, subprocess, csv, re, requests, warnings
from datetime import datetime
import paramiko
import matplotlib
warnings.filterwarnings("ignore", category=UserWarning)

# ==================== CONFIG ====================
ML_IP = "192.168.67.12"
F2B_IP = "192.168.67.13"
SSH_USER = "root"

INTERVAL = 20
SAVE_INTERVAL = 30
HISTORY_LEN = 600

SSH_KEY_PATH = "/root/.ssh/id_rsa"
SSH_KEY_PASSPHRASE = "pros"
SSH_PASSWORD = "1234"

TG_BOT_TOKEN = ""
TG_CHAT_ID = ""

OUT_DIR = "/home/pros/monitor_out"
os.makedirs(OUT_DIR, exist_ok=True)
CSV_LOG = os.path.join(OUT_DIR, "monitor_log_recovery_light_all.csv")

BASELINE_JSON = "/home/pros/test_results_qos_light/baseline_used.json"

THRESHOLD_PCT = 10.0
CONSECUTIVE_OK = 3
AUTO_STOP_AFTER_RECOVERY = False

# pilih backend sesuai environment
if os.environ.get("DISPLAY"):
    matplotlib.use("TkAgg")
else:
    matplotlib.use("Agg")

import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.ticker import MaxNLocator

# ==================== GLOBAL ====================
history = {k: [] for k in [
    "time",
    "ml_throughput","f2b_throughput",
    "ml_latency","f2b_latency",
    "ml_jitter","f2b_jitter",
    "ml_loss","f2b_loss",
    "ml_cpu","f2b_cpu",
    "ml_mem","f2b_mem"
]}
history_lock = threading.Lock()

baseline = None
recovery_counter = 0
recovery_reported = False
last_saved_plot = None

# ==================== UTILS ====================
def send_telegram(msg):
    if not TG_BOT_TOKEN or not TG_CHAT_ID:
        return
    try:
        requests.post(f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage",
                      data={"chat_id": TG_CHAT_ID, "text": msg}, timeout=10)
    except Exception as e:
        print("[TG Error]", e)

def send_photo_to_telegram(path, caption=""):
    if not TG_BOT_TOKEN or not TG_CHAT_ID or not os.path.exists(path):
        return
    try:
        with open(path, "rb") as f:
            requests.post(f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendPhoto",
                          data={"chat_id": TG_CHAT_ID, "caption": caption},
                          files={"photo": f}, timeout=15)
    except Exception as e:
        print("[TG photo error]", e)

def _maybe_fix_key_path(p):
    return p[:-4] if p.endswith(".pub") else p

def _load_key(p, passphrase):
    p = _maybe_fix_key_path(p)
    for loader in [paramiko.RSAKey.from_private_key_file, paramiko.ECDSAKey.from_private_key_file]:
        try:
            return loader(p, password=passphrase)
        except:
            continue
    raise RuntimeError(f"Cannot load key {p}")

def run_ssh(ip, cmd):
    try:
        cli = paramiko.SSHClient()
        cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        kw = {"hostname": ip, "username": SSH_USER, "timeout": 6}
        if SSH_PASSWORD: kw["password"] = SSH_PASSWORD
        if SSH_KEY_PATH: kw["pkey"] = _load_key(SSH_KEY_PATH, SSH_KEY_PASSPHRASE)
        cli.connect(**kw)
        stdin, stdout, stderr = cli.exec_command(cmd, timeout=10)
        out = stdout.read().decode()
        cli.close()
        return out
    except Exception as e:
        print(f"[SSH ERROR] {ip}: {e}")
        return ""

# ==================== METRICS ====================
def get_cpu_usage(ip):
    a = run_ssh(ip, "grep '^cpu ' /proc/stat").split()
    if not a: return 0.0
    total1, idle1 = sum(map(int, a[1:])), int(a[4])
    time.sleep(0.5)
    b = run_ssh(ip, "grep '^cpu ' /proc/stat").split()
    if not b: return 0.0
    total2, idle2 = sum(map(int, b[1:])), int(b[4])
    try:
        return round(100*(1 - (idle2-idle1)/(total2-total1)), 2)
    except:
        return 0.0

def get_mem_usage(ip):
    out = run_ssh(ip, "grep -E 'MemTotal|MemAvailable' /proc/meminfo")
    try:
        lines = out.strip().splitlines()
        total = int(re.findall(r'\d+', lines[0])[0])
        avail = int(re.findall(r'\d+', lines[1])[0])
        return round(100*(1 - avail/total), 2)
    except:
        return 0.0

def run_subprocess(cmd, duration):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=duration+10)
        return p.stdout
    except:
        return ""

def get_iperf(ip, dur=5, udp=False, port=None):
    cmd = ["iperf3","-c",ip,"-t",str(dur),"-J"]
    if udp: cmd += ["-u","-b","10M","-p",str(port or 5202)]
    out = run_subprocess(cmd, dur)
    try:
        data = json.loads(out)
        end = data["end"]["sum" if udp else "sum_received"]
        if udp:
            return end.get("jitter_ms",0.0), end.get("lost_percent",0.0)
        else:
            return round(end.get("bits_per_second",0)/1e6,2)
    except:
        return (0.0,0.0) if udp else 0.0

def get_ping(ip, c=5):
    out = run_subprocess(["ping","-c",str(c),ip], c)
    m_loss = re.search(r"(\d+(?:\.\d+)?)% packet loss", out)
    m_rtt = re.search(r"= [\d\.]+/([\d\.]+)/[\d\.]+/([\d\.]+)", out)
    loss = float(m_loss.group(1)) if m_loss else 100.0
    avg = float(m_rtt.group(1)) if m_rtt else 0.0
    mdev = float(m_rtt.group(2)) if m_rtt else 0.0
    return avg, mdev, loss

# ==================== BASELINE & RECOVERY ====================
def load_baseline():
    global baseline
    try:
        with open(BASELINE_JSON,"r") as f:
            baseline = json.load(f)
        print(f"[BASELINE] Loaded from {BASELINE_JSON}")
    except Exception as e:
        print(f"[BASELINE] Failed: {e}")

def check_recovery(latest):
    if not baseline: return False
    for key, val in latest.items():
        if key == "time": continue
        base = baseline.get(key, {}).get("mean", None)
        if base is None or base == 0:
            continue
        if abs(val - base) > (base * THRESHOLD_PCT / 100):
            return False
    return True

def register_recovery():
    global recovery_reported, last_saved_plot
    recovery_reported = True
    ts = int(time.time())
    msg = f"✅ System fully recovered (all metrics) at {datetime.utcfromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S UTC')}"
    print("[RECOVERY]", msg)
    send_telegram(msg)
    if last_saved_plot:
        send_photo_to_telegram(last_saved_plot, "Recovery snapshot")

# ==================== MONITOR CORE ====================
def collect_metrics(ip):
    res = {}
    threads = [
        threading.Thread(target=lambda: res.update({"ping": get_ping(ip)})),
        threading.Thread(target=lambda: res.update({"iperf": get_iperf(ip)})),
        threading.Thread(target=lambda: res.update({"udp": get_iperf(ip, 5, True, 5202)})),
        threading.Thread(target=lambda: res.update({"cpu": get_cpu_usage(ip)})),
        threading.Thread(target=lambda: res.update({"mem": get_mem_usage(ip)}))
    ]
    [t.start() for t in threads]; [t.join() for t in threads]
    lat,jit,loss,tput,cpu,mem = 0,0,0,0,0,0
    if "ping" in res: lat,_,loss = res["ping"]
    if "udp" in res: jit,loss = res["udp"]
    if "iperf" in res: tput = res["iperf"]
    if "cpu" in res: cpu = res["cpu"]
    if "mem" in res: mem = res["mem"]
    return lat,jit,loss,tput,cpu,mem

def log_to_csv(values):
    h = ["time","ml_throughput","f2b_throughput","ml_latency","f2b_latency",
         "ml_jitter","f2b_jitter","ml_loss","f2b_loss","ml_cpu","f2b_cpu","ml_mem","f2b_mem"]
    f_exists = os.path.exists(CSV_LOG)
    with open(CSV_LOG,"a",newline="") as f:
        w=csv.writer(f)
        if not f_exists: w.writerow(h)
        w.writerow(values)

def collect_once():
    global recovery_counter
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now}] Collecting metrics...")
    res = {}
    threads = [
        threading.Thread(target=lambda: res.update({"ml": collect_metrics(ML_IP)})),
        threading.Thread(target=lambda: res.update({"f2b": collect_metrics(F2B_IP)}))
    ]
    [t.start() for t in threads]; [t.join() for t in threads]
    ml = res.get("ml",[0]*6); f2b = res.get("f2b",[0]*6)
    with history_lock:
        data = {
            "time":now,
            "ml_throughput":ml[3],"f2b_throughput":f2b[3],
            "ml_latency":ml[0],"f2b_latency":f2b[0],
            "ml_jitter":ml[1],"f2b_jitter":f2b[1],
            "ml_loss":ml[2],"f2b_loss":f2b[2],
            "ml_cpu":ml[4],"f2b_cpu":f2b[4],
            "ml_mem":ml[5],"f2b_mem":f2b[5]
        }
        for k,v in data.items():
            history[k].append(v)
            if len(history[k])>HISTORY_LEN: history[k].pop(0)
        log_to_csv(list(data.values()))

        if not recovery_reported:
            if check_recovery(data):
                recovery_counter += 1
                print(f"[RECOVERY] OK {recovery_counter}/{CONSECUTIVE_OK}")
                if recovery_counter >= CONSECUTIVE_OK:
                    register_recovery()
                    if AUTO_STOP_AFTER_RECOVERY:
                        os._exit(0)
            else:
                recovery_counter = 0

# ==================== PLOT + GUI ====================
def save_plot(path):
    with history_lock:
        if not history["time"]: return
        t=[datetime.strptime(x,"%Y-%m-%d %H:%M:%S").strftime("%H:%M:%S") for x in history["time"]]
        fig=plt.figure(figsize=(16,9))
        gs=gridspec.GridSpec(3,2,figure=fig,hspace=0.5,wspace=0.3)
        titles=["Throughput","Latency","CPU","Memory","Jitter","Packet Loss"]
        keys=[("ml_throughput","f2b_throughput"),("ml_latency","f2b_latency"),
              ("ml_cpu","f2b_cpu"),("ml_mem","f2b_mem"),("ml_jitter","f2b_jitter"),("ml_loss","f2b_loss")]
        for i,(k1,k2) in enumerate(keys):
            ax=fig.add_subplot(gs[i//2,i%2])
            ax.plot(t,history[k1],label="ML"); ax.plot(t,history[k2],label="F2B")
            ax.set_title(titles[i]); ax.legend(); ax.grid(True)
            ax.xaxis.set_major_locator(MaxNLocator(nbins=12))
            ax.tick_params(axis='x',labelsize=8,rotation=45)
        fig.subplots_adjust(top=0.95)
        fig.savefig(path,dpi=150)
        plt.close(fig)
        print(f"[SAVE_PLOT] saved {path}")

def saver_thread():
    global last_saved_plot
    while True:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path=os.path.join(OUT_DIR,f"monitor_{ts}.png")
        save_plot(path)
        last_saved_plot=path
        threading.Thread(target=send_photo_to_telegram,args=(path,f"Snapshot {ts}"),daemon=True).start()
        time.sleep(SAVE_INTERVAL)

# ==================== MAIN ====================
if __name__=="__main__":
    load_baseline()
    threading.Thread(target=saver_thread,daemon=True).start()
    
    if os.environ.get("DISPLAY"):
        from tkinter import Tk, BOTH
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        import matplotlib.animation as animation

        root = Tk()
        root.title("Monitoring VM ML & F2B (Full Metrics)")

        fig = plt.Figure(figsize=(16,9))
        canvas = FigureCanvasTkAgg(fig, master=root)
        canvas.get_tk_widget().pack(fill=BOTH, expand=True)

        gs = gridspec.GridSpec(3,2,figure=fig,hspace=0.5,wspace=0.3)
        axes = [fig.add_subplot(gs[i//2,i%2]) for i in range(6)]
        titles=["Throughput","Latency","CPU","Memory","Jitter","Packet Loss"]
        pairs=[("ml_throughput","f2b_throughput"),("ml_latency","f2b_latency"),
               ("ml_cpu","f2b_cpu"),("ml_mem","f2b_mem"),("ml_jitter","f2b_jitter"),("ml_loss","f2b_loss")]

        def animate(i):
            with history_lock:
                if not history["time"]: return
                t=[datetime.strptime(x,"%Y-%m-%d %H:%M:%S").strftime("%H:%M:%S") for x in history["time"]]
                for ax,(k1,k2),title in zip(axes,pairs,titles):
                    ax.clear()
                    ax.plot(t,history[k1],label="ML"); ax.plot(t,history[k2],label="F2B")
                    ax.set_title(title); ax.legend(); ax.grid(True)
                    ax.xaxis.set_major_locator(MaxNLocator(nbins=12))
                    ax.tick_params(axis='x',labelsize=8,rotation=45)
            fig.subplots_adjust(top=0.95)
            canvas.draw_idle()

        threading.Thread(target=lambda: (
            [collect_once() or time.sleep(INTERVAL) for _ in iter(int,1)]
        ),daemon=True).start()

        animation.FuncAnimation(fig, animate, interval=INTERVAL*1000)
        root.mainloop()
    else:
        print("[MODE] Headless — no display available.")
        while True:
            try: collect_once()
            except Exception as e: print("[COLLECT ERROR]", e)
            time.sleep(INTERVAL)
