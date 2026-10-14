# Calculator artifacts

`gpt_5_5/` contains the 55 frozen calculator tools used for the submitted main experiment. Each tool exposes:

```python
def calc(relevant):
    ...
```

The directory intentionally excludes raw tool-generation prompts, responses, repair traces, failed ablation tool sets, and absolute-path registries.

`gpt_5_5/SHA256SUMS` pins every released calculator file. The repository
validator checks this manifest before a run. The artifact also completed a
1,100-case execution test with ground-truth input entities and zero runtime
errors.

The historical identifier `api_gpt-5-5_r5_s8_b1000000_260519_090713` denotes
five total generation rounds and eight validation examples. Archived records
confirm this profile, consistent with the latest manuscript's eight examples
and at most four repairs. The public aggregate and source checksums are in
[generation_summary.json](gpt_5_5/generation_summary.json).

The `cycle1` suffix identifies the outer generation cycle, not the selected
inner repair round. Selected tools came from inner rounds 1 through 4. Of the
55 selected tools, 53 passed all eight training checks; IDs 24 and 33 retained
their best candidates without all checks passing. The reported benchmark
evaluation includes all 55 and remains unchanged. See
[docs/REPRODUCTION.md](../../docs/REPRODUCTION.md) for full reproduction requirements.
