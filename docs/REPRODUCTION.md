# Reproduction guide

## What this repository can reproduce

The repository contains the complete inference/evaluation source, the fixed 55-tool GPT-5.5 calculator set, schema/few-shot artifacts, aggregate results, and a pinned benchmark downloader.

CPU-only validation can check:

- Python syntax and package imports;
- exactly 55 calculator IDs;
- calculator execution on representative inputs;
- calculator-69 evaluator regression behavior;
- JSON/JSONL integrity;
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
legacy evaluator:

```bash
python scripts/evaluate_calculators.py --legacy-evaluator
```

Omitting `--legacy-evaluator` applies the calculator-69 parser correction
documented below. This command evaluates tool execution only; it is not an
end-to-end extraction result.

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

From-scratch tool building requires a legally obtained rule corpus and the downloaded training set. Captured MDCalc text and raw tool-building prompts are intentionally not redistributed.

### Configuration discrepancy requiring author resolution

The submitted paper text describes up to five same-calculator validation examples and four repair rounds. The exact fixed tool artifact used by the reported main run retains the earlier work-log identifier `r5_s8`, indicating an eight-sample/five-round generation budget. Reusing the released tool files reproduces the artifact; regenerating from paper text may produce a different tool set.

Before a public reproducibility claim or camera-ready release, the authors should either:

1. update the manuscript to describe the actual artifact settings, or
2. regenerate tools with the stated 5-example/4-repair configuration and rerun every affected table.

## Evaluation semantics

The reported final-answer metric evaluates the deterministic tool output, not the optional central-LLM prose formatter. `ENABLE_CENTRAL_FINAL_ANSWER` may produce display text, but it does not change `judge_case` scoring.

The submitted tables used the legacy calculator-69 parser. Current runs use the corrected parser; see [results/KNOWN_ISSUES.md](../results/KNOWN_ISSUES.md).
