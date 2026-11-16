#!/bin/sh
# Usage: sh run-phase4.sh <seed-suffix> <scratch-folder>
# Throwaway database only (see README). The scratch folder holds proof.sqlite3 and the seed scripts seed_proof.py / seed_proof2.py.
# Seeds fresh data, runs both proofs in English and Arabic, and compares the JSON, CSV, Excel and PDF of the Operation report.
SUF="$1"; SP="$2"; OUT="C:/Users/user/Desktop/Innovation-hr/docs/evidence/phase4"
cd C:/Users/user/Desktop/Innovation-hr/backend || exit 1
for f in seed_proof seed_proof2; do DJANGO_DB_PATH="$SP/proof.sqlite3" SP="$SP" SUF="$SUF" .venv/Scripts/python.exe manage.py shell -c "exec(open(r'$SP/$f.py').read())" >/dev/null 2>&1; done
cd ../qa/browser || exit 1
for lang in en ar; do
  PROOF_SEED="$SP/proof2.json" PROOF_OUT="$OUT" node phase4a.js $lang > "$OUT/phase4a-objectives-18-19-$lang.txt" 2>&1
  PROOF_SEED="$SP/proof.json" PROOF_OUT="$OUT" node phase4.js $lang > "$OUT/phase4-objectives-20-21-$lang.txt" 2>&1
  (cd ../../backend && .venv/Scripts/python.exe ../qa/browser/compare_exports.py "$OUT" $lang) > "$OUT/export-compare-$lang.txt" 2>&1
  tail -n 1 "$OUT/phase4a-objectives-18-19-$lang.txt" "$OUT/phase4-objectives-20-21-$lang.txt"; cat "$OUT/export-compare-$lang.txt"
done
