#!/bin/bash
# Parallel ranged download of the Duolingo HLR dataset (server supports ranges).
# 16 chunks x ~24MB, downloaded concurrently, then concatenated and md5-verified.
URL="https://dataverse.harvard.edu/api/access/datafile/3091087"
TOTAL=397289705     # will be corrected from the server if wrong
CHUNKS=16
OUT=/home/z/my-project/data/settles.acl16.learning_traces.13m.csv.gz
DIR=/home/z/my-project/data/chunks
MD5_EXPECTED=0a1cae5eb7ad4b0bd9c0de91d74fcced

mkdir -p "$DIR"

# stop the old resume loop if running
pkill -f dl_duolingo.sh 2>/dev/null
pkill -f "curl -sL --retry 3 --retry-delay 2 -C -" 2>/dev/null
sleep 1

# get content-length
LEN=$(curl -sIL "$URL" | tr -d '\r' | awk 'tolower($1)=="content-length:"{print $2}' | tail -1)
if [ -n "$LEN" ] && [ "$LEN" -gt 1000000 ]; then TOTAL=$LEN; fi
echo "total bytes: $TOTAL"

CSIZE=$(( (TOTAL + CHUNKS - 1) / CHUNKS ))

dl_chunk() {
  local i=$1
  local start=$(( i * CSIZE ))
  local end=$(( start + CSIZE - 1 ))
  if [ $end -ge $TOTAL ]; then end=$(( TOTAL - 1 )); fi
  local f="$DIR/part_$(printf '%02d' $i)"
  local want=$(( end - start + 1 ))
  for try in 1 2 3 4 5 6 7 8; do
    local have=$(stat -c %s "$f" 2>/dev/null || echo 0)
    if [ "$have" -eq "$want" ]; then return 0; fi
    curl -sL --max-time 300 -r "$start-$end" -o "$f" "$URL" && {
      have=$(stat -c %s "$f" 2>/dev/null || echo 0)
      [ "$have" -eq "$want" ] && return 0
    }
    sleep 2
  done
  return 1
}

pids=()
for i in $(seq 0 $((CHUNKS-1))); do
  dl_chunk $i &
  pids+=($!)
done
fail=0
for p in "${pids[@]}"; do wait $p || fail=1; done
if [ $fail -ne 0 ]; then echo "SOME CHUNKS FAILED"; exit 1; fi

cat $(ls "$DIR"/part_* | sort) > "$OUT"
echo "assembled: $(stat -c %s "$OUT") bytes (expect $TOTAL)"
echo "md5 check (expect $MD5_EXPECTED):"
md5sum "$OUT"
