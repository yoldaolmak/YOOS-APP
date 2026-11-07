# Security policy

Pennovia 0.2.x is an alpha release. Security corrections target the active main branch; older releases have no guaranteed support window.

## Disclosure

Use the repository's private GitHub vulnerability-reporting feature if enabled. Otherwise contact the maintainer privately using the repository owner's GitHub profile. Do not put exploit details, credentials, or private writing in public issues.

## Data boundaries

- Analysis is local, but profiles can retain verbatim corpus excerpts and generated drafts can contain input-derived material.
- Configured cloud model generation sends prompt text, including representative source sentences, to that provider.
- Google Drive and WordPress exports make network requests only when invoked.
- WordPress export requires HTTPS with certificate verification enabled and defaults to a draft.
- Keys come from environment variables. Do not commit them or private generated files.
- The offline demo uses labeled mock output when no API key is configured.

This policy is not a claim of a full independent security audit.
