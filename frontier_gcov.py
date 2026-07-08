"""Mine hard branches from gcov output (the afl-cov / AFL-corpus path).

Use this when your coverage comes from gcov instead of llvm-cov -- e.g. you
replay the AFL++ queue through a `gcc --coverage` build (exactly what afl-cov
does). The hard-branch definition is identical to the llvm-cov path: a source
line that WAS executed but has one branch taken 0 times while a sibling branch
was taken > 0 ("reached but never flipped").

    # replay the AFL queue through a gcov build, then:
    gcov -b -c yourfile.gcda
    python frontier_gcov.py *.gcov --top 20 --include png --jsonl hard.jsonl

Emits the SAME hard.jsonl schema frontier.py does, so offline.py / probe.py /
report_branches.py consume it unchanged.

Note: gcov does not cleanly label the unexplored side true/false (its
"(fallthrough)" annotation is compiler-dependent), so missing_arm is recorded
as "?"; the LLM infers direction from the source. If you need T/F, use the
llvm-cov path (frontier.py), which reports it exactly.
"""
import argparse, json, re, sys, fnmatch, pathlib as pl

# `      8*:    8:    if (...)`  ->  count token, line number, code
_SRC = re.compile(r"^\s*([^:]+):\s*(\d+):(.*)$")
# `branch  0 taken 8 (fallthrough)`  |  `branch 1 never executed`
_BR = re.compile(r"^branch\s+(\d+)\s+(?:taken\s+(\d+)|(never executed))")


def _count(tok: str):
    tok = tok.strip().rstrip("*")
    if tok in ("-", "#####", "$$$$$", "====="):
        return None            # non-executable / never-executed line
    return int(tok) if tok.isdigit() else None


def parse_gcov(path: pl.Path):
    """Yield hard-branch dicts from one .gcov file."""
    source = path.stem            # fallback; overwritten by Source: header
    cur_line = None
    cur_count = 0
    taken = []                    # branch taken-counts for the current line (None=unreached)
    text = path.read_text(errors="replace").splitlines()

    def flush():
        if cur_line is None or cur_count in (None, 0):
            return None
        reached = [t for t in taken if t is not None]      # branches whose block ran
        if not reached:
            return None
        if any(t == 0 for t in reached) and any(t > 0 for t in reached):
            return {"file": source, "line": cur_line, "missing_arm": "?",
                    "reached_count": max(reached), "function": "?"}
        return None

    results = []
    for line in text:
        m = _SRC.match(line)
        if m:
            code = m.group(3)
            lineno = int(m.group(2))
            if lineno == 0:
                if code.startswith("Source:"):
                    source = code[len("Source:"):]
                continue
            hb = flush()
            if hb:
                results.append(hb)
            cur_line, cur_count, taken = lineno, _count(m.group(1)), []
            continue
        b = _BR.match(line.strip())
        if b and cur_line is not None:
            if b.group(3):                 # "never executed"
                taken.append(None)
            else:
                taken.append(int(b.group(2)))
    hb = flush()
    if hb:
        results.append(hb)
    yield from results


def _match(path, includes, excludes):
    base = pl.Path(path).name
    if includes and not any(g in path or fnmatch.fnmatch(base, g) for g in includes):
        return False
    if excludes and any(g in path or fnmatch.fnmatch(base, g) for g in excludes):
        return False
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("gcov", nargs="+", type=pl.Path, help=".gcov files")
    ap.add_argument("--top", type=int, default=20)
    ap.add_argument("--include", action="append", default=[])
    ap.add_argument("--exclude", action="append", default=[])
    ap.add_argument("--jsonl", type=pl.Path, default=None)
    args = ap.parse_args()

    rows, seen = [], set()
    for gp in args.gcov:
        for hb in parse_gcov(gp):
            if not _match(hb["file"], args.include, args.exclude):
                continue
            key = (hb["file"], hb["line"])
            if key in seen:
                continue
            seen.add(key)
            rows.append(hb)

    rows.sort(key=lambda r: r["reached_count"], reverse=True)
    rows = rows[: args.top]
    for r in rows:
        print(f'{r["file"]}:{r["line"]}')
    if args.jsonl:
        args.jsonl.write_text("\n".join(json.dumps(r) for r in rows))
    print(f"# {len(rows)} hard branches", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
