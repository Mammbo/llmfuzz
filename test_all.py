"""Runnable test suite: python test_all.py

Covers everything that can be validated without a real target build:
  - frontier: one-sided branch detection + ranking + filtering
  - formats:  PNG synth -> patch -> broken CRC -> fix -> valid round trip
  - probe:    agentic generate->probe->refine converges, file stays valid
  - report:   ablation table renders, tools-on beats tools-off
The real target replay/verify path (probe.replay_verifier, run_benchmark with
the real Claude CLI backend) needs a coverage build and is exercised on the
lab machine.
"""
import json, struct, binascii, subprocess, sys, pathlib as pl
import formats as F, offline, probe, run_benchmark as B

HERE = pl.Path(__file__).resolve().parent
OK = []


def check(name, cond):
    assert cond, f"FAIL: {name}"
    OK.append(name)


def test_frontier():
    synth = {
        "data": [{"functions": [{
            "name": "f", "filenames": ["/src/target.c"],
            "branches": [
                [42, 9, 42, 20, 1500, 900, 0, 0],   # both covered -> skip
                [88, 5, 88, 30, 3200, 0,   0, 0],   # one-sided (F) reached=3200
                [131,7, 131,40, 0,    45,  0, 0],   # one-sided (T) reached=45
                [200,3, 200,12, 0,    0,   0, 0],   # never reached -> skip
            ]}], "files": []}]}
    p = HERE / "_t_cov.json"; p.write_text(json.dumps(synth))
    out = subprocess.run([sys.executable, str(HERE/"frontier.py"), str(p),
                          "--top", "20", "--jsonl", str(HERE/"_t.jsonl")],
                         capture_output=True, text=True).stdout.strip().splitlines()
    check("frontier finds exactly the 2 one-sided branches", len(out) == 2)
    check("frontier ranks by reached count", out[0].endswith(":88"))
    rows = [json.loads(l) for l in (HERE/"_t.jsonl").read_text().splitlines()]
    check("frontier records missing arm", rows[0]["missing_arm"] == "F"
          and rows[1]["missing_arm"] == "T")
    (HERE/"_t_cov.json").unlink(); (HERE/"_t.jsonl").unlink()


def test_formats_png_roundtrip():
    png = F.png_write(width=4, height=2)
    check("detect png", F.detect_format(png) == "png")
    patched = F.apply_patch(png, [{"offset": 16, "hex": "0000ffff"}])
    check("edit breaks CRC", "crc=BAD" in F.png_parse(patched))
    fixed = F.fix(patched)
    check("fix repairs CRC", "crc=BAD" not in F.png_parse(fixed))
    for _o, _l, ct, cd, crc in F._png_chunks(fixed):
        want = struct.pack(">I", binascii.crc32(ct + cd) & 0xFFFFFFFF)
        check(f"{ct} crc valid", want == crc)
    check("target field set", struct.unpack(">I", fixed[16:20])[0] == 0xFFFF)


def test_agentic_loop():
    seed = F.png_write(width=4, height=2)
    branch = {"file": "libpng.c", "line": 1234, "missing_arm": "T"}

    def verifier(cand):
        if F.detect_format(cand) != "png":
            return False, "structure broken"
        for _o, _l, ct, cd, crc in F._png_chunks(cand):
            if struct.pack(">I", binascii.crc32(ct + cd) & 0xFFFFFFFF) != crc:
                return False, "CRC rejected"
        w = struct.unpack(">I", cand[16:20])[0]
        return w > 0x7FFF, f"width={w}"

    class Scripted:
        def __init__(s, r): s.r, s.i = r, 0
        def generate(s, p):
            x = s.r[min(s.i, len(s.r) - 1)]; s.i += 1; return ("", x)

    backend = Scripted([
        '```patch\n{"edits":[{"offset":16,"hex":"00000010"}]}\n```',
        '```patch\n{"edits":[{"offset":16,"hex":"0000ffff"}]}\n```',
    ])
    payload, reached, tr = probe.agentic_generate(
        backend, branch, [], seed, verifier, max_iters=4)
    check("loop misses then hits", tr[0]["reached"] is False and tr[1]["reached"] is True)
    check("loop reaches branch", reached is True)
    check("output still valid png", F.detect_format(payload) == "png")


def test_report():
    recs = [{"target": "libpng", "branch": f"p:{i}", "input_type": "binary",
             "tools": True, "reached": i < 9, "iters": 2} for i in range(10)]
    recs += [{"target": "libpng", "branch": f"p:{i}", "input_type": "binary",
              "tools": False, "reached": i < 1, "iters": 1} for i in range(10)]
    s = B.report(recs)
    check("tools-on beats tools-off", s["binary_tools_on"] > s["binary_tools_off"])


def test_real_build_and_verify():
    """End-to-end on a REAL llvm-cov build: compile -> replay -> mine -> verify.
    Auto-skips if the LLVM toolchain isn't installed."""
    import shutil, tempfile, os
    if not all(shutil.which(t) for t in ("clang", "llvm-cov", "llvm-profdata")):
        print("  skip real-build test (clang/llvm not installed)")
        return
    src = ('#include <stdio.h>\n#include <stdint.h>\n#include <stddef.h>\n'
           'int process(const uint8_t*d,size_t n){\n'
           ' if(n<16)return 0;\n int s=0;\n'
           ' if(d[0]==0x89)s++;\n'                       # line 7
           ' uint32_t m=d[4]|(d[5]<<8)|(d[6]<<16)|((uint32_t)d[7]<<24);\n'
           ' if(m==0xCAFEBABE)s++;\n return s;}\n'        # line 9
           'int main(int c,char**v){if(c<2)return 0;FILE*f=fopen(v[1],"rb");'
           'if(!f)return 0;uint8_t b[4096];size_t n=fread(b,1,4096,f);'
           'fclose(f);return process(b,n);}\n')
    with tempfile.TemporaryDirectory() as d:
        dp = pl.Path(d)
        (dp/"t.c").write_text(src)
        (dp/"seeds").mkdir()
        for i, seed in enumerate([b"A"*16, b"hello world 1234", bytes(range(16))]):
            (dp/"seeds"/f"s{i}").write_bytes(seed)
        subprocess.run(["clang", "-g", "-O0", "-fprofile-instr-generate",
                        "-fcoverage-mapping", str(dp/"t.c"), "-o", str(dp/"tc")],
                       check=True, capture_output=True)
        for i, s in enumerate((dp/"seeds").iterdir()):
            subprocess.run([str(dp/"tc"), str(s)],
                           env={**os.environ, "LLVM_PROFILE_FILE": str(dp/f"{i}.profraw")},
                           capture_output=True)
        subprocess.run(["llvm-profdata", "merge", *[str(p) for p in dp.glob("*.profraw")],
                        "-o", str(dp/"m.profdata")], check=True, capture_output=True)
        cov = subprocess.run(["llvm-cov", "export", str(dp/"tc"),
                              f"-instr-profile={dp/'m.profdata'}"],
                             check=True, capture_output=True, text=True).stdout
        (dp/"cov.json").write_text(cov)
        mined = subprocess.run([sys.executable, str(HERE/"frontier.py"),
                                str(dp/"cov.json"), "--include", "t.c"],
                               capture_output=True, text=True).stdout
        check("real: mines the magic-check branches", ":9" in mined and ":7" in mined)

        branch = {"file": "t.c", "line": 9, "missing_arm": "T"}  # m==0xCAFEBABE
        verify = probe.replay_verifier(str(dp/"tc"), branch,
                                       runner=lambda h, i: [h, i])
        miss, _ = verify(b"A"*16)
        hit, _ = verify(b"\x00"*4 + bytes([0xBE,0xBA,0xFE,0xCA]) + b"\x00"*8)
        check("real: verifier miss on benign", miss is False)
        check("real: verifier flip on crafted magic", hit is True)


if __name__ == "__main__":
    for fn in [test_frontier, test_formats_png_roundtrip, test_agentic_loop,
               test_report, test_real_build_and_verify]:
        fn()
    print(f"\n{len(OK)} checks passed:")
    for name in OK:
        print(f"  ok  {name}")
