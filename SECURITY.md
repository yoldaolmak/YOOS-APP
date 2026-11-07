# Security policy

Pennovia 0.2.x is an alpha release. Security corrections target the active main branch; older releases have no guaranteed support window.

## Disclosure

Use the repository's private GitHub vulnerability-reporting feature if enabled. Otherwise contact the maintainer privately using the repository owner's GitHub profile. Do not put exploit details, credentials, or private writing in public issues.

## Data boundaries

- Analysis is local, but profiles can retain verbatim corpus excerpts and generated drafts can contain input-derived material.
- Configured cloud model generation sends prompt text, including representative source sentences, to that provider.
- Google Drive and WordPress exports make network requests only when invoked.
- WordPress export requires HTTPS with certificate verification enabled and defaults to a draft. The REST request does not follow HTTP redirects or accept malformed success responses; configure the canonical HTTPS base URL.
- Keys come from environment variables. Do not commit them or private generated files.
- The offline demo uses labeled mock output when no API key is configured.
- Local exports are written to unique files rather than overwriting earlier exports. New voice profiles and CLI drafts use owner-only file permissions where supported; explicit replacements are written to a temporary file in the same directory, then atomically replaced. This does not encrypt files. Generated temporary PDFs are cleaned up on failure or after Google Drive upload preparation.

- The opt-in Codex CLI backend invokes `codex exec` with an explicit read-only sandbox, never with approval or sandbox bypass flags. This limits write operations but does not make untrusted corpus instructions harmless; run with a least-privilege local account and avoid exposing secrets to the model process.
- Local output files use filesystem permissions provided by the operating system; voice profiles are not encrypted at rest.

The `.env.example` file documents variable names but is not automatically loaded. Use a secret manager or your shell, not a public repository, to store credentials.

This policy is not a claim of a full independent security audit.
