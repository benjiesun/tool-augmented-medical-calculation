# Memory artifacts

The committed `mdcalc_rules_v1.jsonl` is a minimal public rule stub:

- 55 calculator identifiers and names;
- source URLs;
- required input-field names.

It does not contain captured MDCalc webpage text. Mutable runtime files such as
`web_rules.jsonl`, `case_memory.jsonl`, missing-parameter histories, generated
tool registries, and full traces are created locally and ignored by Git.
Runtime rule curation does not append model output to the committed stub.

This stub is sufficient to avoid an unexpected web-retrieval path when reusing the fixed calculator set. It is not sufficient to regenerate all tools from scratch; consult the original calculator sources and applicable terms before rebuilding.

When fresh on-demand generation is explicitly enabled, a stub is not treated
as retrieved formula evidence; the rule retrieval/curation path must run.
