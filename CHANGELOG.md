# Changelog

Pennovia's package metadata currently identifies version **0.2.0 alpha**. Entries here describe merged repository work, not a claimed tagged GitHub release.

## Unreleased — 7 November 2026\n\n- Reject missing and blank provider responses and report malformed provider replies with bounded errors.

- Reuse one language-aware first-person pronoun measure across analysis, scoring and audit.\n\n- Make two-language detection abstain when uncertain; permit explicit English/Turkish overrides for analysis and pipeline commands.

### Behavior and data safety
- Require explicit CLI consent before replacing existing profiles or drafts ([#12](https://github.com/yoldaolmak/Pennovia/pull/12)).
- Reject ambiguous formats and duplicate WordPress exports ([#13](https://github.com/yoldaolmak/Pennovia/pull/13)).
- Preserve distinct local export files and clean temporary PDFs ([#7](https://github.com/yoldaolmak/Pennovia/pull/7)).
- Make corpus ingestion deterministic and CLI diagnostics accurate ([#9](https://github.com/yoldaolmak/Pennovia/pull/9)).

### Voice analysis and profile reliability
- Count complete transition expressions, not word fragments ([#5](https://github.com/yoldaolmak/Pennovia/pull/5)).
- Include short sentences and paragraphs in rhythm metrics ([#6](https://github.com/yoldaolmak/Pennovia/pull/6)).
- Align prompt instructions with Turkish/English usage and prohibit invented firsthand accounts ([#8](https://github.com/yoldaolmak/Pennovia/pull/8)).
- Validate portable voice-profile schema version 1 and legacy unversioned profiles ([#10](https://github.com/yoldaolmak/Pennovia/pull/10)).

### Security and maintainability
- Replace Codex CLI sandbox bypass with read-only execution and safe errors ([#4](https://github.com/yoldaolmak/Pennovia/pull/4)).
- Introduce Ruff checks and remove demo import-time filesystem side effects ([#11](https://github.com/yoldaolmak/Pennovia/pull/11)).

## Package baseline — 0.2.0 alpha
- Rebrand and consolidate the standalone Python package and CLI ([#3](https://github.com/yoldaolmak/Pennovia/pull/3)).
- Support local corpus statistics, portable JSON profiles, optional model-guided drafts, heuristic review, and explicit exports.

## Known limits
The voice similarity and audit scores are uncalibrated. The offline mock demo does not prove AI drafting quality. These changes do not establish writer identity, factual correctness, or independent security certification.
