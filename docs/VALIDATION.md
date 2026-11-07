# Voice review: validation and limitations

Pennovia computes **uncalibrated style heuristics**, not an author-identification model. A numerical score is a description of selected surface features, not a probability that a particular person wrote the text.

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

## Minimum evidence for future author comparison

With permission to use multiple authors' texts, divide material by **document** into training and held-out test sets. Do not test the same source text used to build the profile. Include within-author held-out positives, between-author negatives, hard negatives on the **same topic**, and a baseline that always chooses the most frequent author. Report results separately for Turkish and English, including corpus length, uncertainty, false matches and negative controls.

Until representative held-out corpora have been tested and results independently reviewed, do not market Pennovia's score as authorship verification, identity replication or a calibrated similarity probability.
