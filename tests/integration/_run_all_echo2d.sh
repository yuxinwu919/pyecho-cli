#!/usr/bin/env bash
# Sequentially run ECHO2D for every prepared run directory that has input_in.txt.
set -u

BIN="/Users/yuxinwu/my_projects/ECHO2D_CLI/ECHO2D_v3_5/Codes/MacOS_ARM_OpenMP/ECHO2D"
RUNS_ROOT="/Users/yuxinwu/my_projects/ECHO2D_CLI/tests/integration/test_project/runs"
LOG="/Users/yuxinwu/my_projects/ECHO2D_CLI/tests/integration/echo2d_run_log.txt"
SUMMARY="/Users/yuxinwu/my_projects/ECHO2D_CLI/tests/integration/runs_summary.txt"
TIMEOUT_SECS=1800

rm -f "$SUMMARY"
: > "$LOG"

succeeded=0
failed=0
total_runs=0

> "$SUMMARY"

for d in "$RUNS_ROOT"/*/; do
  if [ ! -f "$d/input_in.txt" ]; then
    continue
  fi

  run_name="$(basename "$d")"
  total_runs=$((total_runs + 1))
  echo "=== RUN $run_name ===" | tee -a "$LOG"

  # Snapshot pre-existing files
  find "$d" -type f | sort > /tmp/_echo2d_before_$$.txt

  start=$(perl -e 'print time')
  # Run the solver with a hard per-run timeout guard (SIGALRM, exit 142 on timeout)
  (cd "$d" && OMP_NUM_THREADS=1 perl -e 'alarm shift; exec @ARGV' "$TIMEOUT_SECS" "$BIN") \
    > "$d/.echo2d_stdout.log" 2>&1
  code=$?
  end=$(perl -e 'print time')
  elapsed=$((end - start))

  # Count newly created files
  find "$d" -type f | sort > /tmp/_echo2d_after_$$.txt
  files=$(comm -13 /tmp/_echo2d_before_$$.txt /tmp/_echo2d_after_$$.txt | wc -l | tr -d ' ')
  rm -f /tmp/_echo2d_before_$$.txt /tmp/_echo2d_after_$$.txt

  # Extract any error-ish lines from stdout for the log
  errs=$(grep -iE "error|fail|abort|panic|terminat|crash" "$d/.echo2d_stdout.log" | head -5)
  lastline=$(tail -1 "$d/.echo2d_stdout.log")

  {
    echo "run=$run_name exit=$code time=${elapsed}s new_files=$files"
    echo "last_line: $lastline"
    if [ -n "$errs" ]; then
      echo "error_lines:"
      echo "$errs" | sed 's/^/  /'
    fi
    echo "---"
  } >> "$LOG"

  if [ "$code" -eq 0 ]; then
    succeeded=$((succeeded + 1))
  else
    failed=$((failed + 1))
  fi

  printf '%s | exit=%s | files=%s | time=%ss\n' "$run_name" "$code" "$files" "$elapsed" >> "$SUMMARY"
  echo "  exit=$code time=${elapsed}s new_files=$files" | tee -a "$LOG"
done

echo ""
echo "TOTAL: $total_runs runs | succeeded=$succeeded failed=$failed" | tee -a "$LOG"
