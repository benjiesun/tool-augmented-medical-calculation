# Reproduction guide

## What this repository can reproduce

The repository contains the complete inference/evaluation source, the fixed 55-tool GPT-5.5 calculator set, schema/few-shot artifacts, aggregate results, and a pinned benchmark downloader.

CPU-only validation can check:

- Python syntax and package imports;
- exactly 55 calculator IDs;
- calculator execution on representative inputs;
- numeric-safe parameter matching and calculator-69 adapter behavior;
- Figure 2 prompt contracts across the three runtime stages;
- JSON/JSONL integrity;
- final-manuscript Figures 1 and 2 checksums and dimensions;
- absence of common secrets, personal server paths, and GitHub-prohibited large files.

## External requirements

The full model run requires:

- Linux with CUDA-capable NVIDIA GPUs;
- Qwen3-8B base weights;
- the Qwen3-8B extraction LoRA adapter used by the submitted run;
- configured API access or local weights for any reasoning/tool-writing models;
- sufficient disk and GPU memory for vLLM.

Model weights and the final extraction adapter were not present in the source material and are not fabricated here. Until the adapter, training command, exact dependency lock, hardware details, and checksums are released, this repository must not claim one-command reproduction of the 86.73% submitted result.

The final supplied LaTeX manuscript, `bibm_arivx.zip` / `main.tex`, reports the following
extraction-training configuration in Table I. These are paper-reported
settings, not a reconstructed training run:

| Setting | Reported value |
|---|---|
| Base model | Qwen3-8B |
| Tuning | LoRA on a frozen base model |
| LoRA rank / alpha / dropout | 16 / 32 / 0.05 |
| Learning rate | 5e-5 |
| Epochs | 5 |
| Global batch size | 8 |
| Maximum training sequence length | 8,192 |

The final paper reports inference timing on two NVIDIA RTX 5090 GPUs.
The training command, seed, final adapter, checkpoint selection, exact
software/CUDA versions, and original training hardware still need to be
provided for exact reproduction. Reported timing is whole-run time divided
by 1,100 cases, excludes tool construction, and is not individual-request latency.

## Prompt templates

The three main prompts use the final paper's Figure 2 contract in
`src/toolmed_agent/prompts.py`. See [PROMPTS.md](PROMPTS.md) for the mapping
to rule curation, tool generation, and parameter extraction. Schemas and
three demonstrations are supplied at runtime; full LLM responses are not
repository inputs. The no-web ablation intentionally does not use the full
retrieval prompt.

These code templates have been aligned with the final source. This is not
a claim that the modified prompts were rerun to achieve the historical
86.73% result. The frozen tools remain unchanged.

## Prepare

```bash
python -m pip install -r requirements.txt
python -m pip install -e .
python scripts/download_data.py
cp configs/runtime.env.example runtime.env
```

Edit `runtime.env` with local paths or API settings. It is ignored by Git.

## Validate the fixed tools

The submitted 94.91% tool score uses benchmark ground-truth parameters and the
submitted project evaluator, which is also used by current runs:

```bash
python scripts/evaluate_calculators.py
```

The previous `--legacy-evaluator` flag remains accepted for command compatibility;
both forms use the submitted evaluator. This command evaluates tool execution
only; it is not an end-to-end extraction result.

## Reuse the fixed tools

The main configuration points `TOOL_PATH` at:

```text
artifacts/calculators/gpt_5_5
```

and sets `LOCAL_TOOLS_ONLY=1`. Run:

```bash
LIMIT=1 bash scripts/run_pipeline.sh
```

Increase `LIMIT` only after the smoke test succeeds. Outputs are written to ignored `output/`, `result/`, and `judge/` directories.
Keep per-case predictions, raw answers, and complete requests local. Leave
`TRACE_FULL_LLM_IO=0` unless privately debugging. Publication checks reject
raw trace files even if they are force-added to Git.

## Rebuild tools

The package exposes:

```bash
toolmed-build-tools --help
toolmed-build-tools-no-web --help
```

From-scratch tool building requires a legally obtained rule corpus and the
downloaded training set. Captured MDCalc text and raw tool-building prompts are
not redistributed. The original private `build_rag_docs.py` and its input
guides are also absent. Supply prepared rule documents explicitly:

```bash
toolmed-build-tools --base_dir . --train_csv data/processed/train_data.csv --stage1_docs_jsonl rag_docs/stage1_tool_builder.jsonl --sample_per_calc 8 --max_rounds 5
```

The local `rag_docs/stage1_tool_builder.jsonl` must contain the authorized rule
corpus and is ignored by Git. Set `TOOL_WRITER_API_BASE`, `TOOL_WRITER_API_KEY`,
and `TOOL_WRITER_MODEL_NAME` in the process environment; the standalone builder
does not load `runtime.env` automatically. This command expresses the latest
paper's eight-example/four-repair profile, but is not a claim of exact
regeneration of the released tools. `max_rounds` includes the initial
generation: five total rounds permit at most four subsequent repair rounds.

### Confirmed generation settings and selection

The latest supplied manuscript states eight same-calculator training examples
and up to four subsequent validation-and-repair rounds (pages 3-4). The
original launch script uses `MAX_ROUNDS=5` and `SAMPLE_PER_CALC=8`. Archived
records confirm eight validation examples for each of the 55 calculators,
the same sample set reused in each executed validation round, and no
candidate-generation round above five. The `r5_s8` identifier therefore
matches the latest paper. The previous five-versus-eight discrepancy was
based on an older manuscript and is resolved.

See [generation_summary.json](../artifacts/calculators/gpt_5_5/generation_summary.json)
for source checksums and aggregate selection records. Of the 55 selected
tools, 53 passed all eight training checks. Calculators 24 and 33 retained
their best candidates without passing every training check. All 55 were kept
in the reported test evaluation; the tool score remains 94.91%.

The optional on-demand and retrieval-builder defaults now use five total
rounds and eight validation examples. The on-demand path reads validation
samples only from `TOOL_TRAIN_CSV`, never from the evaluated test cases;
it samples without replacement and reuses that selection across repairs.
Use the explicit arguments above to make the profile unambiguous. Newly generated tools may differ
from the frozen set and must be evaluated separately.

For the paper's direct-generation ablation (no retrieval and no repair):

```bash
toolmed-build-tools-no-web --base_dir . --train_csv data/processed/train_data.csv --sample_per_calc 8 --max_rounds 1
```

## Evaluation semantics

The reported final-answer metric evaluates the deterministic tool output, not the optional central-LLM prose formatter. `ENABLE_CENTRAL_FINAL_ANSWER` may produce display text, but it does not change `judge_case` scoring.

Current runs retain the submitted calculator-69 final-answer adapter and
scoring rules; parameter matching is separately fixed and identified as
`numeric-safe-v2`. There is no alternate final-answer adapter mode. The previous `LEGACY_EVALUATOR`
environment setting no longer selects a different parser. See
[results/KNOWN_ISSUES.md](../results/KNOWN_ISSUES.md) for the distinction between
the project's answer adapter and the official benchmark scoring function.
