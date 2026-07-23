# Memory artifacts

The committed `mdcalc_rules_v1.jsonl` is a minimal public rule stub:

- 55 calculator identifiers and names;
- source URLs;
- required input-field names.

It does not contain captured MDCalc webpage text. Mutable runtime files such as `case_memory.jsonl`, missing-parameter histories, generated tool registries, and full traces are created locally and ignored by Git.

This stub is sufficient to avoid an unexpected web-retrieval path when reusing the fixed calculator set. It is not sufficient to regenerate all tools from scratch; consult the original calculator sources and applicable terms before rebuilding.
