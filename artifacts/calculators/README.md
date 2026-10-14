# Calculator artifacts

`gpt_5_5/` contains the 55 syntax-valid calculator tools used for the submitted main experiment. Each tool exposes:

```python
def calc(relevant):
    ...
```

The directory intentionally excludes raw tool-generation prompts, responses, repair traces, failed ablation tool sets, and absolute-path registries.

`gpt_5_5/SHA256SUMS` pins every released calculator file. The repository
validator checks this manifest before a run. The artifact also completed a
1,100-case execution test with ground-truth input entities and zero runtime
errors.

The historical work-log identifier for this set was
`api_gpt-5-5_r5_s8_b1000000_260519_090713`. Its naming convention denotes five
total generation rounds and eight validation examples, while the paper
describes up to five examples and four repairs. Five total rounds include an
initial generation and at most four repairs; only the example-count difference
requires confirmation against the selected generation records. See
[docs/REPRODUCTION.md](../../docs/REPRODUCTION.md) before claiming exact
from-scratch reproduction.
