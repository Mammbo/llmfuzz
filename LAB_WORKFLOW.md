# llmFuzz — Front-to-Back Lab Workflow

Produce **hard branches** (conditionals the fuzzer reaches but never flips) from
10 real open-source libraries, then test whether an LLM can flip them. This
guide takes a lab mate from a clean machine to shareable hard-branch benchmarks
and offline LLM reach-rate numbers.

**Mental model — two jobs, don't conflate them:**
- **AFL++ *produces* the hard branches.** You fuzz until stuck; the branches it
  never flipped are the benchmark. (Parts A–C.)
- **The LLM *is tested against* the hard branches — no AFL in that loop.** The
  LLM generates an input, and a coverage build checks whether the branch
  flipped. (Part E.) AFL only returns much later for the online A/B.

Pipeline: `AFL++ (10 targets) → queues → mine hard branches → package → offline LLM test`.

> **2026-07-08 update:** Parts A-C below (Magma/Docker) are what actually
> produced the 7-target results checked into `result/` — they work, and are
> left intact as the historical/validated record. But we hit a real toolchain
> version-mismatch wall doing it (see the callout in Part C), and going
> forward **new coverage builds should use OSS-Fuzz instead of Magma's
> `llvm_cov` fuzzer** — see **§3b** for why and the concrete commands. Magma's
> AFL queues already on disk don't need to be re-fuzzed; only the *coverage
> build* step is being replaced.

---

## 0. Quick start (copy-paste to begin)

You install **nothing AFL- or clang-related on the host** — Magma builds AFL++
and all 10 targets inside Docker. The only host requirement is Docker + git.

```bash
# --- one-time host setup ---
# install docker + git for your distro:
#   Arch:  sudo pacman -S --needed docker git
#   Deb/Ubuntu: sudo apt-get install -y docker.io git
sudo systemctl enable --now docker
sudo usermod -aG docker "$USER" && newgrp docker   # or log out/in
docker run --rm hello-world                        # MUST print "Hello from Docker!"

# --- build + run the fuzzers (all inside Docker) ---
git clone https://github.com/HexHive/magma && cd magma
$EDITOR tools/captain/captainrc      # set the 10 targets, FUZZERS=(aflplusplus), TIMEOUT=14h  (see Part A)
cd tools/captain
./build.sh                           # Docker builds AFL++ + 10 targets (~1-3h, one time)
./run.sh                             # starts all 10 campaigns; ~14h overnight
```

If `hello-world` prints, your setup is done and your host toolchain no longer
matters. Everything below expands these steps and adds mining + the LLM test.

---

## 1. What each file does

| file | role |
|------|------|
| `frontier.py` | **PRIMARY miner.** Reads an `llvm-cov export` JSON, emits one-sided (reached-but-never-flipped) branches as `FILE:LINE` + `hard.jsonl`. |
| `frontier_gcov.py` | Same, but parses `gcov` output (afl-cov / gcov path). Fallback if not using llvm-cov. |
| `formats.py` | Binary tooling for the LLM: detect / parse / hexdump / patch / **checksum-fix** for PNG, PDF, MP4, ELF, gzip. The checksum-fix is what makes LLM binary edits survive format validation. |
| `offline.py` | The generator. Given a hard branch (+ a valid seed for binary targets), asks the LLM for an input/patch that reaches it. Backend: `ClaudeCLIBackend`, shells out to `claude --print` — no API key, rides your Claude Pro/Max subscription. |
| `probe.py` | Coverage **verifier** (did the branch flip?) + the agentic `generate→probe→refine` loop. |
| `run_benchmark.py` | Driver: runs the generator over every branch, verifies, reports reach-rate with the **tools-on/off ablation**. |
| `report_branches.py` | Turns `hard.jsonl` + source into a readable markdown report. |
| `mine.sh` | One command: replay a corpus through a coverage build → `hard.jsonl`. Takes an optional cap (`[cap]`, default 100000 — effectively uncapped, since the goal is finding ALL hard branches) and, in standalone mode, applies a 15s per-input timeout (`TIMEOUT_S` env var) so one pathological input can't hang the whole replay loop. An optional 7th arg (`[export_bin]`) lets `HARNESS` be a one-arg wrapper script for multi-arg CLI tools (e.g. `tiffcp in out`) while `llvm-cov export` still reads the real instrumented binary. |
| `afl_workflow.sh` | `afl-cmin` a queue then `mine.sh` it — the AFL-queue → hard-branches path. |
| `package_benchmark.sh` | Bundle `hard.jsonl` + report + corpus + provenance manifest to send to lab mates. |
| `test_all.py` | Unit suite — library logic (17 checks). |
| `verify_all.py` | Integration suite — drives every CLI end-to-end and reports PASS/FAIL. |
| `benchmark.example.json` | Config template for `run_benchmark.py`. |

---

## 2. Machine + prerequisites

Reference machine: **i5-13400F (6 P-cores + 4 E-cores = 10 physical cores, 16
threads), 31 GB RAM, ~1.8 TB free.** The GPU is irrelevant — AFL is CPU-bound
and the LLM runs via the cloud API.

**The only host requirement to start is Docker + git.** AFL++ and all 10 targets
are built and run *inside Docker containers* by Magma with their own pinned
toolchain — so you do NOT install AFL++, clang, or a specific gcc on the host,
and host-toolchain issues (e.g. a too-new gcc, an Arch partial-upgrade) cannot
break the fuzzing run. The host tools for the *mining* and *LLM* stages come
later, in Parts C and E, and can even be run inside the container if your host
versions don't cooperate.

```bash
# 1) Docker + git — the only thing needed for Parts A-B
#    Debian/Ubuntu: sudo apt-get install -y docker.io git
#    Arch:          sudo pacman -S --needed docker git
#    Fedora:        sudo dnf install -y docker git

# 2) start Docker and run it rootless (Magma requires docker without sudo)
sudo systemctl enable --now docker
sudo usermod -aG docker "$USER"       # then log out/in, or: newgrp docker

# 3) AFL system tuning on the HOST (containers share the host kernel).
#    Do this each boot, or persist it.
echo core | sudo tee /proc/sys/kernel/core_pattern
echo performance | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor
#    If the governor write says "No such file" (intel_pstate, common on the
#    13400F): sudo pacman -S cpupower && sudo cpupower frequency-set -g performance
```

**Validate before touching targets:**
```bash
docker run --rm hello-world           # must succeed rootless before Part A
```

Host tools for later (Parts C/E only — install when you get there, or use the
container): `clang`/`llvm` (llvm-cov, llvm-profdata) for mining, and the
`claude` CLI logged into a Pro/Max subscription for the real LLM backend (no
API key/creds file needed). The llmfuzz scripts themselves are pure stdlib.
To sanity-check them any time (no toolchain needed):
```bash
cd llmfuzz && python3 verify_all.py   # 18 passed (afl step auto-skips if absent)
python3 test_all.py                   # 21 checks passed
```

> **No Python package needed for the LLM backend** — `offline.py` shells out
> to the `claude` CLI directly (stdlib `subprocess`), so there's no
> `pip install` / venv step for Part E. Just make sure `claude` is on `PATH`
> and logged into a Pro/Max subscription (`claude --print "hi"` should work).

---

## 3. Part A — Build & run the 10 fuzzers (Magma, Docker)

Magma builds and runs all 10 heterogeneous targets for you, with AFL++ +
CmpLog + seed corpora included. *(Magma commands below are per Magma's docs —
confirm against your checked-out version, since captainrc keys move between
releases.)*

```bash
git clone https://github.com/HexHive/magma && cd magma
```

**The 10 targets (5 binary / 5 text).** Each is a `(target, program)` pair;
valid program names live in `magma/targets/<target>/configrc`.

| # | target | program | type |
|---|--------|---------|------|
| 1 | libpng | libpng_read_fuzzer | binary (PNG) |
| 2 | libtiff | tiff_read_rgba_fuzzer | binary (TIFF) |
| 3 | libsndfile | sndfile_fuzzer | binary (audio) |
| 4 | poppler | pdf_fuzzer | binary (PDF) |
| 5 | openssl | asn1 | binary (DER) |
| 6 | libxml2 | libxml2_xml_read_memory_fuzzer | text (XML) |
| 7 | sqlite3 | sqlite3_fuzz | text (SQL) |
| 8 | lua | lua | text (Lua) |
| 9 | php | php_fuzz_parser | text (PHP) |
| 10 | libtiff | tiffcp | binary (2nd TIFF program) |

Edit `tools/captain/captainrc`:

```bash
WORKDIR=./workdir
REPEAT=1                # one campaign per program (enough to mine branches)
TIMEOUT=14h             # overnight run; use 10m first to smoke-test. 24h is only
                        # needed for the rigorous online A/B later, not for mining.
POLL=5

FUZZERS=(aflplusplus)   # AFL++ with CmpLog (verify magma/fuzzers/aflplusplus)

aflplusplus_TARGETS=(libpng libtiff libsndfile poppler openssl libxml2 sqlite3 lua php)
# pick programs per target:
libpng_PROGRAMS=(libpng_read_fuzzer)
libtiff_PROGRAMS=(tiff_read_rgba_fuzzer tiffcp)
libsndfile_PROGRAMS=(sndfile_fuzzer)
poppler_PROGRAMS=(pdf_fuzzer)
openssl_PROGRAMS=(asn1)
libxml2_PROGRAMS=(libxml2_xml_read_memory_fuzzer)
sqlite3_PROGRAMS=(sqlite3_fuzz)
lua_PROGRAMS=(lua)
php_PROGRAMS=(php_fuzz_parser)

# Parallelism: Magma runs one campaign per core. You have 10 physical cores,
# so all 10 programs run at once. Leave 1-2 cores for the OS if the box is
# also your daily driver by restricting the core list (see captainrc docs).
WORKERS=1               # workers PER campaign (AFL = 1); concurrency comes from cores
```

**Why CmpLog matters here:** it cracks magic-byte comparisons for free. If you
mine hard branches from *plain* AFL, half your list is trivial magic bytes a
reviewer will say CmpLog would've solved. Mining from AFL++ **with** CmpLog
leaves the branches that defeat a *strong* baseline — the ones worth showing the
LLM can flip. Confirm CmpLog is on in `magma/fuzzers/aflplusplus/`.

Build the images, then run all campaigns in parallel:

```bash
cd tools/captain
./build.sh              # builds the Docker images (first run: ~1-3h)
./run.sh                # launches all 10 campaigns; ~14h wall-clock (overnight)
```

**Also build the coverage variant** (needed to mine + verify). Magma ships an
`llvm_cov` fuzzer that compiles with `-fprofile-instr-generate -fcoverage-mapping`:

```bash
# in captainrc, add a coverage build pass:  FUZZERS=(aflplusplus llvm_cov)
# (llvm_cov just builds/instruments; it doesn't need the full 24h run)
```

**Validate Part A:**
```bash
docker ps                                   # 10 running containers (during run)
find workdir -path '*/queue' -type d -exec sh -c \
  'echo "$(ls "$1" | wc -l) files: $1"' _ {} \;   # queues should be growing
find workdir -name fuzzer_stats -exec grep -H execs_done {} \;  # execs climbing
```
Let it run until the queue count stops growing for several hours (plateau) — that
is when the uncovered branches are genuinely hard.

---

## 4. Part B — Locate the queues and coverage binaries

Magma stores results under `WORKDIR`. Find the AFL queue and the coverage binary
for each program:

```bash
# AFL queues (one per program)
find workdir -type d -name queue
# e.g. workdir/ar/aflplusplus/libpng/libpng_read_fuzzer/0/findings/queue

# extract a coverage binary from the llvm_cov image (per target)
docker create --name cov_libpng magma/llvm_cov/libpng
docker cp cov_libpng:/magma_out/libpng_read_fuzzer ./cov_libpng   # path per target
docker rm cov_libpng
```
*(Exact in-container paths vary by Magma version; `docker cp` the built harness
out, or run the coverage step inside the container.)*

---

## 4b. Recommended going forward: OSS-Fuzz instead of Magma for coverage builds

**Why.** Magma's Docker images pin `clang-9` from 2019, hardcoded via
`apt-get install clang-9` + `update-alternatives` in
`magma/fuzzers/aflplusplus/preinstall.sh` and
`magma/fuzzers/llvm_cov/preinstall.sh` — frozen since Magma's release and
never updated. A coverage binary built through Magma's own `llvm_cov` fuzzer
emits `.profraw` in that old runtime's format; a modern host `llvm-profdata`/
`llvm-cov` (LLVM 18+) rejects it outright:
```
warning: raw profile version mismatch: Profile uses raw profile format
version = 4; expected version = 10
error: no profile can be merged
```
This is exactly the error we hit mining `libtiff` and `openssl` on
2026-07-08 (leftover `cov_libtiff_out`/`cov_openssl_out` binaries from an
earlier Magma-docker attempt) — worked around that day by hand-rebuilding
both libraries on the host with the host's own clang, but that meant
re-solving each library's build system by hand (autoconf flags, missing
static libs, etc.) instead of just using the project's own build script.

**"Just run mine.sh inside the container" does not fix this — tested and
confirmed dead end.** The obvious alternative to a host rebuild is running
the whole mining step inside Magma's own `llvm_cov/<target>` container,
where the profiling tools are guaranteed to match the build. We tried this
for real on 2026-07-08: mounted this repo and the libpng queue into
`magma/llvm_cov/libpng`, and found `llvm-profdata-9` genuinely present in
the image at `/usr/bin/llvm-profdata-9` — Magma's own
`fuzzers/llvm_cov/preinstall.sh` registers `llvm-cov` via
`update-alternatives` but never registers `llvm-profdata`, so it's simply
missing from `PATH` (a real gap in Magma's own tooling, not a missing
package). Symlinking it and rerunning `mine.sh` fully in-container did fix
the raw-profile-version error — `llvm-profdata merge` and `llvm-cov export`
both ran clean. But the result was **0 hard branches**, not a fix. Cause:
this container's `llvm-cov` is version **9.0.0**, and at that version
`llvm-cov export` only emits `regions` in its JSON — the `branches` array
`frontier.py` reads doesn't exist as an export field yet (branch-level
export was added in a materially later LLVM release, roughly the 12–14
range). So the container doesn't just have a *profiling-tool-version*
problem, it has a *missing-feature* problem: Magma's frozen clang-9 predates
the coverage capability this whole pipeline is built on, and no amount of
matching profdata-to-cov versions *inside* that container fixes it, because
both versions are simply too old. This is silently worse than the host
version-mismatch error, since it produces a well-formed-looking `hard.jsonl`
that is empty instead of erroring loudly — if you try this, check
`cov.json`'s function objects for a `"branches"` key before trusting a `0
hard branches` result. This is why the host-rebuild-with-modern-clang we did
for libtiff/openssl wasn't a workaround for a formatting quirk — it was
required to get branch coverage at all, and it's also why §4b recommends
OSS-Fuzz (whose LLVM is periodically rebuilt near-trunk, not frozen at a
2019 release) over continuing to patch around Magma's container.

OSS-Fuzz (`github.com/google/oss-fuzz`) builds its own clang from a pinned
**near-trunk LLVM git revision** inside `infra/base-images/base-clang`
(`checkout_build_install_llvm.sh`), rebuilt periodically. It still drifts
from whatever the host has, but it stays far closer to current LLVM than
Magma's 2019 image, so the version-mismatch class of bug mostly goes away —
and more importantly, **build and profile happen in the same container
image**, so build-toolchain and profiling-toolchain versions can't
diverge in the first place, regardless of how modern either one is.

It also already has all 6 of our libraries as first-class projects, verified
2026-07-08 against `google/oss-fuzz`'s `projects/*/project.yaml`, with
`main_repo` matching what Magma's own `fetch.sh` pins to and `afl` listed
under `fuzzing_engines` for every one:

| target | oss-fuzz project | main_repo |
|---|---|---|
| libpng | `libpng` | `github.com/pnggroup/libpng.git` |
| libtiff | `libtiff` | `gitlab.com/libtiff/libtiff` |
| libsndfile | `libsndfile` | `github.com/libsndfile/libsndfile.git` |
| poppler | `poppler` | `anongit.freedesktop.org/git/poppler/poppler.git` |
| openssl | `openssl` | `github.com/openssl/openssl.git` |
| sqlite3 | `sqlite3` | `sqlite.org/src/dir` |

**Honest tradeoff.** OSS-Fuzz fuzzes each project's current/pinned upstream
as shipped — it does **not** carry Magma's injected historical-CVE canaries
(`-DMAGMA_ENABLE_CANARIES`, `magma/targets/<t>/patches/bugs/*.patch`). That
property is only load-bearing for Part E's *online* A/B ("bugs found"
metric); mining hard branches (Parts A-C) only ever needed a pinned commit +
a saturated corpus + a coverage build, so nothing here is lost for that half
of the project. If the online A/B later needs known-bug ground truth again,
either keep using a Magma-fuzzed queue for that stage specifically, or
hand-apply the same patches from `magma/targets/<t>/patches/bugs/` onto an
OSS-Fuzz checkout.

**Commands (per target):**
```bash
git clone https://github.com/google/oss-fuzz && cd oss-fuzz

# 1) AFL++ campaign build (replaces Magma's captain/build.sh for this target)
python infra/helper.py build_fuzzers --engine afl libpng
# -> build/out/libpng/libpng_read_fuzzer (AFL-instrumented)

# 2) fuzz — helper.py has no built-in "run afl-fuzz" driver; shell in and
#    drive afl-fuzz yourself, or grab OSS-Fuzz's own ClusterFuzz corpus
#    instead of fuzzing from scratch:
python infra/helper.py shell libpng
#   (inside) afl-fuzz -i seed_corpus -o /out/afl_findings -- \
#            build/out/libpng/libpng_read_fuzzer @@
# or, to skip fuzzing and mine against OSS-Fuzz's existing corpus:
python infra/helper.py download_corpora libpng

# 3) coverage build (replaces Magma's llvm_cov fuzzer / cov_*_out artifacts)
python infra/helper.py build_fuzzers --sanitizer coverage libpng
# -> build/out/libpng/libpng_read_fuzzer, now -fprofile-instr-generate

# 4) mine INSIDE the same container, so llvm-profdata/llvm-cov are
#    guaranteed to match the binary that built them:
python infra/helper.py shell libpng
#   (inside; mount this repo in first, e.g. -v $PWD/llmfuzz:/llmfuzz)
cd /llmfuzz
./mine.sh /out/libpng_read_fuzzer /out/afl_findings/queue \
    libpng /out/result/libpng standalone 100000
#   -> copy /out/result/libpng/hard.jsonl back to the host afterward
```

This section is a plan, not yet executed against these 7 targets — the
results in `result/` as of 2026-07-08 came from Magma. Use this path the
next time queues need refreshing, or when adding a target Magma doesn't
have (OSS-Fuzz covers 1000+ projects vs. Magma's fixed list of 10).

---

## 5. Part C — Mine hard branches (llmfuzz)

For each target, replay its AFL queue through its coverage binary and mine. Do
the one-time format check first (below), then loop over targets:

```bash
cd /path/to/llmfuzz

# ONE-TIME: confirm your llvm-cov branch format matches frontier.py
#   run cov binary on a seed -> export -> eyeball a branch tuple.
LLVM_PROFILE_FILE=t.profraw ./cov_libpng -runs=0 seed.png
llvm-profdata merge t.profraw -o t.profdata
llvm-cov export ./cov_libpng -instr-profile=t.profdata | python3 -m json.tool | grep -A2 branches | head
#   -> the 5th & 6th numbers must be exec counts (true, false). LLVM 18 appends a
#      9th field; harmless. If the layout differs, tweak L_TRUE/L_FALSE in frontier.py.

# mine each target (libfuzzer mode = replays the whole queue dir at once)
./afl_workflow.sh <afl_bin> ./cov_libpng \
    workdir/ar/aflplusplus/libpng/libpng_read_fuzzer/0/findings/queue \
    png result/libpng libfuzzer
#   -> result/libpng/hard.jsonl
```

> **llvm-cov version mismatch:** `.profraw` is version-specific, and this is
> not a theoretical warning — we hit it for real on `libtiff`/`openssl`
> (`raw profile format version = 4; expected version = 10`). Magma's
> coverage binary is built with `clang-9` (2019, hardcoded in
> `magma/fuzzers/llvm_cov/preinstall.sh`), which is almost certainly older
> than your host llvm. Two fixes, cheapest first:
> 1. Run the mining inside the container where the versions match instead of
>    on the host — mount llmfuzz in and run `mine.sh` there:
>    ```bash
>    docker run --rm -v "$PWD/llmfuzz:/llmfuzz" -v "$PWD/workdir:/workdir" \
>        magma/llvm_cov/libpng bash -c \
>        "cd /llmfuzz && ./mine.sh /magma_out/libpng_read_fuzzer /workdir/.../queue png /out libfuzzer"
>    ```
> 2. If that's not workable, rebuild the coverage binary manually on the host
>    with the host's own clang (what we ended up doing for `libtiff`/
>    `openssl`) — works, but means re-deriving each library's build flags by
>    hand instead of reusing its own build script.
>
> Going forward, prefer **§4b (OSS-Fuzz)** instead of either workaround: build
> and profile happen in the same container there, so this class of bug can't
> occur regardless of how old or new that container's LLVM is.

Then **curate**: open each `hard.jsonl`, keep the ~5-10 that are genuinely
input-reachable format checks (magic values, field constraints, checksum-gated
paths). Drop length guards, OOM/error paths, and harness plumbing.

**Validate Part C:**
```bash
wc -l result/*/hard.jsonl                     # each should have branches
python3 report_branches.py result/libpng/hard.jsonl --src <src files> --out libpng_hard.md
# spot-check: open libpng_hard.md, confirm the marked lines are real parse checks
```

---

## 6. Part D — Package to share with lab mates

```bash
./package_benchmark.sh libpng result/libpng/hard.jsonl \
    result/libpng/mincorpus share <src files...>
#   -> share/libpng_benchmark.tar.gz  (hard.jsonl + report + corpus + MANIFEST.txt)
```
Fill in the two blank lines in `MANIFEST.txt` (library version/commit, harness)
before sending — a `FILE:LINE` is meaningless without which libpng and which
harness it came from.

---

## 7. Part E — Test with the LLM (offline, NO afl)

Point `run_benchmark.py` at each target's branches + coverage binary + a valid
seed. This is the actual experiment.

```json
{ "targets": [ {
    "name": "libpng", "input_type": "binary",
    "src": ["pngrutil.c", "harness.c"],
    "seed": "seeds/valid.png",
    "cov_harness": "cov_libpng",
    "branches": "result/libpng/hard.jsonl"
} ] }
```
```bash
# confirm `claude` is logged in and reachable non-interactively first:
claude --print "hi"

# then confirm the wiring on ONE branch:
python3 offline.py --branch pngrutil.c:1234 --missing-arm T \
    --src pngrutil.c harness.c --seed seeds/valid.png --out gen.png

# then the full benchmark with the ablation:
python3 run_benchmark.py --config benchmark.json --tools both --agentic 4
```
Output = reach-rate (how many hard branches the LLM flipped), split by text vs
binary and **tools-on vs tools-off** — the core result. No `afl-fuzz` runs here;
the verifier replays each generated input through the coverage binary and checks
the branch flipped.

---

## 8. Validation checklist (per stage)

| stage | check | pass condition |
|-------|-------|----------------|
| toolchain | `verify_all.py` / `test_all.py` | passes (17 checks in `test_all.py`) |
| A: fuzzing | `docker ps`; queue file counts | containers up; queues grow then plateau |
| A: coverage | run cov binary on a seed | writes a `.profraw` |
| format | eyeball an `llvm-cov export` branch tuple | idx 4,5 are true/false counts |
| C: mining | `wc -l result/*/hard.jsonl` | non-empty; lines are real parse checks |
| D: package | open `MANIFEST.txt` | provenance filled in |
| E: LLM link | `offline.py` on one branch (`claude` logged in, no `--backend` flag) | writes an output file |
| E: results | `run_benchmark.py` | prints reach-rate + ablation table |

---

## 9. Timing & resource plan for the i5-13400F

- **Concurrency:** 10 physical cores → run all 10 programs at once, one core each
  (Magma schedules one campaign per core). If this is also your daily machine,
  drop to 8 concurrent and leave 2 cores for the OS.
- **E-cores are slower:** the 4 E-cores do fewer execs/sec, so targets scheduled
  there plateau later. Put the heavier targets (poppler, php, openssl, sqlite3)
  on P-cores and the light ones (libpng, lua) on E-cores if you pin manually.
- **Duration:** `TIMEOUT=14h` per campaign (overnight); all 10 run concurrently,
  so ≈14h wall-clock + one-time image build (~1-3h). Smoke-test with
  `TIMEOUT=10m` first to confirm the whole pipeline before committing the night.
- **Plateau > clock:** the real signal is the queue/edge count going flat for
  ~6h. Small targets (libpng, lua, libsndfile, libxml2) plateau well within 14h;
  the big ones (php, poppler) may still be climbing — that's fine, branches still
  uncovered after 14h of AFL++ with CmpLog are legitimately hard. Note the
  duration in the manifest and re-run those two longer later if you want.
- **RAM:** ~31 GB is comfortable for 10 AFL instances; watch poppler/php. If the
  box swaps, reduce concurrency.
- **Disk:** budget a few GB per campaign for queues/crashes; you have ~1.8 TB.
- **Rigor note:** one overnight (~14h) campaign per target is fine for
  *producing* a hard-branch list. For the later *online* A/B (does the LLM
  mutator help AFL), follow Klees et al.: ≥5 trials/arm, 24h each, with
  statistical tests.

---

## 10. Appendix — exact commands run, 2026-07-08 (7-target mining pass)

This is the literal, reproducible transcript that produced the `result/`
directory as it stands today (14,983 hard branches across 7 targets). Kept
verbatim, gotchas and all, instead of the idealized version — if you're
re-running this on a fresh machine, the failures below are exactly what
you'll hit too. Magma's overnight AFL++/CmpLog queues were already on disk
under `magma/tools/captain/workdir/`; this appendix starts from there.

`mine.sh` itself was edited first (see the diff in this repo's history): the
old hardcoded `--top 40` became an optional `[cap]` arg (default 100000,
effectively uncapped), a 15s-per-input `timeout` was added around the
standalone-mode replay loop, and an optional `[export_bin]` 7th arg was added
so `HARNESS` can be a one-arg wrapper script while `llvm-cov export` still
reads the real instrumented ELF.

### libpng, sqlite3, libsndfile — binaries already built, just regenerate hard.jsonl

These three already had a coverage binary and a merged `cov.json` on disk
from an earlier session (built per the manual recipe: clone at the pinned
commit, `clang -g -fprofile-instr-generate -fcoverage-mapping`, link with
the `driver.c` pattern from §1). No replay needed — just rerun the miner
directly on the existing `cov.json` with the new uncapped `--top`:

```bash
cd /home/mambo/Downloads/llmfuzz

python3 frontier.py result/libpng/cov.json --top 100000 \
    --include libpng --exclude harness --exclude driver.c \
    --jsonl result/libpng/hard.jsonl.new
mv result/libpng/hard.jsonl.new result/libpng/hard.jsonl        # 333 branches

python3 frontier.py result/sqlite3/cov.json --top 100000 \
    --include "sqlite3.c" --exclude harness --exclude driver.c --exclude ossfuzz.c \
    --jsonl result/sqlite3/hard.jsonl.new
mv result/sqlite3/hard.jsonl.new result/sqlite3/hard.jsonl      # 3,835 branches

python3 frontier.py result/libsndfile/cov.json --top 100000 \
    --include libsndfile_src --exclude harness --exclude driver.c --exclude sndfile_fuzzer \
    --jsonl result/libsndfile/hard.jsonl.new
mv result/libsndfile/hard.jsonl.new result/libsndfile/hard.jsonl  # 930 branches
```
`--include sqlite3.c` (not `sqlite_src`) matters: the harness lives at
`sqlite_src/test/ossfuzz.c`, which a bare `sqlite_src` include would have
pulled in alongside the real library file. Same reasoning for excluding
`sndfile_fuzzer` from the libsndfile include.

### libtiff — full manual build, both programs (tiff_read_rgba_fuzzer + tiffcp)

The leftover `magma/tools/captain/cov_libtiff_out/*` binaries (built earlier
through Magma's own `llvm_cov` fuzzer / Docker pipeline) had the right pinned
commit but were incompatible with this host's `llvm-profdata` — raw profile
format version 4 vs. expected version 10, because Magma's Docker image pins
`clang-9` from 2019. Rebuilt from scratch on host instead:

```bash
rm -rf /tmp/libtiff_src
git clone --no-checkout https://gitlab.com/libtiff/libtiff.git /tmp/libtiff_src
cd /tmp/libtiff_src
git checkout c145a6c14978f73bb484c955eb9f84203efcb12e

export CC=clang CXX=clang++
export CFLAGS="-g -fprofile-instr-generate -fcoverage-mapping"
export CXXFLAGS="-g -fprofile-instr-generate -fcoverage-mapping"
export LDFLAGS="-fprofile-instr-generate -fcoverage-mapping"

./autogen.sh   # exits 127 -- fails trying to `wget` a config.guess/config.sub
               # refresh (no wget on this host); harmless, `configure` was
               # already generated by the time it fails, so just continue.
./configure --disable-shared
make -j$(nproc)
```

Compile the vendored harness (`magma/targets/libtiff/src/tiff_read_rgba_fuzzer.cc`,
C++, needs `tiffio.hxx`) and link it against the freshly-built static libs.
The driver must be compiled separately in C mode — `clang++` treats `.c`
files as C++, and `driver.c`'s `uint8_t *buf = malloc(sz)` needs an explicit
cast under C++ that we didn't want to add to the shared driver file:

```bash
clang -g -fprofile-instr-generate -fcoverage-mapping -c /tmp/driver.c -o /tmp/driver_c.o

clang++ -g -fprofile-instr-generate -fcoverage-mapping -std=c++11 \
  -I/tmp/libtiff_src/libtiff \
  -c /home/mambo/Downloads/llmfuzz/magma/targets/libtiff/src/tiff_read_rgba_fuzzer.cc \
  -o /tmp/tiff_read_rgba_fuzzer.o

clang++ -g -fprofile-instr-generate -fcoverage-mapping \
  /tmp/tiff_read_rgba_fuzzer.o /tmp/driver_c.o \
  -o /tmp/tiff_read_rgba_fuzzer_cov \
  /tmp/libtiff_src/libtiff/.libs/libtiffxx.a /tmp/libtiff_src/libtiff/.libs/libtiff.a \
  -lz -ljpeg -ljbig -llzma -lzstd -lwebp -ldeflate -lstdc++ -lm
```
Two deviations from the link recipe as originally described: (1) dropped
`-Wl,-Bstatic -llzma -Wl,-Bdynamic` for a plain `-llzma` — this host has no
static `liblzma.a`, only the shared lib; (2) added `-lzstd -lwebp -ldeflate`
— this host's `./configure` auto-detected zstd/webp/libdeflate support (all
installed), so the built `libtiff.a` needed those symbols at link time even
though the original recipe didn't mention them.

`tiffcp` needs no separate harness — it's `/tmp/libtiff_src/tools/tiffcp`,
a real CLI straight out of the same build. But it's a 2-arg tool
(`tiffcp -M in.tif out.tif`) and mine.sh's standalone loop only passes one
arg, so it needs a wrapper — and a subtler problem: AFL queue filenames look
like `id:000000,time:0,orig:foo.tif`, and libtiff's CLI tools parse a comma
in the filename as the "open TIFF directory N" separator (`file.tif,3`), so
passing the raw queue filename truncates at the first comma and `TIFFOpen`
fails. The wrapper copies to a comma-free path first:

```bash
mkdir -p /tmp/scratch
cat > /tmp/tiffcp_wrapper.sh <<'EOF'
#!/bin/bash
cp "$1" /tmp/scratch/tiffcp_in.tif
exec /tmp/libtiff_src/tools/tiffcp -M /tmp/scratch/tiffcp_in.tif /tmp/scratch/tiffcp_tmp.out
EOF
chmod +x /tmp/tiffcp_wrapper.sh
```

Mine both programs:

```bash
cd /home/mambo/Downloads/llmfuzz
rm -rf result/libtiff_rgba result/libtiff_cp
mkdir -p result/libtiff_rgba result/libtiff_cp

./mine.sh /tmp/tiff_read_rgba_fuzzer_cov \
  magma/tools/captain/workdir/ar/aflplusplus/libtiff/tiff_read_rgba_fuzzer/0/findings/default/queue \
  "tif_" result/libtiff_rgba standalone 100000     # 1,360 branches

./mine.sh /tmp/tiffcp_wrapper.sh \
  magma/tools/captain/workdir/ar/aflplusplus/libtiff/tiffcp/0/findings/default/queue \
  "tif" result/libtiff_cp standalone 100000 /tmp/libtiff_src/tools/tiffcp   # 1,809 branches
```
Include patterns differ on purpose: `tif_` (with the trailing underscore)
matches every `tif_*.c` library file but *not* the harness
(`tiff_read_rgba_fuzzer.cc` has no `tif_` substring) — needed since that
harness is linked into the rgba binary. The tiffcp binary never links that
harness at all, so the looser `tif` (no underscore) is safe there and also
picks up `tools/tiffcp.c` itself (`tiffcp.c` contains `tif`).

### openssl — full manual build

Also not usable from the leftover `cov_openssl_out/asn1` (same profile
version mismatch as libtiff, same root cause). Rebuilt on host:

```bash
rm -rf /tmp/openssl_src
git clone --no-checkout https://github.com/openssl/openssl.git /tmp/openssl_src
cd /tmp/openssl_src
git checkout 3bd5319b5d0df9ecf05c8baba2c401ad8e3ba130

export CC=clang CXX=clang++
export CFLAGS="-fprofile-instr-generate -fcoverage-mapping"
export CXXFLAGS="-fprofile-instr-generate -fcoverage-mapping"
./config --debug enable-fuzz-libfuzzer enable-fuzz-afl disable-tests -DPEDANTIC \
  -DFUZZING_BUILD_MODE_UNSAFE_FOR_PRODUCTION no-shared no-module \
  enable-tls1_3 enable-rc5 enable-md2 enable-ec_nistp_64_gcc_128 enable-ssl3 \
  enable-ssl3-method enable-nextprotoneg enable-weak-ssl-ciphers \
  $CFLAGS -fno-sanitize=alignment

make -j$(nproc) LDCMD="$CXX $CXXFLAGS"
```
This `make` fails at the final `fuzz/asn1` (and every other `fuzz/*`) link
step with `undefined reference to main`, for two stacked reasons: (1) the
Makefile recipe uses shell syntax `${LDCMD:-clang}`, and a `make VAR=val`
command-line assignment isn't reliably exported into that recipe's shell, so
it silently fell back to plain `clang`; (2) more fundamentally,
`fuzz/driver.c` compiles out its own `main()` whenever
`OPENSSL_NO_FUZZ_LIBFUZZER` is undefined — i.e. whenever
`enable-fuzz-libfuzzer` is set (exactly what Magma's own build.sh passes) —
and instead only defines `LLVMFuzzerInitialize`/`LLVMFuzzerTestOneInput`
shims, expecting an external fuzzing engine to supply `main()`. Either fix
alone (fixing LDCMD, or just dropping `enable-fuzz-libfuzzer`) would still
leave the other problem. By the time `make` fails, every object file needed
already exists (`fuzz/asn1-bin-asn1.o`, `fuzz/asn1-bin-driver.o`,
`fuzz/asn1-bin-fuzz_rand.o`), so relink by hand using Magma's own standalone
driver as the missing `main()`:

```bash
clang -g -fprofile-instr-generate -fcoverage-mapping -c \
  /home/mambo/Downloads/llmfuzz/magma/fuzzers/llvm_cov/src/StandaloneFuzzTargetMain.c \
  -o /tmp/StandaloneFuzzTargetMain.o

cd /tmp/openssl_src
clang -pthread -m64 -fno-omit-frame-pointer -g -fprofile-instr-generate \
  -fcoverage-mapping -fno-sanitize=alignment -L. \
  -o /tmp/asn1_cov \
  fuzz/asn1-bin-asn1.o fuzz/asn1-bin-driver.o fuzz/asn1-bin-fuzz_rand.o \
  /tmp/StandaloneFuzzTargetMain.o \
  -lssl -lcrypto -ldl -pthread
```
This is exactly why the task notes' guess turned out right in spirit but
wrong in mechanism: an external fuzzing-engine main() genuinely was needed
(so `LIB_FUZZING_ENGINE` wasn't a red herring), it just needed to be supplied
as a link input after-the-fact rather than as a `LIB_FUZZING_ENGINE`
environment variable before `make`.

Mine it:

```bash
cd /home/mambo/Downloads/llmfuzz
mkdir -p result/openssl
./mine.sh /tmp/asn1_cov \
  magma/tools/captain/workdir/ar/aflplusplus/openssl/asn1/0/findings/default/queue \
  "crypto" result/openssl standalone 100000    # 4,247 branches
```
`--include crypto` alone is enough to exclude both the harness (`fuzz/asn1.c`
has no `crypto` substring) and the `apps/`/`test/` trees, without needing an
extra `--exclude`.

### poppler — binary already built, just needed a clean full replay

`/tmp/pdf_fuzzer_cov` (two-stage build: freetype2 then poppler via cmake, per
the recipe in §3b/notes) already existed from an earlier session, and an
earlier partial replay had gotten through 12,392 of 13,153 queue files before
stalling — almost certainly the "PDF causes an infinite loop" input the
15s-per-input timeout in the rewritten `mine.sh` exists to handle. Just
re-ran the full replay with the fixed script:

```bash
cd /home/mambo/Downloads/llmfuzz
rm -rf result/poppler
mkdir -p result/poppler
./mine.sh /tmp/pdf_fuzzer_cov \
  magma/tools/captain/workdir/ar/aflplusplus/poppler/pdf_fuzzer/0/findings/default/queue \
  "poppler_src" result/poppler standalone 100000    # 2,469 branches
```

### Final tally

```bash
wc -l result/*/hard.jsonl
#    333 result/libpng/hard.jsonl
#    930 result/libsndfile/hard.jsonl
#   1809 result/libtiff_cp/hard.jsonl
#   1360 result/libtiff_rgba/hard.jsonl
#   4247 result/openssl/hard.jsonl
#   2469 result/poppler/hard.jsonl
#   3835 result/sqlite3/hard.jsonl
#  14983 total
```

## 11. Appendix — wiring the offline benchmark for real, 2026-07-08

Picking up from §7/§10 with `claude` actually logged in on this machine.
Goal: get `run_benchmark.py --config benchmark.json --tools both --agentic 4`
running against all 7 curated sets above. Results so far:

**Bug found and fixed: `ClaudeCLIBackend` was silently returning nothing.**
`offline.py` called `claude --print --output-format json`, but that flag
combo returns one `{"type":"result","result":"..."}` object, not the
streamed `assistant`/`thinking` message blocks the parser was written to
read — so every real call parsed to `("", "")`, and `extract_patch()` raised
`ValueError: no patch/hex block found` downstream. Fix: use
`claude --print --output-format stream-json --verbose` instead (the CLI
requires `--verbose` whenever `--print` is combined with `stream-json`).
`run_benchmark.py` reuses `offline.ClaudeCLIBackend`, so it inherited the fix
for free. Confirmed for real against `result/libpng/curated.jsonl` line 1
(the magic-signature branch): given a valid seed PNG, the model read
`formats.py`'s `parse()`/`hexdump()` output, correctly identified the
signature check, and emitted a 1-byte patch (`offset 1: 0x50->0x00`) that
`materialize()`/`fix()` applied exactly as reasoned — see the repro command
in `HANDOFF.md`.

**`probe.replay_verifier()` gained an `export_bin` param**, mirroring
`mine.sh`'s `[export_bin]` 7th arg (see §10's libtiff_cp notes above): when
`cov_harness` is a one-arg wrapper script for a multi-arg CLI tool (tiffcp
needs `tiffcp -M in out`, not a single positional arg), `llvm-cov export`
must still read the coverage mapping from the real instrumented ELF, not the
wrapper shell script. `run_benchmark.py`'s `run_one()` now passes
`target.get("export_bin")` through to the verifier.

**Built `benchmark.json`** (kept out of git — see `.gitignore` — since its
paths point at this machine's `/tmp` build dirs; `benchmark.example.json`
remains the portable template). Rather than assume each cov binary's
calling convention, confirmed it empirically: ran each one both as
`LLVM_PROFILE_FILE=... ./cov_bin -runs=0 seed` (libFuzzer convention) and
`LLVM_PROFILE_FILE=... ./cov_bin seed` (standalone, `argv[1]`), and checked
exit code + output:

| target | cov_harness | convention |
|---|---|---|
| libpng | `/tmp/libpng_cov` | libFuzzer (`-runs=0`) |
| libsndfile | `/tmp/libsndfile_src/ossfuzz/sndfile_fuzzer` | libFuzzer |
| libtiff_rgba | `/tmp/tiff_read_rgba_fuzzer_cov` | libFuzzer |
| poppler | `/tmp/pdf_fuzzer_cov` | libFuzzer |
| sqlite3 | `/tmp/sqlite3_cov` | libFuzzer |
| **openssl** | `/tmp/asn1_cov` | **standalone** — `-runs=0` crashes it (`StandaloneFuzzTargetMain.c:32: Assertion 'f' failed`, it tries to open a file literally named `-runs=0`); needs seed as bare `argv[1]` |
| **libtiff_cp** | `/tmp/tiffcp_wrapper.sh` (`export_bin`: real `/tmp/libtiff_src/tools/tiffcp`) | **standalone**, real 2-arg CLI tool wrapped per §10 |

So only openssl and libtiff_cp need `"standalone": true` in the config; the
rest use `replay_verifier`'s default libFuzzer-style runner.

**Smoke-tested** a 1-branch-per-target config
(`--tools both --agentic 1`) — 6 of 7 targets ran clean end-to-end
(generate → verify against the coverage build). **sqlite3 fails.**

**Blocker, not yet fixed: sqlite3's prompt blows the context window.**
sqlite3's harness source is a single 8MB amalgamated `sqlite3.c`
(`/tmp/sqlite_src/sqlite3.c`, ~8.3M characters). `bundle_sources()` in
`offline.py` inlines every `--src` file's full text into the prompt
unconditionally — for sqlite3 that alone produces an 8.3-million-character
prompt, and the `claude` CLI call fails (`rc=1`, empty stderr). Note that
`branch_context()` already extracts a small ±10-line window around the
target line separately and puts it in the prompt's "Surrounding code"
section — the full-file dump is largely redundant for what the model
actually needs to reason about the target branch. Candidate fixes (not yet
decided): cap `bundle_sources()`'s per-file size generically (skip the full
dump above some threshold, note the file was omitted, rely on
`branch_context()`), or don't reference the full `sqlite3.c` from
`benchmark.json`'s sqlite3 entry in the first place. See `HANDOFF.md` for
the open question.

**Not yet run:** the full `run_benchmark.py --config benchmark.json --tools
both --agentic 4` pass — blocked on the sqlite3 fix above. At `--agentic 4`
with `--tools both` across ~60 branches this is a real number of live Claude
CLI calls (up to 4 refine iterations x 2 tools-modes per binary branch), so
budget for that — not instant, not free.
