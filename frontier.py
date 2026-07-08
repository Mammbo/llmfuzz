"""Extract 'hard branches' (the fuzzer's frontier) from an llvm-cov export.

A hard branch is a ONE-SIDED branch: the branch point was executed (one arm
has count > 0) but the other arm was never taken (count == 0). That is exactly
"the fuzzer reached this conditional but never flipped it" -- the wall it's
stuck against. llvm-cov reports these natively as partially-covered branches.

Pipeline to produce the input JSON:
    # 1. coverage-mapping build of your libFuzzer harness
    clang -g -O1 -fsanitize=fuzzer -fprofile-instr-generate -fcoverage-mapping \\
        harness.c target.c -o harness_cov
    # 2. replay the SATURATED afl corpus once (no fuzzing), collect a profile
    LLVM_PROFILE_FILE=cov.profraw ./harness_cov -runs=0 corpus_dir/*
    llvm-profdata merge cov.profraw -o cov.profdata
    # 3. export coverage as JSON
    llvm-cov export ./harness_cov -instr-profile=cov.profdata > cov.json
    # 4. mine the frontier
    python frontier.py cov.json --top 20 --include 'target' --exclude harness

Outputs:
  * stdout: one `FILE:LINE` per line, ready to pipe into offline.py --branch
  * --jsonl: richer record per branch (missing arm, reached count, function)
"""
import argparse, json, sys, fnmatch, pathlib as pl


# llvm-cov branch region layout (LLVM >= ~12):
#   [line_start, col_start, line_end, col_end,
#    true_count, false_count, file_id, expanded_file_id, (kind?)]
L_LINE, L_TRUE, L_FALSE = 0, 4, 5


def _iter_branches(cov: dict):
    """Yield (filename, branch_tuple, function_name) across the export.

    Branches live under files[].branches AND functions[].branches; the function
    view carries a name and its own filenames table. We walk functions first
    (to attach names) then fall back to file-level branches for anything a
    function block did not cover.
    """
    seen = set()
    for export in cov.get("data", []):
        for fn in export.get("functions", []):
            fname = fn.get("name", "?")
            files = fn.get("filenames", [])
            for br in fn.get("branches", []):
                fid = br[6] if len(br) > 6 else 0
                path = files[fid] if fid < len(files) else (files[0] if files else "?")
                key = (path, br[L_LINE], br[1] if len(br) > 1 else 0)
                seen.add(key)
                yield path, br, fname
        for f in export.get("files", []):
            path = f.get("filename", "?")
            for br in f.get("branches", []):
                key = (path, br[L_LINE], br[1] if len(br) > 1 else 0)
                if key in seen:
                    continue
                yield path, br, "?"


def _one_sided(br: list):
    """Return ('T'|'F', reached_count) if the branch is one-sided, else None.

    'T' means the TRUE arm is the unexplored direction (true_count == 0),
    'F' means the FALSE arm is unexplored. reached_count is the count on the
    arm that DID execute -- higher = the fuzzer hammered this wall harder.
    """
    if len(br) <= L_FALSE:
        return None
    t, f = br[L_TRUE], br[L_FALSE]
    reached = t > 0 or f > 0
    if not reached:
        return None                      # dead / never-reached: not a frontier
    if t > 0 and f == 0:
        return ("F", t)                  # need to make condition false
    if f > 0 and t == 0:
        return ("T", f)                  # need to make condition true
    return None                          # both arms covered: not hard


def _match(path: str, includes, excludes) -> bool:
    base = pl.Path(path).name
    if includes and not any(
        fnmatch.fnmatch(path, g) or fnmatch.fnmatch(base, g) or g in path
        for g in includes
    ):
        return False
    if excludes and any(
        fnmatch.fnmatch(path, g) or fnmatch.fnmatch(base, g) or g in path
        for g in excludes
    ):
        return False
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cov_json", type=pl.Path, help="llvm-cov export JSON")
    ap.add_argument("--top", type=int, default=20,
                    help="cap number of branches (ranked by reached count)")
    ap.add_argument("--include", action="append", default=[],
                    help="only files matching (glob or substring); repeatable")
    ap.add_argument("--exclude", action="append", default=[],
                    help="drop files matching (glob or substring); repeatable")
    ap.add_argument("--min-reached", type=int, default=1,
                    help="require the reached arm to have >= this count")
    ap.add_argument("--jsonl", type=pl.Path, default=None,
                    help="also write rich per-branch records here")
    args = ap.parse_args()

    cov = json.loads(args.cov_json.read_text())

    rows = []
    dedup = set()
    for path, br, fname in _iter_branches(cov):
        if not _match(path, args.include, args.exclude):
            continue
        res = _one_sided(br)
        if res is None:
            continue
        arm, reached = res
        if reached < args.min_reached:
            continue
        line = br[L_LINE]
        key = (path, line, arm)
        if key in dedup:
            continue
        dedup.add(key)
        rows.append({
            "file": path,
            "line": line,
            "missing_arm": arm,          # direction the fuzzer never took
            "reached_count": reached,    # how hard it hammered the other arm
            "function": fname,
        })

    rows.sort(key=lambda r: r["reached_count"], reverse=True)
    rows = rows[: args.top]

    for r in rows:
        print(f'{r["file"]}:{r["line"]}')

    if args.jsonl:
        with open(args.jsonl, "w") as fh:
            for r in rows:
                fh.write(json.dumps(r) + "\n")

    print(f"# {len(rows)} hard branches", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
