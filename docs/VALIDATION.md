# Validation limits

Pennovia measures **selected features of writing style**. Scores are uncalibrated; they do not verify authorship, lived experience or factual accuracy.

## What is tested

- Corpus reading, English/Turkish analysis, profile JSON compatibility, scoring and exports.
- Synthetic end-to-end CLI and Studio flows: analysis → model-shaped response → review → TXT/HTML/PDF and simulated WordPress draft.
- Errors such as blank provider replies and unusable inputs.

Tests use synthetic provider responses. They **do not** verify live model connectivity, WordPress publication, writing quality or fidelity to a real author's style.

## How to interpret a score

Audit PASS requires **70/100 and at least 200 words**. It compares sentence rhythm, first-person rate, questions, transitions, paragraph structure and common AI clichés. Different writers can receive similar scores.

Turkish negation detection covers only listed forms, not every inflected verb. Vocabulary richness uses 500-token windows; recurring phrases do not cross document boundaries. These are descriptive signals, not identity tests.

## Editorial review

Compare the draft with the source writing. Check rhythm, point of view and recurring expressions. Verify facts, quotes and claimed experiences separately.

Pennovia guides drafts; it does **not** identify authors or guarantee voice fidelity. A large authorship-identification benchmark is outside the product's current scope.
