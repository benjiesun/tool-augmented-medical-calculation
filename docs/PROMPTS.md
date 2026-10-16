# Figure 2 and executable prompt templates

Figure 2 is explicitly a **condensed** prompt description. The repository
uses its instructions as the shared contract for the three main stages.
Actual requests additionally contain the calculator-specific inputs listed
in the figure, so they are not byte-for-byte copies of an image.

![Figure 2: prompt overview from the final manuscript](../assets/figure2.png)

The original figure is rendered from the unmodified final LaTeX source.
The source hash and rendering region are recorded in
[figure2.source.json](../assets/figure2.source.json).

## Source of truth in code

All three contracts are in [src/toolmed_agent/prompts.py](../src/toolmed_agent/prompts.py),
version `final-manuscript-figure2-v1`.

| Figure 2 panel | Shared builder | Runtime use |
|---|---|---|
| Rule curation | `build_rule_curation_messages` | Main pipeline rule curator; returns both rule specification and schema |
| Tool synthesis | `build_tool_synthesis_messages` | Standalone retrieval builder and on-demand tool writer |
| Parameter extraction | `build_extraction_prompt` | Schema-based extractor and its generic fallback request |

Rule curation requests the formula/scoring rule, inputs, conditions, boundary
cases, output contract, evidence, and schema including types, units, enums,
and nullable/default behavior. Both rule and schema are retained in local
memory for tool construction.

Tool synthesis receives the curated rules, specification-derived schema,
training examples, expected output type, and rule references. Its missing
input behavior is benchmark-specified, not an unconditional `N/A` instruction.
Numeric/text/Boolean/date/unit parsing and deterministic execution follow
the figure. The execution harness still rejects unsafe generated code.

Extraction receives required fields, output JSON schema, field specifications,
three same-calculator training demonstrations, question, and current note.
It preserves allowed source units, uses null for unsupported fields, false
for absent Boolean criteria, and negative enum values for explicit negative
evidence. There is no extra instruction to calculate mean arterial pressure
inside the extraction prompt or invent unsupported non-null values.

Clinical schemas and demonstration metadata are not LLM run outputs. The
downloader restores demonstration notes locally from the pinned training
data; no historical model response or full request transcript is committed.

## Scope

Figure 2 describes the full workflow. Validation feedback adds repair
instructions when a candidate fails. The intentionally no-web ablation,
optional unit-normalization stage, and optional prose formatter are separate
from these three main prompt panels.

This alignment changes the reusable prompt code, not the frozen 55 tools or
the manuscript. It is not a claim that an unrecorded historical request was
identical or that the revised templates have been rerun to reproduce 86.73%.
The final SFT adapter is still needed for complete reproduction.

`tests/test_prompts.py` checks that runtime entry points use the shared
contracts, specification schemas exist for all 55 released calculators,
extraction includes three examples, and tool validation samples training
data rather than test labels.
