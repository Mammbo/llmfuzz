#!/usr/bin/env bash
# End-to-end AFL++ -> hard branches.
#
#   afl-fuzz produces a queue; this minimizes it (afl-cmin), replays the
#   minimized corpus through a COVERAGE build, and mines source-level hard
#   branches for the LLM. afl-showmap/afl-cmin give edge coverage (useful for
#   minimizing), but the LLM needs SOURCE branch coverage -- that comes from
#   replaying through the coverage build, which is what mine.sh does.
#
# Usage:
#   ./afl_workflow.sh <afl_target> <cov_target> <queue_dir> <include> [out_dir] [libfuzzer|standalone]
#
# Example (this repo's stb demo):
#   ./afl_workflow.sh afl_target cov_target out/default/queue stb_image.h result standalone
#
# You need two builds of the same harness:
#   AFL:       afl-clang-fast -g -O2 harness.c target.c -o afl_target      (+ libAFLDriver.a if it's a libFuzzer harness)
#   coverage:  clang -g -O1 -fprofile-instr-generate -fcoverage-mapping harness.c target.c -o cov_target
set -euo pipefail

AFL_TARGET="$1"; COV_TARGET="$2"; QUEUE="$3"; INCLUDE="$4"
OUT="${5:-aflout}"; MODE="${6:-standalone}"
HERE="$(cd "$(dirname "$0")" && pwd)"
[ -e "$AFL_TARGET" ] && AFL_TARGET="$(realpath "$AFL_TARGET")"
mkdir -p "$OUT"

echo "[afl] minimizing queue with afl-cmin (preserves coverage, drops redundant inputs)"
AFL_SKIP_CPUFREQ=1 AFL_I_DONT_CARE_ABOUT_MISSING_CRASHES=1 \
  afl-cmin -i "$QUEUE" -o "$OUT/mincorpus" -- "$AFL_TARGET" @@

echo "[afl] mining source-level hard branches from the minimized corpus"
"$HERE/mine.sh" "$COV_TARGET" "$OUT/mincorpus" "$INCLUDE" "$OUT" "$MODE"

echo "[afl] done -> $OUT/hard.jsonl"
echo "[afl] next: python3 report_branches.py $OUT/hard.jsonl --src <sources> --out hard.md"
