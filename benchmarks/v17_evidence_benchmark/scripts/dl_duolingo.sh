#!/bin/bash
# Robust resumable download of the Duolingo HLR learning-traces dataset
# (Settles & Meeder 2016, Harvard Dataverse doi:10.7910/DVN/N8XJME).
# Loops curl with resume (-C -) until the file is complete, then verifies MD5.
# Expected: 379.0 MB, md5 0a1cae5eb7ad4b0bd9c0de91d74fcced

URL="https://dataverse.harvard.edu/api/access/datafile/3091087"
OUT="/home/z/my-project/data/settles.acl16.learning_traces.13m.csv.gz"
MD5_EXPECTED="0a1cae5eb7ad4b0bd9c0de91d74fcced"

for i in $(seq 1 200); do
  size=$(stat -c %s "$OUT" 2>/dev/null || echo 0)
  echo "[try $i] current size: $size"
  if [ "$size" -ge 397000000 ] 2>/dev/null; then
    echo "size looks complete, stopping loop"
    break
  fi
  curl -sL --retry 3 --retry-delay 2 -C - --max-time 900 -o "$OUT" "$URL"
  rc=$?
  echo "[try $i] curl exit: $rc, size now: $(stat -c %s "$OUT" 2>/dev/null || echo 0)"
  if [ $rc -eq 0 ]; then
    echo "curl finished with rc=0"
    break
  fi
  sleep 3
done

echo "=== final size ==="
stat -c %s "$OUT"
echo "=== md5 (expect $MD5_EXPECTED) ==="
md5sum "$OUT"
