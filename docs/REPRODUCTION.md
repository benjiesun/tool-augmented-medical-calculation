# Reproduction guide

## What this repository can reproduce

The repository contains the complete inference/evaluation source, the fixed 55-tool GPT-5.5 calculator set, schema/few-shot artifacts, aggregate results, and a pinned benchmark downloader.

CPU-only validation can check:

- Python syntax and package imports;
- exactly 55 calculator IDs;
- calculator execution on representative inputs;
- calculator-69 evaluator regression behavior;
- JSON/JSONL integrity;
- the original manuscript Figure 1 checksum and dimensions;
- absence of common secrets, personal server paths, and GitHub-prohibited large files.

## External requirements

The full model run requires:

- Linux with CUDA-capable NVIDIA GPUs;
- Qwen3-8B base weights;
- the Qwen3-8B extraction LoRA adapter used by the submitted run;
- configured API access or local weights for any reasoning/tool-writing models;
- sufficient disk and GPU memory for vLLM.

Model weights and the final extraction adapter were not present in the source material and are not fabricated here. Until the adapter, training command, exact dependency lock, hardware details, and checksums are released, this repository must not claim one-command reproduction of the 86.73% submitted result.

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
toolmed-build-tools --base_dir . --train_csv data/processed/train_data.csv --stage1_docs_jsonl rag_docs/stage1_tool_builder.jsonl --sample_per_calc 5 --max_rounds 5
```

The local `rag_docs/stage1_tool_builder.jsonl` must contain the authorized rule
corpus and is ignored by Git. Set `TOOL_WRITER_API_BASE`, `TOOL_WRITER_API_KEY`,
and `TOOL_WRITER_MODEL_NAME` in the process environment; the standalone builder
does not load `runtime.env` automatically. This command expresses the paper's
five-example/four-repair limits, but is not a claim of exact regeneration of
the released tools. `max_rounds` includes the initial generation: five total
rounds permit at most four subsequent repair rounds.

### Configuration discrepancy requiring author resolution

The submitted paper describes up to five same-calculator validation examples
and four repair rounds. The fixed artifact retains an `r5_s8` work-log
identifier, whose naming convention denotes five total rounds and eight
validation examples. Five total rounds are compatible with four repairs;
the round labels alone are not a discrepancy. The five-versus-eight example
count still requires confirmation against the selected generation runs.
Reusing the released files reproduces the artifact; rebuilding from paper
settings may produce a different tool set.

Before a public reproducibility claim or camera-ready release, the authors should either:

1. confirm the validation-example count from the original generation records
   and describe the settings actually used, or
2. regenerate tools with the stated five-example/four-repair configuration
   and rerun every affected table.

## Evaluation semantics

The reported final-answer metric evaluates the deterministic tool output, not the optional central-LLM prose formatter. `ENABLE_CENTRAL_FINAL_ANSWER` may produce display text, but it does not change `judge_case` scoring.

Current runs retain the submitted calculator-69 answer adapter and scoring
protocol. There is no alternate rescore mode. The previous `LEGACY_EVALUATOR`
environment setting no longer selects a different parser. See
[results/KNOWN_ISSUES.md](../results/KNOWN_ISSUES.md) for the distinction between
the project's answer adapter and the official benchmark scoring function.
