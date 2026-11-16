#!/bin/sh
# Usage: sh run-phase5.sh <seed-suffix> <scratch-folder>   (same throwaway database as run-phase4.sh)
SUF="$1"; SP="$2"; OUT="C:/Users/user/Desktop/Innovation-hr/docs/evidence/phase5"
mkdir -p "$OUT"
cd C:/Users/user/Desktop/Innovation-hr/backend || exit 1
DJANGO_DB_PATH="${DB:-$SP/proof.sqlite3}" SP="$SP" SUF="$SUF" .venv/Scripts/python.exe manage.py shell -c "exec(open(r'C:/Users/user/Desktop/Innovation-hr/qa/browser/seed/phase5_general_tasks.py').read())" >/dev/null 2>&1
cd ../qa/browser || exit 1
for lang in en ar; do
  PROOF_SEED="$SP/proof3.json" PROOF_OUT="$OUT" node phase5.js $lang > "$OUT/phase5-objective-22-$lang.txt" 2>&1
  tail -n 1 "$OUT/phase5-objective-22-$lang.txt"
done
