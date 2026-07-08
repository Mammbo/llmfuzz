"""Offline LLM input generator (text + binary).

Given source files and one hard branch, ask an LLM for an input that reaches
the branch. Two modes:

  text   : model emits the input verbatim (UTF-8) -- unchanged from v1.
  binary : model is handed a valid --seed plus tool output (parse + hexdump)
           and emits a PATCH (offset/hex edits); we materialize it against the
           seed and repair checksums. This is the non-text path Penghui flagged:
           the model reasons over a text view of the bytes, not the raw bytes.

Backend: shells out to the Claude CLI (`claude --print`) -- no API key needed,
rides your Claude Pro/Max subscription instead of a Vertex/Gemini service account.
"""
from __future__ import annotations
import argparse, json, re, subprocess, sys, pathlib as pl
import formats as F


# ----------------------------------------------------------------- prompts
PROMPT_TEXT = """You are an expert at constructing inputs for fuzz harnesses.

Produce ONE input that causes execution to reach the target branch. The bytes
in the fenced `input` block are written verbatim (UTF-8) and passed to the
harness.

## Target branch
File: {branch_file}
Line: {branch_line}   (unexplored direction: {missing_arm})

Surrounding code:
```c
{branch_context}
```

## Source files
{sources}

Reason about how input bytes propagate into the library and what the branch
requires, then respond with exactly one fenced block:

```input
<the input the harness should read>
```
"""

PROMPT_BINARY = """You are an expert at constructing binary inputs for fuzz harnesses.

You are given a VALID seed file of format `{fmt}` and want to change it so
execution reaches the target branch. You cannot see raw bytes usefully, so use
the structural view and hexdump below. Express your answer as byte EDITS on the
seed; checksums/lengths are repaired for you afterward.

## Target branch
File: {branch_file}
Line: {branch_line}   (unexplored direction: {missing_arm})

Surrounding code:
```c
{branch_context}
```

## Seed structure  (parse)
```
{seed_parse}
```

## Seed hexdump (head)
```
{seed_hex}
```

## Source files
{sources}

Reason about which field(s) the branch inspects and which seed offsets hold
them. Then respond with exactly one fenced JSON block. Offsets are decimal byte
offsets into the seed; hex is the replacement bytes (same length as what they
overwrite):

```patch
{{"edits": [{{"offset": 16, "hex": "0000ffff"}}], "fix_checksums": true}}
```
"""


# ----------------------------------------------------------------- backend
class ClaudeCLIBackend:
    """Shells out to `claude --print --output-format json`.

    No API key: authenticates via whatever `claude` is already logged into
    on this machine (Pro/Max subscription). `model` is passed through as
    `--model <name>` if given; omitted, the CLI uses its own default.
    """
    def __init__(self, model: str | None = None):
        self.model = model

    def generate(self, prompt: str) -> tuple[str, str]:
        cmd = ["claude", "--print", "--output-format", "stream-json", "--verbose"]
        if self.model:
            cmd += ["--model", self.model]

        result = subprocess.run(cmd, input=prompt.encode(), capture_output=True)
        if result.returncode != 0:
            stderr = result.stderr.decode("utf-8", errors="replace")
            raise RuntimeError(f"Claude CLI failed (rc={result.returncode}): {stderr[:200]}")

        stdout = result.stdout.decode("utf-8", errors="replace")
        thoughts, final = [], []
        for line in stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if obj.get("type") == "assistant":
                for block in obj.get("message", {}).get("content", []):
                    if block.get("type") == "thinking":
                        thoughts.append(block.get("thinking", ""))
                    elif block.get("type") == "text":
                        final.append(block["text"])
        return ("\n\n".join(thoughts), "\n\n".join(final))


# ----------------------------------------------------------------- helpers
def branch_context(src: pl.Path, line: int, before=10, after=10) -> str:
    lines = src.read_text(errors="replace").splitlines()
    lo, hi = max(0, line - 1 - before), min(len(lines), line + after)
    return "\n".join(
        f"{i+1:4d}: {lines[i]}" + ("  // <- TARGET" if i == line - 1 else "")
        for i in range(lo, hi))


def bundle_sources(files: list[pl.Path]) -> str:
    return "\n\n".join(f"### {f}\n```c\n{f.read_text(errors='replace')}\n```"
                       for f in files)


def resolve_branch_file(spec: str, srcs: list[pl.Path]):
    """Best-effort locate the branch's source file; None if unavailable."""
    p = pl.Path(spec)
    if p.exists():
        return p
    for s in srcs:
        if str(s).endswith(spec) or s.name == spec:
            return s
    return None


def extract_input(text: str) -> bytes:
    m = re.search(r"```input\s*\n(.*?)```", text, re.DOTALL)
    body = m.group(1) if m else text
    return body.rstrip("\n").encode("utf-8")


def extract_patch(text: str):
    m = re.search(r"```patch\s*\n(.*?)```", text, re.DOTALL)
    if m:
        return json.loads(m.group(1))
    m = re.search(r"```(?:json)?\s*\n(\{.*?\})\s*```", text, re.DOTALL)
    if m:
        return json.loads(m.group(1))
    m = re.search(r"```hex\s*\n(.*?)```", text, re.DOTALL)
    if m:
        return {"whole_hex": m.group(1).strip()}
    raise ValueError("no ```patch``` / ```hex``` block found")


def materialize(seed: bytes, patch: dict) -> bytes:
    if "whole_hex" in patch:
        return bytes.fromhex(re.sub(r"\s", "", patch["whole_hex"]))
    out = F.apply_patch(seed, patch.get("edits", []))
    if patch.get("fix_checksums", True):
        out = F.fix(out)
    return out


def build_prompt(branch, srcs, seed: bytes | None):
    bf = resolve_branch_file(branch["file"], srcs)
    ctx = branch_context(bf, branch["line"]) if bf else "(source not provided)"
    common = dict(branch_file=(bf or branch["file"]), branch_line=branch["line"],
                  missing_arm=branch.get("missing_arm", "?"),
                  branch_context=ctx, sources=bundle_sources(srcs))
    if seed is None:
        return PROMPT_TEXT.format(**common)
    return PROMPT_BINARY.format(
        fmt=F.detect_format(seed), seed_parse=F.parse(seed),
        seed_hex=F.hexdump(seed, 0, 256), **common)


def generate(backend, branch: dict, srcs: list[pl.Path],
             seed: bytes | None = None):
    """Return (payload_bytes, thoughts, final_text)."""
    prompt = build_prompt(branch, srcs, seed)
    thoughts, final = backend.generate(prompt)
    if seed is None:
        return extract_input(final), thoughts, final
    return materialize(seed, extract_patch(final)), thoughts, final


# ----------------------------------------------------------------- cli
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--branch", required=True, help="FILE:LINE")
    ap.add_argument("--missing-arm", default="?", help="T or F (from frontier.py)")
    ap.add_argument("--src", nargs="+", type=pl.Path, required=True)
    ap.add_argument("--seed", type=pl.Path, help="valid seed => binary mode")
    ap.add_argument("--out", type=pl.Path, required=True)
    ap.add_argument("--model", default=None, help="passed to `claude --model`; omit for CLI default")
    ap.add_argument("--cot", type=pl.Path, default=None, help="write CoT here")
    args = ap.parse_args()

    fpart, _, lpart = args.branch.rpartition(":")
    branch = {"file": fpart, "line": int(lpart), "missing_arm": args.missing_arm}
    seed = args.seed.read_bytes() if args.seed else None
    backend = ClaudeCLIBackend(model=args.model)

    payload, thoughts, final = generate(backend, branch, args.src, seed)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(payload)
    if args.cot:
        args.cot.write_text(f"## thoughts\n{thoughts}\n\n## final\n{final}\n")
    print(f"wrote {len(payload)} bytes to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
