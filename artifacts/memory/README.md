# Memory artifacts

The committed `mdcalc_rules_v1.jsonl` is a minimal public rule stub:

- 55 calculator identifiers and names;
- source URLs;
- required input-field names.

It does not contain captured MDCalc webpage text. Mutable runtime files such as
`web_rules.jsonl`, `case_memory.jsonl`, missing-parameter histories, generated
tool registries, and full traces are created locally and ignored by Git.
The metadata supports offline reuse of the fixed calculator set. Generating
new tools requires formula evidence from the calculator sources.

On-demand generation retrieves and curates rule evidence before constructing
a tool. Retrieved rules are cached locally in `web_rules.jsonl`.
