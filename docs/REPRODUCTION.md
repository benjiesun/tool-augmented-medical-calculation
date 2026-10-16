# Reproduction guide

## Environment and models

Calculator execution and tests require Python 3.10 or later. Local LLM inference uses vLLM on Linux with CUDA-capable NVIDIA GPUs.

```bash
python -m pip install -r requirements.txt
python -m pip install -e .
python -m pip install -r requirements-local.txt
python scripts/download_data.py
cp configs/runtime.env.example runtime.env
```

The local-inference dependencies are optional when using model APIs or running calculators only. Dependency ranges are specified in `pyproject.toml` and the requirements files; they are not an exact training-environment lock.

For the paper's extraction model, provide Qwen3-8B and its trained LoRA adapter:

```dotenv
EXTRACTION_MODE=local
EXTRACTION_MODEL_PATH=models/Qwen3-8B
EXTRACTION_USE_SFT=1
EXTRACTION_SFT_LORA_PATH=adapters/qwen3-8b-extraction
```

The trained extraction adapter and SFT training script are not included in this release. The paper specifies the following training settings:

| Setting | Value |
|---|---|
| Base model | Qwen3-8B |
| Tuning | LoRA on a frozen base model |
| LoRA rank / alpha / dropout | 16 / 32 / 0.05 |
| Learning rate | 5e-5 |
| Epochs | 5 |
| Global batch size | 8 |
| Maximum training sequence length | 8,192 |

Exact reproduction additionally requires the trained checkpoint, training seed, and software environment. The paper reports inference timing on two NVIDIA RTX 5090 GPUs; timing is total inference time divided by 1,100 cases and excludes tool construction.

## Model configuration

Edit `runtime.env` with local paths or API credentials. For an API-backed central model, configure:

```dotenv
CENTRAL_MODE=api
CENTRAL_API_BASE=https://your-endpoint.example/v1
CENTRAL_API_KEY=your-api-key
CENTRAL_MODEL_NAME=your-model-name
```

Replace these placeholders with your provider's values. `TOOL_WRITER_*` settings control the tool-generation model. The optional rule-curation model uses `RULE_RETRIEVER_*`, falling back to the tool writer when unset. Keep credentials in the Git-ignored `runtime.env` file.

The three main prompt templates are documented in [PROMPTS.md](PROMPTS.md).

## Fixed-tool execution

The default configuration uses the released calculator set:

```dotenv
TOOL_PATH=artifacts/calculators/gpt_5_5
LOCAL_TOOLS_ONLY=1
CASE_SEARCH_TOPK=3
DISABLE_UNIT_NORMALIZER=1
TOOL_INPUT_POLICY=raw_only
JUDGE_EXTRACTION_SOURCE=raw
```

Run one case after configuring the central and extraction models:

```bash
toolmed-run --root-dir . --env-file runtime.env --limit 1
```

Use `--limit 0` for the full test set. On Linux, `LIMIT=1 bash scripts/run_pipeline.sh` is an equivalent launcher. Case outputs, execution results, and evaluation records are written to `output/`, `result/`, and `judge/`; these directories are ignored by Git. `TRACE_FULL_LLM_IO=0` disables full request/response logging.

To evaluate the calculators independently using ground-truth parameters:

```bash
python scripts/evaluate_calculators.py
```

The released set scores 1,044/1,100 with no runtime errors under `submitted-adapter-v1`. This command tests tool execution; reproducing end-to-end accuracy also requires the extraction model. See [Evaluation](EVALUATION.md) for scoring details.

## Tool generation

The retrieval-based builder requires a prepared rule corpus and the downloaded training set. Supply the corpus through `--stage1_docs_jsonl`; see `toolmed-build-tools --help` for options. Set `TOOL_WRITER_API_BASE`, `TOOL_WRITER_API_KEY`, and `TOOL_WRITER_MODEL_NAME` in the process environment. The standalone builder does not automatically load `runtime.env`.

```bash
toolmed-build-tools --base_dir . --train_csv data/processed/train_data.csv --stage1_docs_jsonl rag_docs/stage1_tool_builder.jsonl --sample_per_calc 8 --max_rounds 5
```

The corpus is UTF-8 JSONL, one rule document per line. Each document should
contain `calculator_id` (string), `title` (calculator name), and `text` (the
formula, input definitions, conditions, and output rules). Optional `doc_id`,
`url`, and `source` fields record provenance. Include rule documents for each
calculator being generated. Use documents that you are permitted to process;
the local `rag_docs/` directory is ignored by Git.

Each calculator uses eight training examples for validation, sampled without replacement and reused across repairs. `max_rounds=5` permits an initial candidate and up to four repairs. The released tools and their selection statistics are documented in [Calculator artifacts](../artifacts/calculators/README.md).

The optional on-demand builder uses `TOOL_TRAIN_CSV`, `TOOL_WRITER_SAMPLE_PER_CALC=8`, and `TOOL_WRITER_MAX_ROUNDS=5`. It validates against training examples, independently of the evaluated test rows. Model sampling and provider versions can affect newly generated code, so evaluate regenerated tools separately.

For direct generation without retrieval or feedback repair:

```bash
toolmed-build-tools-no-web --base_dir . --train_csv data/processed/train_data.csv --sample_per_calc 8 --max_rounds 1
```

## Validation

```bash
python scripts/validate_artifacts.py
python -m unittest discover -s tests -v
python scripts/run_calculator.py --input examples/mean_arterial_pressure/input.json
```

These CPU checks cover artifact integrity, calculator execution, parameter matching, answer conversion, prompt entry points, and training/test separation. They do not require model credentials.
