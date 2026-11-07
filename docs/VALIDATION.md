# Voice review: validation and limitations

Pennovia computes **uncalibrated style heuristics**, not an author-identification model. A numerical score is a description of selected surface features, not a probability that a particular person wrote the text.

## Synthetic end-to-end pipeline check

`tests/test_cli_synthetic_pipeline.py` drives the actual `pennovia run` command through bundled corpus ingestion, author profiling, OpenRouter response parsing, heuristic audit and local HTML/TXT/PDF exports. A second case checks a WordPress draft response, and a third checks that empty model output blocks export. Provider and WordPress HTTP responses are simulated; no API keys or network services are needed.

This verifies software integration, **not** live model connectivity, writing quality, voice fidelity or real WordPress publication. A successful CI run does not establish those capabilities.

## What automated tests establish

The offline suite checks supported English/Turkish token behavior, profile portability, shared first-person semantics, and deliberately different **synthetic writing styles**. Synthetic contrast tests assert only that obvious differences in sentence rhythm, personal pronouns and transition expressions influence score ordering. They do **not** establish real-world author-discrimination accuracy.

The audit requires at least **200 whitespace-delimited words** and a heuristic score of at least 70 to display PASS. That minimum is a conservative software guard, not a scientific sample-size threshold. Warnings such as missing transitions only apply when the source profile has enough observed transitions to make the comparison meaningful.

## What the model cannot establish

- Whether two writers with similar sentence lengths and pronoun rates are actually different people.
- Whether model-generated travel memories and quotations are genuine.
- Whether an individual author's voice remains stable between topics, dates and formats.
- Whether an input corpus contains multiple authors or pasted text from other sources.
- Whether a high similarity number predicts the quality or originality of a draft.

Negative-construction frequency uses a conservative set of whole Turkish word forms and English negation expressions; one sentence contributes at most one match. It does not infer suffix-based Turkish verb negation, and existing profiles should be regenerated for the corrected metric.

The corpus analyzer calculates vocabulary richness from fixed 500-token windows with a final tail-covering window. It does not invent signature word pairs across separate source documents. These are descriptive metrics, not proof of a writer's identity.

The current scorer combines sentence-length similarity, first-person rate and observed transitions. Because it does not compare all lexical, syntactic or semantic properties, **unrelated writing can receive a high score** when those limited properties match.

## Practical editorial check

The product goal is **style-guided drafting**, not author identification. For a useful review, compare the draft with the source writing: sentence rhythm, point of view, characteristic transitions and paragraph structure. Check claims, first-person experiences and quotations separately; a high heuristic score cannot validate any of them.

Studio uses the same analyzer, generator, audit and scorer as the CLI, with a local HTTP wrapper. Its automated tests exercise source intake, a synthetic provider response, review and downloads. These checks verify software wiring, **not** the quality of any real model's output.

Do not market numeric style scores as verified voice fidelity, a probability of authorship, or a guarantee of publishable content. No large-scale author-identification benchmark is a prerequisite for this toolkit's intended use.
