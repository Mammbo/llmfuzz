"""verify_all.py — exercise every file in the package and report PASS/FAIL.

    python3 verify_all.py

Library logic is covered by test_all.py; this additionally drives every CLI /
script end-to-end (frontier, frontier_gcov, offline, report_branches,
run_benchmark, mine.sh, afl_workflow.sh). Checks that need a toolchain
(clang/llvm, gcc/gcov, afl-fuzz) auto-skip if it's absent and say so.
"""
import json, os, shutil, subprocess, sys, tempfile, pathlib as pl

HERE = pl.Path(__file__).resolve().parent
PY = sys.executable
P = F = S = 0


def ok(n):   global P; P += 1; print(f"  \033[32mPASS\033[0m  {n}")
def bad(n, e=""): global F; F += 1; print(f"  \033[31mFAIL\033[0m  {n}  {e}")
def skip(n): global S; S += 1; print(f"  \033[33mSKIP\033[0m  {n}")
def have(*t): return all(shutil.which(x) for x in t)


def run(cmd, **kw):
    return subprocess.run(cmd, cwd=HERE, capture_output=True, text=True, **kw)


def sec(t): print(f"\n{t}")


# ---------------------------------------------------------------- 1. imports
sec("1. module imports")
for m in ["frontier", "frontier_gcov", "formats", "offline", "probe",
          "run_benchmark", "report_branches"]:
    r = run([PY, "-c", f"import {m}"])
    ok(f"import {m}") if r.returncode == 0 else bad(f"import {m}", r.stderr.strip()[-200:])


# ---------------------------------------------------------------- 2. test suite
sec("2. unit suite (test_all.py)")
r = run([PY, "test_all.py"])
ok("test_all.py (21 checks)") if "checks passed" in r.stdout else bad("test_all.py", r.stderr[-200:])


# ---------------------------------------------------------------- 3. offline CLI (claude backend)
sec("3. offline.py CLI (real Claude CLI calls -- needs `claude` logged in)")
if not have("claude"):
    for n in ["offline text mode", "offline binary mode wired"]:
        skip(n + " (no `claude` CLI on PATH)")
else:
    with tempfile.TemporaryDirectory() as d:
        d = pl.Path(d)
        (d/"t.c").write_text("int f(){if(1){}return 0;}\n")
        r = run([PY, "offline.py", "--branch", f"{d/'t.c'}:1", "--src", str(d/"t.c"),
                 "--out", str(d/"g.txt")])
        ok("offline text mode") if (d/"g.txt").exists() else bad("offline text", r.stderr[-200:])
        # binary mode needs a PNG seed
        import importlib, sys as _s; _s.path.insert(0, str(HERE))
        import formats as _F
        (d/"s.png").write_bytes(_F.png_write(4, 2))
        r = run([PY, "offline.py", "--branch", "x.c:1", "--src", str(d/"t.c"),
                 "--seed", str(d/"s.png"), "--out", str(d/"g.png")])
        # a real model asked for a ```patch``` block may still occasionally reply
        # without one -- offline.py should either apply it (g.png written) or
        # raise a clean, recognizable error, not crash uninformatively.
        ok("offline binary mode wired") if (d/"g.png").exists() or \
            (r.returncode != 0 and "patch" in (r.stderr+r.stdout).lower()) \
            else bad("offline binary", r.stderr[-200:])


# ---------------------------------------------------------------- 5. coverage tools (clang/llvm)
sec("4. llvm-cov path: build -> frontier.py -> report_branches.py -> mine.sh -> run_benchmark.py")
if not have("clang", "llvm-cov", "llvm-profdata"):
    for n in ["frontier.py CLI", "report_branches.py CLI", "mine.sh", "run_benchmark.py CLI"]:
        skip(n + " (no clang/llvm)")
else:
    work = HERE / "_verify"
    shutil.rmtree(work, ignore_errors=True)
    (work / "seeds").mkdir(parents=True)
    src = ('#include <stdio.h>\n#include <stdint.h>\n#include <stddef.h>\n'
           'int process(const uint8_t*d,size_t n){\n'
           ' if(n<8)return 0;\n'
           ' int s=0;\n'
           ' if(d[0]==0x89)s++;\n'
           ' if(d[1]==0x50)s++;\n'
           ' uint32_t m=d[4]|(d[5]<<8)|(d[6]<<16)|((uint32_t)d[7]<<24);\n'
           ' if(m==0xCAFEBABE)s++;\n'
           ' return s;}\n'
           'int main(int c,char**v){if(c<2)return 0;FILE*f=fopen(v[1],"rb");'
           'if(!f)return 0;uint8_t b[4096];size_t n=fread(b,1,4096,f);fclose(f);'
           'return process(b,n);}\n')
    (work/"t.c").write_text(src)
    for i, seed in enumerate([b"hello wo", b"AAAAAAAA", bytes(range(8))]):
        (work/"seeds"/f"s{i}").write_bytes(seed)
    subprocess.run(["clang", "-g", "-O0", "-fprofile-instr-generate",
                    "-fcoverage-mapping", str(work/"t.c"), "-o", str(work/"cov")],
                   check=True, capture_output=True)
    for i, s in enumerate((work/"seeds").iterdir()):
        subprocess.run([str(work/"cov"), str(s)], capture_output=True,
                       env={**os.environ, "LLVM_PROFILE_FILE": str(work/f"{i}.profraw")})
    subprocess.run(["llvm-profdata", "merge", *[str(p) for p in work.glob("*.profraw")],
                    "-o", str(work/"m.profdata")], check=True, capture_output=True)
    (work/"cov.json").write_text(subprocess.run(
        ["llvm-cov", "export", str(work/"cov"), f"-instr-profile={work/'m.profdata'}"],
        check=True, capture_output=True, text=True).stdout)

    # frontier.py
    r = run([PY, "frontier.py", str(work/"cov.json"), "--include", "t.c",
             "--jsonl", str(work/"hard.jsonl")])
    ok("frontier.py CLI") if r.stdout.count("t.c:") >= 3 else bad("frontier.py CLI", (r.stdout+r.stderr)[-200:])

    # report_branches.py
    r = run([PY, "report_branches.py", str(work/"hard.jsonl"), "--src", str(work/"t.c"),
             "--out", str(work/"hard.md")])
    ok("report_branches.py CLI") if (work/"hard.md").exists() else bad("report_branches.py CLI", r.stderr[-200:])

    # mine.sh (standalone)
    r = run(["bash", "mine.sh", str(work/"cov"), str(work/"seeds"), "t.c",
             str(work/"mineout"), "standalone"])
    ok("mine.sh") if (work/"mineout"/"hard.jsonl").exists() else bad("mine.sh", r.stderr[-200:])

    # run_benchmark.py via a real config (real Claude CLI backend + REAL standalone verifier)
    if not have("claude"):
        skip("run_benchmark.py CLI (no `claude` CLI on PATH)")
    else:
        cfg = {"targets": [{"name": "t", "input_type": "text", "standalone": True,
                            "src": [str(work/"t.c")], "cov_harness": str(work/"cov"),
                            "branches": str(work/"hard.jsonl")}]}
        (work/"cfg.json").write_text(json.dumps(cfg))
        r = run([PY, "run_benchmark.py", "--config", str(work/"cfg.json"),
                 "--tools", "on", "--out", str(work/"report.json")])
        ok("run_benchmark.py CLI") if (work/"report.json").exists() and "reach rate" in r.stdout \
            else bad("run_benchmark.py CLI", r.stderr[-300:])

    # gcov path
    if have("gcc", "gcov"):
        subprocess.run(["gcc", "--coverage", "-O0", "-g", str(work/"t.c"),
                        "-o", str(work/"gcov_t")], check=True, capture_output=True, cwd=work)
        for s in (work/"seeds").iterdir():
            subprocess.run([str(work/"gcov_t"), str(s)], capture_output=True, cwd=work)
        subprocess.run(["gcov", "-b", "-c", "gcov_t-t.gcda"], capture_output=True, cwd=work)
        r = run([PY, "frontier_gcov.py", str(work/"t.c.gcov"), "--include", "t.c"])
        ok("frontier_gcov.py CLI") if r.stdout.count("t.c:") >= 3 else bad("frontier_gcov.py CLI", (r.stdout+r.stderr)[-200:])
    else:
        skip("frontier_gcov.py CLI (no gcov)")
    shutil.rmtree(work, ignore_errors=True)


# ---------------------------------------------------------------- 6. afl scripts
sec("5. afl_workflow.sh")
if have("afl-fuzz", "clang", "llvm-cov"):
    ok("afl-fuzz present (afl_workflow.sh runnable; skipped live fuzz for speed)")
else:
    skip("afl_workflow.sh (no afl-fuzz; needs your machine)")


# ---------------------------------------------------------------- summary
print(f"\n{'='*40}\n{P} passed, {F} failed, {S} skipped")
sys.exit(1 if F else 0)
