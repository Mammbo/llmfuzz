"""Offline benchmark driver + ablation report.

Reads a benchmark config, runs the offline generator over every hard branch,
verifies each candidate against the coverage build, and reports success rate
broken down by input_type (text/binary) and tools (on/off).

The tools-on vs tools-off split is the core experiment: tools-on gives the
model the structural parse + hexdump + patch contract; tools-off asks it for a
whole-file hex blob with no structural help. That directly tests whether the
tooling layer is what makes non-text targets work.

Config (JSON):
{
  "targets": [
    {
      "name": "libpng",
      "input_type": "binary",
      "src": ["/magma/targets/libpng/png.c", "/magma/.../harness.c"],
      "seed": "/magma/.../seeds/default.png",
      "cov_harness": "/build/libpng/harness_cov",
      "branches": "/out/libpng/hard.jsonl"
    },
    { "name": "tinyexpr", "input_type": "text",
      "src": ["/t/tinyexpr.c","/t/fuzz.c"], "branches": "/out/tinyexpr/hard.jsonl" }
  ]
}
"""
from __future__ import annotations
import argparse, json, pathlib as pl
import offline, probe


def _load_branches(path: pl.Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


def run_one(backend, target: dict, branch: dict, tools: bool,
            agentic: int) -> dict:
    srcs = [pl.Path(s) for s in target.get("src", [])]
    binary = target["input_type"] == "binary"
    seed = pl.Path(target["seed"]).read_bytes() if (binary and tools) else None
    # tools-off on a binary target => force whole-file hex, no structural view
    if binary and not tools:
        seed = None  # generator falls back to text/hex path (no parse/hexdump)

    verifier = probe.replay_verifier(
        target["cov_harness"], branch,
        runner=(lambda h, i: [h, i]) if target.get("standalone") else None,
        export_bin=target.get("export_bin")) \
        if target.get("cov_harness") else (lambda b: (False, "no cov_harness"))

    if agentic > 1:
        _, reached, tr = probe.agentic_generate(
            backend, branch, srcs, seed, verifier, max_iters=agentic)
        iters = len(tr)
    else:
        payload, _, _ = offline.generate(backend, branch, srcs, seed)
        reached, _ = verifier(payload)
        iters = 1
    return {"target": target["name"], "branch": f'{branch["file"]}:{branch["line"]}',
            "input_type": target["input_type"], "tools": tools,
            "reached": bool(reached), "iters": iters}


def report(records: list[dict]) -> dict:
    def rate(rs):
        n = len(rs); k = sum(r["reached"] for r in rs)
        return k, n, (k / n if n else 0.0)

    def line(label, rs):
        k, n, p = rate(rs)
        return f"  {label:<26} {k:>3}/{n:<3}  {p*100:5.1f}%"

    print("\n=== hard-branch reach rate ===")
    print(line("OVERALL", records))
    print("  -- by input type --")
    for t in ("text", "binary"):
        rs = [r for r in records if r["input_type"] == t]
        if rs:
            print(line(t, rs))
    print("  -- by tools (binary only) --")
    for tl in (True, False):
        rs = [r for r in records if r["input_type"] == "binary" and r["tools"] == tl]
        if rs:
            print(line(f"tools={'on' if tl else 'off'}", rs))
    print("  -- per target --")
    for name in sorted({r["target"] for r in records}):
        print(line(name, [r for r in records if r["target"] == name]))

    summary = {
        "overall": rate(records)[2],
        "binary_tools_on": rate([r for r in records
                                 if r["input_type"] == "binary" and r["tools"]])[2],
        "binary_tools_off": rate([r for r in records
                                  if r["input_type"] == "binary" and not r["tools"]])[2],
    }
    return summary


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", type=pl.Path, required=True)
    ap.add_argument("--model", default=None, help="passed to `claude --model`; omit for CLI default")
    ap.add_argument("--tools", choices=["on", "off", "both"], default="both")
    ap.add_argument("--agentic", type=int, default=1, help="max probe iters (1=one-shot)")
    ap.add_argument("--out", type=pl.Path, default=pl.Path("report.json"))
    args = ap.parse_args()

    cfg = json.loads(args.config.read_text())
    backend = offline.ClaudeCLIBackend(model=args.model)
    tool_modes = {"on": [True], "off": [False], "both": [True, False]}[args.tools]

    records = []
    for target in cfg["targets"]:
        branches = _load_branches(pl.Path(target["branches"]))
        for branch in branches:
            for tools in tool_modes:
                if target["input_type"] == "text" and tools is False:
                    continue  # tools ablation is meaningless for text
                records.append(run_one(backend, target, branch, tools, args.agentic))

    summary = report(records)
    args.out.write_text(json.dumps({"summary": summary, "records": records}, indent=2))
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
