# Calculator input and output example

This example invokes a released deterministic calculator with structured
parameters. It requires the installed package and a CPU, but no model, API
key, patient note, or downloaded benchmark.

From the repository root:

```bash
python scripts/run_calculator.py --input examples/mean_arterial_pressure/input.json
```

The [input](mean_arterial_pressure/input.json) contains calculator ID 5 and
systolic/diastolic pressures of 120/80 mmHg. The released tool returns an
average arterial pressure of 93.33333333333333 mmHg. The complete expected
response is in [output.json](mean_arterial_pressure/output.json).

To use another released calculator, supply its identifier and the field names
and units expected by that calculator in `relevant_entities`. The files in
`artifacts/calculators/gpt_5_5/` define those inputs. Missing fields or a missing
calculator produce an `error` in the response and a nonzero exit status.

This example demonstrates tool execution only. It does not run the SFT
extractor or reproduce an end-to-end benchmark accuracy.
