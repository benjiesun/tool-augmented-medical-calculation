# Evaluation

## Dataset and metrics

Evaluation uses MedCalc-Bench Verified v1.0.7: 1,100 test cases across 55 calculators. The downloader verifies the test CSV SHA-256:

```text
91d222234a5a427de1127e864a199a51af9e709357352423c8a22857476e7abf
```

- **Final-answer accuracy:** fraction of test cases with a correct calculator output after answer conversion and benchmark scoring.
- **Tool accuracy:** final-answer accuracy with ground-truth input entities, isolating calculator execution from extraction.
- **Parameter match rate (PMR):** matched required parameters divided by all required parameters.

The optional central-model prose response is not scored; evaluation uses the deterministic calculator output.

## Final-answer protocol

Protocol identifier: `submitted-adapter-v1`.

In [evaluation.py](../src/toolmed_agent/evaluation.py), `extract_answer_for_scoring` converts tool outputs before `check_correctness` applies calculator-specific rules adapted from the [benchmark evaluator](https://github.com/nikhilk7153/MedCalc-Bench-Verified/blob/v1.0.7/evaluation/evaluate.py):

| Output type | Comparison |
|---|---|
| Date | Calendar-date equality using `%m/%d/%Y` |
| Gestational age, calculator 69 | Exact week/day pair |
| Integer score | Rounded predicted value equals the reference |
| Decimal value | Prediction falls within the row's inclusive lower/upper bounds |

The project answer adapter differs from the benchmark's [answer extraction](https://github.com/nikhilk7153/MedCalc-Bench-Verified/blob/v1.0.7/evaluation/run.py). In particular, a calculator-69 tuple such as `('14 weeks', '1 days')` is converted to `N/A` and scored incorrect. The benchmark comparison function can recognize the week/day pair when given that tuple's string representation directly. This adapter behavior affects the reported final-answer protocol and is covered by regression tests.

Date comparison accepts equivalent zero-padded and unpadded calendar dates on both Windows and Linux. ISO dates and two-digit years are outside this protocol.

`--legacy-evaluator` is accepted for CLI compatibility and does not select another scoring mode. The `legacy_evaluator` output field identifies the final-answer protocol only; parameter matching is versioned separately.

## Parameter matching

Matcher identifier: `numeric-safe-v2`.

Numeric fields are compared numerically with tolerance `max(1e-6, 0.001 * max(abs(gold), abs(prediction), 1))`. Boolean predictions do not substitute for numeric measurements. Boolean reference fields accept explicit Boolean values or numeric 0/1. Units and parameter dates are normalized before comparison.

The earlier `legacy-nonzero-bool-v1` matcher treated nonzero numeric values as `True`, which could incorrectly match values such as 47 and 87. The paper's 97.47% PMR and PMR-based error breakdown use that earlier matcher; they are not measurements from `numeric-safe-v2`. Corrected values require the corresponding complete raw predictions and are not available for the paper's best run. This PMR correction does not change final-answer scoring.

To evaluate parameters from a complete local prediction file:

```bash
python scripts/rescore_extractions.py --predictions output/run.steps.jsonl --output output/parameter_metrics.json
```

The script requires all 1,100 raw extractions and the pinned test CSV. It preserves recorded final-answer judgments while recomputing parameter metrics and diagnostic groups. Stored match counts alone are insufficient. A wrong final answer with matching parameters does not by itself distinguish tool-code errors from answer-conversion errors.

## Calculator 24 reference case

For row 1002 (note ID 2), the benchmark specifies oral hydrocortisone 162.935 mg converted to oral dexamethasone:

| Field | Value |
|---|---:|
| Benchmark reference | 6.11006 mg |
| Accepted interval | 5.80456–6.41556 mg |
| Released tool output | 4.88805 mg |

The released tool matches `hydrocortisone` as `cortisone` because of its substring-check ordering. Evaluation retains this tool for comparison with the paper's fixed artifact. The paper's Case C reference is printed as 6.029 mg; evaluation uses the benchmark value above. The printed value lies within the accepted interval, whereas the tool output does not.

## Commands

Run `python scripts/evaluate_calculators.py` for gold-input tool evaluation. Run `toolmed-run --root-dir . --env-file runtime.env --limit 0` for full-pipeline evaluation with configured models. Model requirements are described in the [reproduction guide](REPRODUCTION.md).
