# Aggregate results

This directory contains small, reviewable tables rather than per-case model traces.

- `main_results.csv`: the submitted manuscript's main comparison table.
- `tool_quality.csv`: tool-level and end-to-end results for tool-generation settings.
- `extractor_results.csv`: parameter matching and final accuracy across extraction models.
- `ablations.csv`: component ablations.
- `submitted_run_manifest.json`: dataset hash, fixed-tool checksum location,
  submitted configuration, and independently checkable tool-level expectations.

## Primary submitted configuration

| Metric | Value |
|---|---:|
| Test cases | 1,100 |
| Correct final calculations | 954 |
| Final accuracy | 86.73% |
| Matched parameters | 5,241 / 5,377 |
| Parameter matching rate | 97.47% |
| Tool-level accuracy | 94.91% |

These are the numbers in the anonymous submitted manuscript. Current code
retains the same project answer adapter and scoring protocol. The
post-submission calculator-69 parsing change has been withdrawn and does not
replace any submitted result; read [KNOWN_ISSUES.md](KNOWN_ISSUES.md) for the
relationship to the official benchmark evaluator.

## Baseline provenance

The first four rows of `main_results.csv` are contextual values transcribed
from the submitted manuscript, not reruns made with this repository. Their
evaluation sets and protocols are not identical, so they should not be treated
as a controlled head-to-head comparison.

| Row | Primary source | Scope recorded in the submitted manuscript |
|---|---|---|
| MedRaC / LLaMA3.1-8B | [EMNLP 2025 paper](https://aclanthology.org/2025.emnlp-main.548/) | External reported result on the authors' cleaned subset; not the full Verified v1.0.7 split |
| Open-book / GLM-4.6V and GLM-4.7 | [benchmark-audit preprint](https://arxiv.org/abs/2603.02222) | External reported values; the GLM-4.7 row is not a full 1,100-case evaluation |
| Code agent / Claude Sonnet 4.6 | [Anthropic system-card index](https://www.anthropic.com/system-cards) | External reported five-run mean on the verified benchmark |

The Qwen, tool-quality, extractor, and ablation rows are internal experimental
aggregates. They preserve the anonymous manuscript's tables. The complete
case-level outputs for the submitted best run and the extraction adapter were
absent from the source bundle, so only
the fixed-tool score can currently be independently rerun from this repository.

Full prompts, committed patient-note copies, API request identifiers, raw
outputs, and historical logs are deliberately excluded. The pinned downloader
can reconstruct the local, ignored few-shot notes from the licensed upstream
training file. Subject to the upstream data license and double-blind policy, a
per-case reproducibility archive can later be published as a versioned release
or archival dataset.
