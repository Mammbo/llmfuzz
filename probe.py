"""Verify whether a candidate input flips a target branch, and drive an
agentic generate->probe->refine loop.

A verifier is any callable: bytes -> (reached: bool, feedback: str).

`replay_verifier` builds the real one for your environment: it runs the
candidate through an llvm-cov coverage build, re-exports coverage, and checks
whether the previously-zero arm of the target branch now has a nonzero count.
It shells out to llvm-profdata / llvm-cov, so it needs your target machine.

For unit tests, pass a pure-python verifier (see tests/).
"""
from __future__ import annotations
import json, os, subprocess, tempfile, pathlib as pl
import offline


def replay_verifier(cov_harness: str, branch: dict, llvm_cov="llvm-cov",
                    llvm_profdata="llvm-profdata", runner=None, export_bin=None):
    """Return verifier(candidate_bytes) -> (reached, feedback) for a real build.

    cov_harness: binary built with -fprofile-instr-generate -fcoverage-mapping.
    branch:      {"file","line","missing_arm"} from frontier.py.
    runner:      argv builder (harness, input_path) -> list[str]. Default is the
                 libFuzzer convention used by Magma/OSS-Fuzz. For a standalone
                 target that reads argv[1], pass runner=lambda h,i: [h, i].
    export_bin:  the real coverage-instrumented ELF llvm-cov reads the mapping
                 from. Defaults to cov_harness; set this separately when
                 cov_harness is a one-arg wrapper script for a multi-arg CLI
                 tool (e.g. tiffcp), mirroring mine.sh's [export_bin] arg.
    """
    want_arm = branch.get("missing_arm")
    if runner is None:
        runner = lambda h, i: [h, "-runs=0", i]
    export_bin = export_bin or cov_harness

    def verify(candidate: bytes):
        with tempfile.TemporaryDirectory() as d:
            inp = pl.Path(d) / "cand"
            inp.write_bytes(candidate)
            profraw = pl.Path(d) / "c.profraw"
            profdata = pl.Path(d) / "c.profdata"
            env = {**os.environ, "LLVM_PROFILE_FILE": str(profraw)}
            subprocess.run(runner(cov_harness, str(inp)),
                           env=env, capture_output=True)
            subprocess.run([llvm_profdata, "merge", str(profraw),
                            "-o", str(profdata)], capture_output=True, check=True)
            out = subprocess.run(
                [llvm_cov, "export", export_bin,
                 f"-instr-profile={profdata}"],
                capture_output=True, check=True).stdout
            cov = json.loads(out)
        reached, near = _branch_reached(cov, branch, want_arm)
        return reached, near

    return verify


def _branch_reached(cov: dict, branch: dict, want_arm):
    """Did the target line's missing arm get a nonzero count? Plus feedback."""
    tgt_line = branch["line"]
    for export in cov.get("data", []):
        for f in export.get("files", []):
            if not str(f.get("filename", "")).endswith(pl.Path(branch["file"]).name):
                continue
            for br in f.get("branches", []):
                if br[0] != tgt_line:
                    continue
                t, fl = br[4], br[5]
                got = (fl > 0) if want_arm == "F" else (t > 0)
                return got, (f"branch@{tgt_line} true={t} false={fl} "
                             f"needed_arm={want_arm} -> {'FLIPPED' if got else 'still one-sided'}")
    return False, f"branch@{tgt_line} not present in coverage (line never reached)"


def agentic_generate(backend, branch: dict, srcs, seed: bytes | None,
                     verifier, max_iters: int = 4):
    """generate -> materialize -> verify -> (on miss) feed probe back and retry.

    Returns (payload, reached, transcript). transcript is a list of per-iter
    dicts for logging / the CoT index.
    """
    base_prompt = offline.build_prompt(branch, srcs, seed)
    prompt = base_prompt
    transcript, best = [], None
    for it in range(max_iters):
        thoughts, final = backend.generate(prompt)
        if seed is None:
            payload = offline.extract_input(final)
        else:
            payload = offline.materialize(seed, offline.extract_patch(final))
        reached, feedback = verifier(payload)
        transcript.append({"iter": it, "reached": reached,
                            "feedback": feedback, "bytes": len(payload)})
        best = payload
        if reached:
            return payload, True, transcript
        prompt = (base_prompt +
                  f"\n\n## Previous attempt #{it} did NOT reach the branch\n"
                  f"Probe result: {feedback}\n"
                  f"Revise your edits to satisfy the branch condition.\n")
    return best, False, transcript
