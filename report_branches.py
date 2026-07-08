"""Render a hard.jsonl into a shareable markdown report with source context.

    python report_branches.py hard.jsonl --src a.c b.c --out hard_branches.md

Produces a summary table plus, for each branch, the surrounding source with the
target line marked and the unexplored direction noted. This is the artifact to
hand the lab: "here are N hard branches, here's exactly what each one guards."
"""
import argparse, json, pathlib as pl


def context(src: pl.Path, line: int, before=6, after=4) -> str:
    lines = src.read_text(errors="replace").splitlines()
    lo, hi = max(0, line - 1 - before), min(len(lines), line + after)
    out = []
    for i in range(lo, hi):
        mark = "  <-- TARGET (unexplored)" if i == line - 1 else ""
        out.append(f"{i+1:5d}  {lines[i]}{mark}")
    return "\n".join(out)


def resolve(spec: str, srcs):
    p = pl.Path(spec)
    if p.exists():
        return p
    for s in srcs:
        if str(s).endswith(pl.Path(spec).name) or s.name == pl.Path(spec).name:
            return s
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("hard_jsonl", type=pl.Path)
    ap.add_argument("--src", nargs="*", type=pl.Path, default=[])
    ap.add_argument("--out", type=pl.Path, default=pl.Path("hard_branches.md"))
    ap.add_argument("--title", default="Hard branches")
    args = ap.parse_args()

    rows = [json.loads(l) for l in args.hard_jsonl.read_text().splitlines() if l.strip()]
    arm = {"T": "true arm never taken", "F": "false arm never taken"}

    md = [f"# {args.title}", "",
          f"{len(rows)} hard branches (branch reached by the fuzzer, one side "
          f"never taken). Ranked by how many times the taken side executed.", "",
          "| # | location | function | unexplored | times reached |",
          "|---|----------|----------|-----------|--------------|"]
    for i, r in enumerate(rows, 1):
        loc = f'{pl.Path(r["file"]).name}:{r["line"]}'
        md.append(f'| {i} | `{loc}` | `{r["function"]}` | '
                  f'{arm.get(r["missing_arm"], r["missing_arm"])} | {r["reached_count"]} |')
    md.append("")

    for i, r in enumerate(rows, 1):
        src = resolve(r["file"], args.src)
        md.append(f'## {i}. `{pl.Path(r["file"]).name}:{r["line"]}`  '
                  f'({arm.get(r["missing_arm"], r["missing_arm"])})')
        if src:
            md.append("```c")
            md.append(context(src, r["line"]))
            md.append("```")
        else:
            md.append("_(source not provided)_")
        md.append("")

    args.out.write_text("\n".join(md))
    print(f"wrote {args.out} ({len(rows)} branches)")


if __name__ == "__main__":
    main()
