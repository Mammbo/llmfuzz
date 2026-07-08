#!/usr/bin/env bash
# Mine hard branches from a coverage build in one shot.
#
# Usage:
#   ./mine.sh <cov_harness> <corpus_dir> <include> [out_dir] [libfuzzer|standalone] [cap] [export_bin]
#
# Examples:
#   ./mine.sh /build/libpng/harness_cov corpus/ pngrutil out/libpng libfuzzer
#   ./mine.sh demo/target_cov demo/seeds target.c demo/out standalone
#   ./mine.sh demo/target_cov demo/seeds target.c demo/out standalone 500
#
#   # multi-arg CLI tool (e.g. tiffcp foo.tif out.tif): point HARNESS at a
#   # one-arg wrapper script for the replay loop, and pass the REAL
#   # coverage-instrumented binary as export_bin so llvm-cov export reads
#   # coverage mapping from the actual ELF, not the wrapper shell script.
#   ./mine.sh /tmp/tiffcp_wrapper.sh corpus/ tif out/libtiff_cp standalone 100000 /path/to/tiffcp
#
# Produces:  <out_dir>/cov.json  and  <out_dir>/hard.jsonl
set -euo pipefail

HARNESS="$1"; CORPUS="$2"; INCLUDE="$3"
OUT="${4:-out}"; MODE="${5:-libfuzzer}"
# CAP: max branches to keep (ranked by reached count). The real goal is
# finding ALL hard branches, not a fixed top-N, so default effectively
# uncapped instead of frontier.py's old hardcoded --top 40.
CAP="${6:-100000}"
# per-input wall-clock limit in standalone mode -- one pathological input
# (e.g. a poppler PDF that triggers an infinite loop) must not block the
# whole replay loop forever.
TIMEOUT_S="${TIMEOUT_S:-15}"
HERE="$(cd "$(dirname "$0")" && pwd)"
# resolve the harness to an absolute path so a bare name like "cov_target"
# (which is NOT on $PATH) still runs from the replay loop
[ -e "$HARNESS" ] && HARNESS="$(realpath "$HARNESS")"
# EXPORT_BIN: the binary llvm-cov reads coverage mapping from. Normally the
# same as HARNESS, but when HARNESS is a wrapper script (multi-arg CLI tools
# under the one-arg replay loop) this must point at the real instrumented ELF.
EXPORT_BIN="${7:-$HARNESS}"
[ -e "$EXPORT_BIN" ] && EXPORT_BIN="$(realpath "$EXPORT_BIN")"
mkdir -p "$OUT/prof"

echo "[mine] replaying corpus through $HARNESS ($MODE, cap=$CAP)"
if [ "$MODE" = "libfuzzer" ]; then
  # libFuzzer processes the whole corpus in one run; -runs=0 = execute, don't fuzz
  LLVM_PROFILE_FILE="$OUT/prof/c.profraw" "$HARNESS" -runs=0 "$CORPUS"/* >/dev/null 2>&1 || true
else
  # standalone target that reads argv[1]: one profraw per input
  i=0
  for f in "$CORPUS"/*; do
    LLVM_PROFILE_FILE="$OUT/prof/$i.profraw" timeout "${TIMEOUT_S}s" "$HARNESS" "$f" >/dev/null 2>&1 || true
    i=$((i+1))
  done
fi

echo "[mine] merging profiles + exporting coverage"
llvm-profdata merge "$OUT"/prof/*.profraw -o "$OUT/cov.profdata"
llvm-cov export "$EXPORT_BIN" -instr-profile="$OUT/cov.profdata" > "$OUT/cov.json"

echo "[mine] extracting hard branches (include=$INCLUDE)"
python3 "$HERE/frontier.py" "$OUT/cov.json" --top "$CAP" \
    --include "$INCLUDE" --exclude harness --jsonl "$OUT/hard.jsonl"

echo "[mine] wrote $OUT/hard.jsonl"
echo "[mine] NOTE: review these by hand and keep the 5-10 that are real"
echo "       input-reachable format checks (drop length guards / error paths)."
