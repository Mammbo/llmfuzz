#!/usr/bin/env bash
# Package a hard-branch benchmark to share with lab mates.
#
#   ./package_benchmark.sh <name> <hard.jsonl> <corpus_dir> <out_dir> [src files...]
#
# Produces  <out_dir>/<name>/  with:
#   hard.jsonl          the branch list (file:line, missing arm, reached count)
#   hard_branches.md    human-readable report with source context (if src given)
#   corpus/             the seed/queue inputs the branches were mined from
#   MANIFEST.txt        provenance: library, harness, build cmds, how to test
# ...and a <name>_benchmark.tar.gz you can send.
#
# Example:
#   ./package_benchmark.sh libpng result/hard.jsonl result/mincorpus share \
#       /magma/targets/libpng/repo/pngrutil.c /magma/targets/libpng/src/harness.c
set -euo pipefail

NAME="$1"; HARD="$2"; CORPUS="$3"; OUT="$4"; shift 4 || true
SRCS="$*"
HERE="$(cd "$(dirname "$0")" && pwd)"
B="$OUT/$NAME"
mkdir -p "$B/corpus"

cp "$HARD" "$B/hard.jsonl"
if [ -n "$SRCS" ]; then
  python3 "$HERE/report_branches.py" "$HARD" --src $SRCS \
      --out "$B/hard_branches.md" --title "$NAME — hard branches" >/dev/null
fi
cp "$CORPUS"/* "$B/corpus/" 2>/dev/null || true

NBR=$(grep -c . "$HARD" || echo 0)
NCORP=$(ls "$B/corpus" 2>/dev/null | wc -l | tr -d ' ')
cat > "$B/MANIFEST.txt" <<EOF
benchmark : $NAME
created   : $(date -u +%Y-%m-%dT%H:%M:%SZ)
branches  : $NBR   (see hard.jsonl / hard_branches.md)
corpus    : $NCORP files (in corpus/ ; the inputs these branches were mined from)
sources   : $SRCS

FILL IN before sharing (needed to reproduce):
  library + version/commit : e.g. libpng 1.6.40 @ <git sha>
  fuzz harness             : <path/name>

Reproduce (two builds of the same harness):
  afl build : afl-clang-fast -g -O2 <harness.c> <target.c> -o afl_target
              (append libAFLDriver.a if it is a libFuzzer-style harness)
  cov build : clang -g -O1 -fprofile-instr-generate -fcoverage-mapping \\
              <harness.c> <target.c> -o cov_target

Mine (how these branches were produced):
  AFL_SKIP_CPUFREQ=1 afl-fuzz -i seeds -o out -- ./afl_target @@
  ./afl_workflow.sh afl_target cov_target out/default/queue <include> result <mode>

Test with llmfuzz (offline, NO afl needed):
  edit benchmark.json to point at cov_target + hard.jsonl + a seed, then
  python3 run_benchmark.py --config benchmark.json --backend gemini --tools both --agentic 4
EOF

tar czf "$OUT/${NAME}_benchmark.tar.gz" -C "$OUT" "$NAME"
echo "packaged $NBR branches -> $OUT/${NAME}_benchmark.tar.gz"
echo "         (edit $B/MANIFEST.txt to fill in library version + harness before sending)"
