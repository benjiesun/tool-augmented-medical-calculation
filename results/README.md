# Results

The paper reports **86.73% final-answer accuracy** on MedCalc-Bench Verified v1.0.7, covering 55 calculators and 1,100 test cases.

| File | Contents |
|---|---|
| [main_results.csv](main_results.csv) | Main results and published reference baselines |
| [tool_quality.csv](tool_quality.csv) | Calculator accuracy with ground-truth parameters |
| [extractor_results.csv](extractor_results.csv) | Parameter-extraction results |
| [ablations.csv](ablations.csv) | Ablation results |
| [submitted_run_manifest.json](submitted_run_manifest.json) | Dataset, model, and evaluation configuration |

These tables contain paper-reported aggregates. External baseline rows are published reference values rather than controlled reruns. PMR values and their derived error groups use `legacy-nonzero-bool-v1`, whose numeric-matching defect is corrected in the current `numeric-safe-v2` implementation; corrected best-run PMR is unavailable. See [Evaluation](../docs/EVALUATION.md) for metric definitions and version differences.

For environment setup and experiment commands, see the [reproduction guide](../docs/REPRODUCTION.md).
