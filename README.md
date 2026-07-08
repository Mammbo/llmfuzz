# llmFuzz — LLM-guided hybrid fuzzing

An offline benchmark and online mutator that uses an LLM to get a fuzzer past
**hard branches** — conditionals the fuzzer reaches but never flips. The central
design choice: **one frontier extractor serves both jobs.** Offline it builds
the benchmark of hard branches; online it re-runs against the live corpus to
tell the LLM which wall the fuzzer is currently stuck against.

## What a "hard branch" is

A **one-sided branch**: `llvm-cov` reports the branch point as reached (one arm
has count > 0) while the other arm has count 0. That is exactly "the fuzzer got
up to this conditional and drove it one way thousands of times but never flipped
it." It comes out as `FILE:LINE`, which is what the generator consumes.

## The non-text problem (the actual research contribution)

Models don't understand raw bytes; they reason about binaries through
text-extraction tools (`pdftotext`, symbol dumps, file sniffing). So instead of
hoping the model's internal heuristics work, we hand it those tools explicitly
and deterministically (`formats.py`) and change the output contract: for binary
targets the model emits a **patch** (offset/hex edits) on a valid seed, and we
repair checksums/lengths afterward. The checksum-repair step (`fix`) is the
thing that silently kills naive LLM binary fuzzing — one edited byte and every
downstream CRC rejects the file long before the target branch.

## Components

| file | role |
|------|------|
| `frontier.py` | mine one-sided (hard) branches from an `llvm-cov export` JSON → `FILE:LINE` + `hard.jsonl` |
| `formats.py` | detect / parse / hexdump / patch / **checksum-fix** for PNG, PDF, MP4, ELF, gzip … |
| `offline.py` | generator: text (verbatim) + binary (seed+patch) modes; backend shells out to the Claude CLI (`claude --print`), no API key needed |
| `probe.py` | coverage verifier + agentic `generate → probe → refine` loop |
| `run_benchmark.py` | driver + **tools-on/off ablation** report |
| `test_all.py` | runnable suite for everything validatable without a target build |

## Pipeline (dependency order)

```bash
# 0. coverage-mapping build of the libFuzzer harness (alongside the AFL build)
clang -g -O1 -fsanitize=fuzzer -fprofile-instr-generate -fcoverage-mapping \
    harness.c target.c -o harness_cov

# 1. fuzz to saturation with AFL as usual, then replay the SATURATED corpus once
LLVM_PROFILE_FILE=cov.profraw ./harness_cov -runs=0 corpus_dir/*
llvm-profdata merge cov.profraw -o cov.profdata
llvm-cov export ./harness_cov -instr-profile=cov.profdata > cov.json

# 2. mine ~20 hard branches
python frontier.py cov.json --top 20 --include target --exclude harness \
    --jsonl out/libpng/hard.jsonl

# 3. offline benchmark with the ablation (needs `claude` logged in, no API key)
python run_benchmark.py --config benchmark.example.json --tools both --agentic 4
```

## Benchmark:

Magma is the credible substrate: standard, prebuilt AFL harnesses + seed
corpora, and **canaries at real bugs** behind hard branches, so the online
evaluation measures real bugs, not just crashes.

- **text:** sqlite3, openssl
- **binary:** libpng (PNG), libtiff (TIFF), poppler, FFmpeg / libarchive (container)

## Evaluation

- **Offline:** for each hard branch, run the generated input through the
  coverage build and check the previously-zero arm is now nonzero. Report by
  input type and by **tools-on vs tools-off** — that ablation is the experiment
  that tests whether the tooling layer is what makes non-text targets work.
- **Online:** A/B AFL vs AFL+llmFuzz-on-stall; edge coverage over time,
  time-to-cover the target branches, and bugs found (Magma canaries). ≥10 trials
  + Mann-Whitney U, per Klees et al. "Evaluating Fuzz Testing."

## Status

**Validated in-sandbox** (`python test_all.py`, 17 checks green):
frontier one-sided detection + ranking + filtering; PNG synth → patch → broken
CRC → `fix` → valid round trip; agentic loop refining a wrong guess into one
that flips the branch while keeping the file valid; ablation report rendering.

**Done on the lab machine (2026-07-08):** built coverage binaries and mined
`hard.jsonl` for 7 of the planned 10 Magma targets against overnight
AFL++/CmpLog queues — **14,983 raw hard branches**, then curated down to **60**
genuinely input-reachable format/parse decisions (rejecting malloc guards,
error-formatting, and generic loop bounds) and packaged for sharing:

| target | raw branches | curated | package |
|---|---:|---:|---|
| openssl (asn1) | 4,247 | 8 | `share/openssl_benchmark.tar.gz` |
| sqlite3 | 3,835 | 9 | `share/sqlite3_benchmark.tar.gz` |
| poppler (pdf_fuzzer) | 2,469 | 8 | `share/poppler_benchmark.tar.gz` |
| libtiff (tiffcp) | 1,809 | 9 | `share/libtiff_cp_benchmark.tar.gz` |
| libtiff (tiff_read_rgba_fuzzer) | 1,360 | 8 | `share/libtiff_rgba_benchmark.tar.gz` |
| libsndfile | 930 | 8 | `share/libsndfile_benchmark.tar.gz` |
| libpng | 333 | 10 | `share/libpng_benchmark.tar.gz` |

Each package bundles the curated `hard.jsonl`, a source-annotated
`hard_branches.md` report, a 30-file **unminimized** corpus sample (no
`afl-cmin` on this host — see LAB_WORKFLOW.md §10), and a `MANIFEST.txt` with
the exact pinned commit and harness path. All 7 match Magma's own pinned
commit **except libpng**, which was built from `pnggroup/libpng@d1d0abe`
instead of Magma's pinned `glennrp/libpng@a37d483` — see
`share/libpng/MANIFEST.txt` for the full note

**Claude CLI backend confirmed working end-to-end (2026-07-08):** the
original `ClaudeCLIBackend` shelled out to `claude --print --output-format
json`, which returns one `{"type":"result", "result": "..."}` object — not
the streamed `assistant`/`thinking` message blocks the parser expected, so
every real call silently came back empty. Fixed by switching to `claude
--print --output-format stream-json --verbose` (the `--verbose` flag is
required by the CLI whenever `--print` is combined with `stream-json`).
Confirmed with a real branch: given libpng's magic-signature check
(`result/libpng/curated.jsonl` line 1) plus a valid seed PNG, the model used
`formats.py`'s structural `parse()`/`hexdump()` to reason about the 8-byte
PNG signature, proposed a one-byte patch (`offset 1: 0x50 -> 0x00`) to break
`png_sig_cmp`, and `materialize()`/`fix()` applied it correctly — reproduce
with:
```bash
python3 offline.py --branch /tmp/libpng/pngrutil.c:135 --missing-arm T \
    --src /tmp/libpng/pngrutil.c \
    --seed magma/targets/libpng/corpus/libpng_read_fuzzer/not_kitty.png \
    --out /tmp/test_gen.png --cot /tmp/test_cot.txt
cat /tmp/test_cot.txt   # model's reasoning + the patch it emitted
```

`benchmark.json` (all 7 mined targets, gitignored — paths are host-specific
`/tmp` build dirs) is built and `run_benchmark.py --config benchmark.json
--tools both --agentic 1` runs clean on a 1-branch-per-target smoke config
for 6 of the 7 targets. **sqlite3 blocks the full run**: its harness source
is a single 8MB amalgamated `sqlite3.c`, and `bundle_sources()` in
`offline.py` inlines every `--src` file's full text into the prompt — for
sqlite3 alone that's an 8.3M-character prompt, which the Claude CLI rejects.
Needs a fix to `bundle_sources()` (or a different way to give the model
sqlite3 branch context) before the full 60-branch benchmark can run;
excluding sqlite3's target entry from `benchmark.json` unblocks the other 6
in the meantime.

Also added while wiring `run_benchmark.py`: `probe.replay_verifier()` now
takes an `export_bin` param, mirroring `mine.sh`'s existing `[export_bin]`
arg — needed because `libtiff_cp`'s harness is a wrapper script
(`tiffcp_wrapper.sh`, since `tiffcp` is a real 2-arg CLI tool) but
`llvm-cov export` must still read the real instrumented `tiffcp` ELF, not
the wrapper. `benchmark.json`'s `libtiff_cp` entry sets `cov_harness` to the
wrapper and `export_bin` to the real binary. Each of the 7 targets' actual
invocation convention (libFuzzer `-runs=0 file` vs. Magma's standalone
`StandaloneFuzzTargetMain` driver reading `argv[1]`) was confirmed
empirically rather than assumed — only `openssl`'s `asn1_cov` and
`libtiff_cp` need `"standalone": true`; the rest use the default runner.

**Still needs the lab machine:** the end-to-end AFL A/B. The report numbers
printed by the test suite are a **synthetic plumbing check**, not results.

## Next

1. Fix `bundle_sources()` in `offline.py` to handle oversized single-file
   sources (sqlite3.c is 8MB) before running the full offline ablation.
2. Run the offline ablation against the 60 curated branches with
   `run_benchmark.py --config benchmark.json --tools both --agentic 4`
   (Claude CLI backend, `probe.replay_verifier`).
3. Mine the remaining 3 targets (libxml2, lua, php) to complete the 10-target set.
4. For any future mining pass — new targets or re-fuzzing these 7 — prefer
   OSS-Fuzz over Magma's `llvm_cov` fuzzer for the coverage build. Magma's
   Docker images pin clang-9 (2019); its `llvm-cov` predates the JSON
   `branches` export field entirely, so mining fully inside a Magma container
   silently returns 0 branches instead of erroring. See LAB_WORKFLOW.md §4b
   for the concrete OSS-Fuzz commands and the one real tradeoff (no injected
   bug canaries, which only matters for step 6 below).
5. Extend `formats.py` PDF xref-repair and MP4 atom-size-repair to match PNG's CRC path.
6. Run the online A/B on libpng + poppler first (cleanest checksum stories) —
   note this stage wants Magma's bug canaries, so keep using Magma-fuzzed
   queues for it even after switching new mining to OSS-Fuzz.
