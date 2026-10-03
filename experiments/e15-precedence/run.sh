#!/usr/bin/env bash
# experiments/e15-precedence/run.sh
#
# E15 — one resolution order for every consumer (PLAN.md fixes the hypotheses and pass marks).
#
#   before:  the validator as committed at BEFORE_REF (default: the commit before E15's change)
#   (b):     tools/ai-xf-validate.py --resolve, under both parsers
#   (c):     independent/results-indep.json, written by an independent resolver (independent/)
#
# Needs: python3, uv, bun (only to re-run the independent resolver: E15_RERUN_INDEP=1).
# Writes run-out/ (gitignored) and results.json here.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
W="$HERE/run-out"
BEFORE_REF="${BEFORE_REF:-bee8d8c}"
mkdir -p "$W"
cd "$REPO"

git show "$BEFORE_REF:tools/ai-xf-validate.py" > "$W/validate-before.py"
echo "# before: current behaviour per case, and the regression corpus"
python3 "$HERE/measure.py" before "$W/validate-before.py" "$W/before-cases.json"
python3 "$HERE/measure.py" snapshot "$W/validate-before.py" "$W/before-snapshot.json"

echo "# after: the changed validator"
python3 "$HERE/measure.py" resolve tools/ai-xf-validate.py "$W/after-resolve.json"
python3 "$HERE/measure.py" snapshot tools/ai-xf-validate.py "$W/after-snapshot.json"

if [ "${E15_RERUN_INDEP:-0}" = 1 ]; then
  T="$(mktemp -d -t e15indep)"
  cp "$HERE/independent/"*.ts "$HERE/PROPOSED-RULE.md" "$HERE/INTERFACE.md" "$HERE/cases-input.json" "$T/"
  cp -R "$HERE/fixtures" "$T/"
  (cd "$T" && bun run run-cases.ts >/dev/null)
  cp "$T/results-indep.json" "$HERE/independent/results-indep.json"
fi
cp "$HERE/independent/results-indep.json" "$W/results-indep.json"

echo "# H3 suites, H4 nesting"
suite() { if "$@" >/dev/null 2>&1; then echo true; else echo false; fi; }
e2_std=$(cd experiments/e2-resolution && suite python3 -m unittest test_resolution)
e2_py=$(cd experiments/e2-resolution && suite uv run -q --with pyyaml python3 -m unittest test_resolution)
e2_run=$(suite experiments/e2-resolution/run.sh)
ex=$(python3 tools/ai-xf-validate.py examples --level 3 --json | python3 -c 'import json,sys;d=json.load(sys.stdin);print(str(d["passed"] and not d["findings"]).lower())')
base=$(git diff --quiet -- experiments/e2-resolution/baseline-examples-level2.json && echo true || echo false)
printf '{"e2_unittest_stdlib": %s, "e2_unittest_pyyaml": %s, "e2_run_sh": %s, "examples_level3_clean": %s, "e2_baseline_unchanged": %s}\n' \
  "$e2_std" "$e2_py" "$e2_run" "$ex" "$base" > "$W/suites.json"

nest() {  # bundle, parser -> {"passed", "duplicate_id_findings"}
  local pre=(python3); [ "$2" = pyyaml ] && pre=(uv run -q --with pyyaml python3)
  "${pre[@]}" tools/ai-xf-validate.py "$1" --level 2 --json | python3 -c \
    'import json,sys;d=json.load(sys.stdin);print(json.dumps({"passed":d["passed"],"duplicate_id_findings":sum("duplicate id" in f["message"] for f in d["findings"])}))' || true
}
F4="$HERE/fixtures/f4"
printf '{"outer_stdlib": %s, "outer_pyyaml": %s, "team_stdlib": %s, "team_pyyaml": %s}\n' \
  "$(nest "$F4/outer" stdlib)" "$(nest "$F4/outer" pyyaml)" "$(nest "$F4/outer/team" stdlib)" "$(nest "$F4/outer/team" pyyaml)" > "$W/nesting.json"

echo "# compare"
python3 "$HERE/measure.py" compare "$W"
