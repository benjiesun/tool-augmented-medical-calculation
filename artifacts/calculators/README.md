# Calculator artifacts

`gpt_5_5/` contains the 55 calculator tools used for the main experiment. Each tool exposes:

```python
def calc(relevant):
    ...
```

`gpt_5_5/SHA256SUMS` pins every released calculator file. The repository
validator checks this manifest before a run. The artifact also completed a
1,100-case execution test with ground-truth input entities and zero runtime
errors.

Tool generation uses up to five candidates per calculator: an initial
candidate and up to four repairs. Each candidate is validated on the same
eight training examples. Selection statistics and source checksums are in
[generation_summary.json](gpt_5_5/generation_summary.json).

The `cycle1` suffix identifies the outer generation cycle, not the selected
inner repair round. Selected tools came from inner rounds 1 through 4. Of the
55 selected tools, 53 passed all eight training checks; IDs 24 and 33 retained
their best candidates without all checks passing. Benchmark evaluation
includes all 55 tools. See
[docs/REPRODUCTION.md](../../docs/REPRODUCTION.md) for full reproduction requirements.
