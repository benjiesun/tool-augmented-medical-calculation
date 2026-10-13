# Submitted evaluation protocol

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

This behavior is retained to reproduce the submitted evaluation. All reported
tables and generated calculator files remain unchanged. Any future evaluation
with a different answer adapter must be reported as a separate protocol and
applied consistently to all compared systems.

## Running the submitted evaluator

Both the main pipeline and `scripts/evaluate_calculators.py` use the submitted
adapter. The previous `--legacy-evaluator` script flag is accepted for command
compatibility and no longer selects a different evaluator. The previous
`LEGACY_EVALUATOR` environment variable is not used to switch parsing modes.
The `legacy_evaluator: true` summary field identifies the retained submitted
protocol.

The fixed-tool command measures calculator execution with ground-truth input
entities. It does not regenerate the 86.73% end-to-end SFT result; that requires
the submitted extraction adapter and full model run.

## Equivalent portable date comparison

The submitted date implementation used the POSIX-only
`strftime("%-m/%-d/%Y")`, which fails on Windows. The repository compares the
parsed calendar dates instead, while retaining the same `%m/%d/%Y` input
format. ISO dates and two-digit years are not newly accepted for final-answer
scoring. This changes platform compatibility, not the date matching criterion.
