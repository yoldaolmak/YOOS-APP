# Changelog

Version **0.2.0 alpha**. GitHub release details are recorded separately in [release notes](release/v0.2.0-alpha.md); the release must pass the live-model and CI gates.

## Post-release maintenance — 7 November 2026

- Refine README introduction and publish precise live Ollama results, including the neutral-control comparison.
- Validate all bounded profile rate fields and malformed Studio request options; correct the bundled demo's provenance labels. The tagged `v0.2.0` release remains unchanged.

## Unreleased — 7 November 2026

- Pin public DNS results for HTTPS article downloads to prevent redirect/DNS-rebinding requests to non-public IPs; ignore environment proxies for URL corpus ingestion.

- Add Pennovia Studio ([#30](https://github.com/yoldaolmak/Pennovia/pull/30)): one local browser screen for sample collection, voice profile, model-assisted draft, editorial review and manual exports. Studio uses the existing Python core/CLI capabilities, bundled static assets and the standard library server; no accounts, database or hosted platform.
- Align README, setup, Python API, architecture, contributor guidance, branding, security and validation documentation with the working Core / CLI / Studio boundaries; no code behavior change.

- Reject missing and blank provider responses and report malformed provider replies with bounded errors ([#17](https://github.com/yoldaolmak/Pennovia/pull/17)).

- Reuse one language-aware first-person pronoun measure across analysis, scoring and audit ([#16](https://github.com/yoldaolmak/Pennovia/pull/16)).

- Make two-language detection abstain when uncertain; permit explicit English/Turkish overrides for analysis and pipeline commands ([#15](https://github.com/yoldaolmak/Pennovia/pull/15)).

### Behavior and data safety
- Allow repeatable HTTPS article links and pasted text (including stdin) as voice-profile sources in the existing `analyze` and `run` CLI commands; keep the 51-word per-source floor.
- Refuse WordPress REST redirects, malformed success responses and ambiguous URL configuration; report bounded network errors.
- Write profiles and generated drafts with restrictive file permissions and atomic explicit replacement, retaining exclusive creation by default in the CLI.
- Require explicit CLI consent before replacing existing profiles or drafts ([#12](https://github.com/yoldaolmak/Pennovia/pull/12)).
- Reject ambiguous formats and duplicate WordPress exports ([#13](https://github.com/yoldaolmak/Pennovia/pull/13)).
- Preserve distinct local export files and clean temporary PDFs ([#7](https://github.com/yoldaolmak/Pennovia/pull/7)).
- Make corpus ingestion deterministic and CLI diagnostics accurate ([#9](https://github.com/yoldaolmak/Pennovia/pull/9)).

### Voice analysis and profile reliability
- Keep genre templates from demanding invented firsthand experience, unsupplied quotes or witnesses; prioritize observed author voice over genre tone.
- Select style-reference sentences across source documents rather than concentrating on the first file.
- Count one bounded negative-construction observation per sentence; prevent substring matches and use both language lists when detection abstains ([#21](https://github.com/yoldaolmak/Pennovia/pull/21)).
- Cover the complete corpus tail in vocabulary metrics and prevent cross-document signature phrases ([#20](https://github.com/yoldaolmak/Pennovia/pull/20)).
- Prevent short drafts from passing heuristic review despite high scores; avoid impossible transition warnings.
- Count complete transition expressions, not word fragments ([#5](https://github.com/yoldaolmak/Pennovia/pull/5)).
- Include short sentences and paragraphs in rhythm metrics ([#6](https://github.com/yoldaolmak/Pennovia/pull/6)).
- Align prompt instructions with Turkish/English usage and prohibit invented firsthand accounts ([#8](https://github.com/yoldaolmak/Pennovia/pull/8)).
- Validate portable voice-profile schema version 1 and legacy unversioned profiles ([#10](https://github.com/yoldaolmak/Pennovia/pull/10)).

### Security and maintainability
- Keep corpus-derived author labels, phrases and sample sentences out of model system instructions; treat them as untrusted user-message data.
- Verify the built wheel from a fresh environment outside the checkout, including bundled demo assets.
- Replace Codex CLI sandbox bypass with read-only execution and safe errors ([#4](https://github.com/yoldaolmak/Pennovia/pull/4)).
- Introduce Ruff checks and remove demo import-time filesystem side effects ([#11](https://github.com/yoldaolmak/Pennovia/pull/11)).

## Package baseline — 0.2.0 alpha
- Rebrand and consolidate the standalone Python package and CLI ([#3](https://github.com/yoldaolmak/Pennovia/pull/3)).
- Support local corpus statistics, portable JSON profiles, optional model-guided drafts, heuristic review, and explicit exports.

## Known limits
The voice similarity and audit scores are uncalibrated. The offline mock demo does not prove AI drafting quality. These changes do not establish writer identity, factual correctness, or independent security certification.
