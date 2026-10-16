# Tool-Augmented Large Language Models for Reliable Medical Calculation from Patient Notes

[English](README.md) | [中文](docs/README_zh.md)

Yang Zhong, Ling Luo, Xuanlyu Zhu, Yanhua Wang, Yuanyuan Sun, Jian Wang, Hongfei Lin

Code for *Tool-Augmented Large Language Models for Reliable Medical Calculation from Patient Notes*.

The framework combines schema-constrained parameter extraction with reusable Python calculators. It retrieves and structures medical calculation rules, generates tools with execution-based feedback, and applies the validated tools to parameters extracted from patient notes. The paper reports **86.73% final-answer accuracy** on MedCalc-Bench Verified v1.0.7.

## Overview

![Figure 1: framework overview](docs/figures/figure1.png)

The workflow consists of rule retrieval and curation, calculator synthesis and validation, parameter extraction, and deterministic tool execution. The repository includes 55 calculator tools, calculator-specific schemas, and three same-calculator demonstrations per extraction task.

![Figure 2: prompts for rule curation, tool synthesis, and parameter extraction](docs/figures/figure2.png)

The three prompt templates are implemented in [prompts.py](src/toolmed_agent/prompts.py). See [Prompt templates](docs/PROMPTS.md) for their inputs and runtime entry points.

## Installation

Use Python 3.10 or later. Local LLM inference requires Linux, CUDA, and an NVIDIA GPU; calculator execution and repository tests also run on CPU.

```bash
git clone https://github.com/benjiesun/tool-augmented-medical-calculation.git
cd tool-augmented-medical-calculation
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pip install -e .
```

On Windows PowerShell, activate the environment with `.\.venv\Scripts\Activate.ps1`.

For local model inference and embedding-based retrieval, also install:

```bash
python -m pip install -e ".[local,retrieval]"
```

## Data and model preparation

Download the benchmark and prepare the demonstration library:

```bash
python src/download_data.py
```

The script downloads MedCalc-Bench Verified v1.0.7, verifies file checksums, and prepares three training demonstrations for each calculator. See [Data](data/README.md) for the generated files.

Configure model paths and API endpoints in `runtime.env`:

```bash
cp data/runtime.env.example runtime.env
```

For the paper's extraction setup, set `EXTRACTION_MODEL_PATH` to Qwen3-8B and `EXTRACTION_SFT_LORA_PATH` to its extraction LoRA adapter. **The trained adapter is not included in this release.** The calculators can be used independently of the extraction model. Model requirements and training settings are listed in the [reproduction guide](docs/REPRODUCTION.md).

## Usage

### Run a calculator

```bash
python src/run_calculator.py --input data/examples/mean_arterial_pressure/input.json
```

The example supplies systolic/diastolic pressures of 120/80 mmHg and returns a mean arterial pressure of approximately 93.33 mmHg. See [examples](data/examples/README.md) for the input and output formats.

### Run the extraction and calculation pipeline

After configuring the central and extraction models:

```bash
toolmed-run --root-dir . --env-file runtime.env --limit 1
```

Use `--limit 0` to process the full test set. Outputs are saved under `output/`, `result/`, and `judge/`.

### Evaluate the released calculators

```bash
python src/evaluate_calculators.py
```

This evaluates calculator execution using ground-truth input parameters. End-to-end evaluation additionally runs parameter extraction. Metric definitions and answer handling are described in [Evaluation](docs/EVALUATION.md).

### Run tests

```bash
python src/validate_artifacts.py
python -m unittest discover -s tests -v
```

These checks require neither a GPU nor model API access. For tool generation and ablations, see the [reproduction guide](docs/REPRODUCTION.md#tool-generation).

## Repository structure

| Directory | Contents |
|---|---|
| `src/` | Data preparation and execution scripts; core package in `toolmed_agent/` |
| `artifacts/` | 55 calculators, checksums, and rule metadata |
| `data/` | Schemas, demonstration metadata, configuration template, and examples |
| `docs/` | Figures, Chinese README, reproduction guide, and technical notes |
| `tests/` | CPU regression tests |
| `.github/` | Automated Windows/Linux checks |

## Citation

If you use this code in your research, please cite:

```bibtex
@unpublished{zhong2026toolaugmented,
  title = {Tool-Augmented Large Language Models for Reliable Medical Calculation from Patient Notes},
  author = {Zhong, Yang and Luo, Ling and Zhu, Xuanlyu and Wang, Yanhua and Sun, Yuanyuan and Wang, Jian and Lin, Hongfei},
  year = {2026},
  note = {Manuscript},
  url = {https://github.com/benjiesun/tool-augmented-medical-calculation}
}
```

## License

Project code is released under [Apache License 2.0](LICENSE), except the benchmark-derived evaluator and data artifacts, which are covered by CC BY-SA 4.0. See [licensing notes](docs/NOTICE.md) for attribution and licensing details.

For research use only; not validated for clinical use. Review and isolate generated code before execution; see [execution notes](docs/NOTICE.md#safe-execution).
