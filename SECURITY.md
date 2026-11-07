# Security

Pennovia 0.2.x is an alpha release. Security fixes target `main`; older versions have no guaranteed support window.

**Report vulnerabilities privately** through GitHub's private vulnerability reporting, if enabled, or contact the maintainer through their GitHub profile. Do not post exploits, credentials or private writing in public issues.

## Local Studio

`pennovia studio` binds to **127.0.0.1**. Host and Origin checks, a session token, Content Security Policy and request-size limits reduce exposure. Do not expose Studio through tunnels, port forwarding or public proxies. Browser drafts and profiles are not persisted automatically.

Studio creates WordPress **drafts only**. Publishing requires explicit `--publish` in the CLI or `publish=True` in the Python API.

## Data and network

- Local files and pasted text are analyzed locally. Selected HTTPS URLs are fetched from their sites (2 MB response limit, basic local-address rejection). URL reading is **not** an isolation sandbox for hostile sources.
- Voice profiles may store source sentences verbatim. Keep profile JSON private.
- Cloud generation sends selected profile excerpts and prompts to the chosen provider. Never put API keys in browser fields or committed files.
- WordPress and Google Drive connect only on explicit export. WordPress requires canonical HTTPS, verifies TLS and rejects redirects.
- Local exports use distinct filenames. CLI profiles/drafts use restricted file permissions where supported and atomic replacement when overwrite is explicit; they are **not encrypted**.
- Codex CLI runs in a read-only sandbox. This does not eliminate prompt-injection risks in source material.

Pennovia does not automatically load `.env` files. Supply credentials through environment variables or a secret manager.

Security checks are not an independent security certification.
