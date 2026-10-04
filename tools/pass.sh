# One stage-two pass check for a chart folder: lint, snapshot, rerun, compare, report diff bounds.
# Usage, from the project root: tools/pass.sh <module path> <run name> "<chart folder under CHARTS/>"
# e.g. tools/pass.sh src/au_econ/releases/abs/labour_force_6202 lfs "6202 - Labour Force"
set -e
MOD=$1; NAME=$2; D="CHARTS/$3"
uv run ruff check "$MOD"; uv run ruff format --check "$MOD"; uv run mypy "$MOD" | tail -1
mkdir -p scratch && rm -rf scratch/prev && cp -R "$D" scratch/prev
uv run run.py "$NAME" 2>&1 | grep -E " ok | fail"
uv run python tools/compare_charts.py scratch/prev "$D" > scratch/pass.txt || true
grep -v "^DIFF" scratch/pass.txt
uv run python tools/compare_charts.py scratch/prev "$D" $(grep DIFF scratch/pass.txt | awk '{print $2}') | grep rows | awk '{print "rows",$3,$4,"cols",$6,$7}' | sort | uniq -c
rm scratch/pass.txt
