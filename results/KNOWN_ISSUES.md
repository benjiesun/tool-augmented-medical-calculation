# Known evaluator issue

## Calculator 69 duration parsing

The evaluator used for the submitted tables did not recognize a valid duration emitted as a Python-like list such as:

```text
['14 weeks', '1 days']
```

The fixed GPT-5.5 tool produced numerically correct week/day values for all 20 calculator-69 test cases, but the legacy parser converted all of them to `N/A`. This affected every archived main extractor run.

The evaluator in this repository accepts list, tuple, and string duration formats and is the default. Set `LEGACY_EVALUATOR=1` only when reproducing the submitted parsing behavior.

For the submitted best run, applying only this confirmed parser correction to the archived outputs changes 954/1,100 to 974/1,100 (86.73% to 88.55%). This post-submission audit value is **not** presented as the submitted-paper result and should not replace the paper table until the full evaluation is rerun and the authors decide how to report the correction.

## Portable date comparison

The legacy date evaluator used the POSIX-only `strftime("%-m/%-d/%Y")` directive. The current implementation compares parsed date components and therefore works on Windows as well as Linux.
