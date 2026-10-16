# Prompt templates

Figure 2 summarizes the instructions used for rule curation, tool synthesis, and parameter extraction. Shared templates are defined in [prompts.py](../src/toolmed_agent/prompts.py), with contract identifier `final-manuscript-figure2-v1`.

![Figure 2: prompt overview](figures/figure2.png)

## Runtime entry points

| Stage | Template builder | Runtime entry point |
|---|---|---|
| Rule curation | `build_rule_curation_messages` | `CentralHost._organize_web_rule_with_llm` in [pipeline.py](../src/toolmed_agent/pipeline.py) |
| Tool synthesis | `build_tool_synthesis_messages` | [Standalone builder](../src/toolmed_agent/tool_builder/prompts.py) and [on-demand writer](../src/toolmed_agent/tool_generation.py) |
| Parameter extraction | `build_extraction_prompt` | Schema-based and generic requests in [extraction.py](../src/toolmed_agent/extraction.py) |

## Rule curation

Inputs are the calculator name, question, retrieved evidence snippets, and source links. The model returns a rule specification and a calculator schema as JSON. The specification covers the formula or scoring rule, inputs, conditions, boundary cases, output format, and supporting evidence. The schema defines required fields, value types, units, categorical values, and nullable/default behavior.

## Tool synthesis

Inputs are the curated rule, schema, expected output type, training examples, and retrieved references. The model returns `required_entities` and Python source for `calc(relevant)`. The instructions cover scalar and structured inputs, number/text/Boolean/date/unit parsing, conditional branches, rounding, and benchmark-specific missing-input behavior. Tools must be deterministic and use no external dependencies.

Execution feedback is appended when a candidate fails validation. The validation set is reused across the repair rounds.

## Parameter extraction

Inputs are the calculator identifier and name, question, required fields, JSON schema, field specifications, three same-calculator training examples, and the patient note. The model returns a single JSON object containing the required parameters.

Measured values use `[value, unit]`, preserving allowed source units. Unsupported required fields use `null`; absent Boolean criteria use `false`; explicit negative evidence maps to the relevant negative categorical value.

## Scope and versions

Figure 2 shows condensed instructions; runtime requests also contain calculator-specific evidence and case inputs. The no-web ablation, optional unit normalization, and optional prose formatting have separate prompts.

The current templates implement the Figure 2 contract. The paper's reported accuracy comes from its experiment run; no end-to-end benchmark result is provided for this template revision. The released calculator files are versioned separately by their SHA-256 manifest.
