# Notices and third-party material

## Project code

Unless a file says otherwise, source code in this repository is licensed under
Apache License 2.0.

`src/toolmed_agent/evaluation.py` includes scoring semantics adapted from
MedCalc-Bench-Verified v1.0.7
(`evaluation/evaluate.py`). That file is marked and distributed under
CC BY-SA 4.0, with modifications for safe parsing, extraction metrics,
equivalent cross-platform date handling, and the submitted project's separate
answer adapter. The post-submission calculator-69 normalization has been
withdrawn; see `results/KNOWN_ISSUES.md`.

## MedCalc-Bench Verified

Files under `data/processed/` are adaptations of **MedCalc-Bench Verified v1.0.7**, published by its maintainers under the Creative Commons Attribution-ShareAlike 4.0 International license:

- Upstream repository: https://github.com/nikhilk7153/MedCalc-Bench-Verified
- Pinned release: https://github.com/nikhilk7153/MedCalc-Bench-Verified/releases/tag/v1.0.7
- License: https://creativecommons.org/licenses/by-sa/4.0/

Those dataset-derived files are not relicensed under Apache-2.0. Redistribution and adaptations must preserve attribution and comply with CC BY-SA 4.0.

## Calculator sources

`artifacts/memory/mdcalc_rules_v1.jsonl` contains only source URLs, calculator names, and short input-field stubs needed to prevent an offline fixed-tool run from scraping websites. It intentionally excludes captured webpage excerpts and tool-building prompts. Calculator source URLs point to MDCalc; use of the linked site remains governed by MDCalc's own terms.

## Models and external services

Model weights, LoRA adapters, proprietary model outputs, and API credentials are not distributed. Qwen, GLM, Llama, vLLM, and any API provider retain their respective licenses and terms.

## Figure

`assets/framework.svg` is an original, repository-specific schematic made from
generic text and geometric shapes. It contains no third-party logos, author
names, affiliations, or manuscript metadata.
