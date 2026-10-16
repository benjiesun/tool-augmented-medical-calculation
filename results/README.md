# Reported result and evaluation notes

The final manuscript reports **86.73% final-answer accuracy** on MedCalc-Bench
Verified v1.0.7 (55 calculators, 1,100 test cases). This is a paper-reported
value, not a new model run performed while preparing the repository.

This repository is for reproducing the method. It does not distribute
historical per-case extractions, complete LLM responses, request transcripts,
or run logs. New local runs write to ignored output directories.

The existing small CSVs retain historical aggregate reference values only:
`main_results.csv`, `tool_quality.csv`, `extractor_results.csv`, and
`ablations.csv`. External baseline rows are contextual published values,
not controlled reruns. The PMR columns use the defective historical matcher
and are not validated results from current code. Do not use them to claim a
corrected PMR or to regenerate the paper's error attribution.

[KNOWN_ISSUES.md](KNOWN_ISSUES.md) explains the corrected parameter matcher,
the local final-answer adapter, and the Case C manuscript typo.
[submitted_run_manifest.json](submitted_run_manifest.json) records the
reported configuration; [final_manuscript_manifest.json](final_manuscript_manifest.json)
identifies the final source and author order. Neither file contains model
responses.

For data, model requirements, prompt templates, and execution commands, see
[the reproduction guide](../docs/REPRODUCTION.md).
