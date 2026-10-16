# Evaluation protocols and manuscript errata

The final supplied LaTeX source is preserved as the manuscript of record for
this repository update. Keeping the paper unchanged does not make its known
measurement errors valid. Historical paper values and corrected-code results
are explicitly separated below.

## Confirmed parameter-matching defect

The historical `_scalar_match` tried Boolean conversion before numeric
comparison. `_to_bool` converted every nonzero number to `True`, so 47 and 87
matched, including `[47, "years"]` and `[87, "years"]`. This is a project
parameter-metric bug, not the benchmark's final-answer comparison rule.

Current parameter matching is versioned **`numeric-safe-v2`**. Numeric gold
annotations are compared numerically, not by truthiness; predicted Booleans
cannot stand in for numeric measurements. Boolean gold annotations accept
only explicit Boolean tokens or numeric 0/1. The existing numeric tolerance
(`max(1e-6, 0.001 * max(abs(gold), abs(prediction), 1))`), unit aliases, and
parameter-date normalization are otherwise retained.

Consequences for the unchanged manuscript:

- **97.47% (5,241/5,377) is a legacy reported PMR, not a corrected result.**
  Complete raw predictions for the 954/1,100 best run were not found, so its
  corrected PMR remains unavailable, not zero and not an estimate.
- PMR-based Figure 3, Figure 4, and the Figure 5 error attribution require
  recomputation from the respective raw predictions. The reported 80
  extraction / 66 generated-tool split is not revalidated. Those figures are
  not published here as corrected figures.
- All-parameters-matching cases with wrong final answers are a diagnostic
  group, not automatically proof of a generated-tool bug. The local answer
  adapter and benchmark output contract must also be inspected.

Run `scripts/rescore_extractions.py` with complete raw predictions and the
pinned test file to reproduce this audit. Judge-only files containing old
match counts cannot recover the original predictions.

## Unchanged final-answer protocol

The repository retains the submitted project's answer adapter and scoring
protocol. The submitted final accuracy remains 954/1,100 (86.73%), and the
fixed-tool accuracy remains 1,044/1,100 (94.91%). An earlier repository audit
introduced additional calculator-69 answer normalization; that change has been
withdrawn. It was a change to evaluation, not an improvement to the SFT
extractor or the generated calculators, and is not a replacement paper result.

## Relationship to the official benchmark

The project's `check_correctness` follows the calculator-specific scoring rules
in [MedCalc-Bench Verified v1.0.7](https://github.com/nikhilk7153/MedCalc-Bench-Verified/blob/v1.0.7/evaluation/evaluate.py):

- Dates: exact calendar-date match in the `%m/%d/%Y` format.
- Calculator 69: exact week/day pair match.
- Integer scores: round the predicted numeric value, then compare.
- Decimal outputs: use the test row's inclusive lower and upper limits.

The project's `extract_answer_for_scoring` is an additional answer adapter
before `check_correctness`. It is not an unchanged copy of the official
benchmark's [`extract_answer` in `run.py`](https://github.com/nikhilk7153/MedCalc-Bench-Verified/blob/v1.0.7/evaluation/run.py).

For example, the released calculator 69 emits a tuple like
`('14 weeks', '1 days')`. The submitted project adapter converts it to `N/A`,
so the final judgment is incorrect under the submitted protocol. The official
`check_correctness`, given the tuple's string representation directly, can
recognize the week/day pair. The parsing limitation therefore belongs to the
project's preceding adapter; it must not be attributed to the official
benchmark's week/day comparison rule.

This behavior is retained to reproduce the submitted final-answer evaluation.
The four historical CSV tables and all generated calculator files remain
unchanged; the parameter matcher is separately corrected and versioned.
Any future final-answer evaluation
with a different answer adapter must be reported as a separate protocol and
applied consistently to all compared systems.

## Running the submitted evaluator

Both the main pipeline and `scripts/evaluate_calculators.py` use the submitted
adapter. The previous `--legacy-evaluator` script flag is accepted for command
compatibility and no longer selects a different evaluator. The previous
`LEGACY_EVALUATOR` environment variable is not used to switch parsing modes.
The `legacy_evaluator: true` summary field identifies the retained submitted
**final-answer** protocol, not a request to use the defective PMR matcher.
New summaries additionally identify `final_answer_protocol: submitted-adapter-v1`
and `parameter_matcher_version: numeric-safe-v2`.

The fixed-tool command measures calculator execution with ground-truth input
entities. It does not regenerate the 86.73% end-to-end SFT result; that requires
the submitted extraction adapter and full model run.

## Equivalent portable date comparison

The submitted date implementation used the POSIX-only
`strftime("%-m/%-d/%Y")`, which fails on Windows. The repository compares the
parsed calendar dates instead, while retaining the same `%m/%d/%Y` input
format. ISO dates and two-digit years are not newly accepted for final-answer
scoring. This changes platform compatibility, not the date matching criterion.

## Case C: manuscript gold-answer typo

The final source's Table VII and accompanying Case C paragraph print
**6.029 mg**. In the pinned MedCalc-Bench Verified v1.0.7 test file (SHA-256
`91d222234a5a427de1127e864a199a51af9e709357352423c8a22857476e7abf`),
row **1002**, calculator **24**, note ID **2**, has:

| Item | Pinned benchmark value |
|---|---:|
| Oral hydrocortisone input | 162.935 mg |
| Oral dexamethasone gold answer | **6.11006 mg** |
| Lower / upper accepted limits | 5.80456 / 6.41556 mg |
| Frozen generated-tool result | 4.88805 mg |

The repository uses the actual dataset label, not the manuscript typo. The
frozen tool remains unchanged: its substring ordering mistakes
`hydrocortisone` for `cortisone`. A regression test preserves this observed
artifact behavior and checks that the result is outside the benchmark limits.
The manuscript's 6.029 happens to be inside those limits; correcting the
printed label alone does not establish a change to any aggregate final score.

## Authorship and source provenance

The ZIP's bundled `main.pdf` has six authors, whereas its current `main.tex`
has seven, adding **Xuanlyu Zhu** third. README and `CITATION.cff` follow
the seven-author source order. A fresh PDF was compiled from that source
without editing it; the stale bundled PDF was not used as the current paper.
Source hashes and scope are recorded in
[final_manuscript_manifest.json](final_manuscript_manifest.json).
