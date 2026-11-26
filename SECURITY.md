# Security

## Deployment scope

Knovera currently targets trusted local development. The authentication implementation permits local-owner fallback without a valid token. Do not expose this configuration as an authenticated multi-user service.

The Windows setup script uses PostgreSQL trust authentication and development credentials, and provisions a privileged application role. Public deployment requires enforced authentication/authorization, a least-privilege database role, strong secrets, restricted network access, and a deployment-specific security review.

## Handling sensitive data

- Keep API keys, database credentials, and signing secrets in untracked environment files.
- Never put secrets in browser-visible `VITE_*` settings.
- Keep uploaded documents, database dumps, and runtime storage outside Git.
- Review logs and screenshots before sharing them.
- Load serialized model artifacts only from trusted sources.

## Reporting a vulnerability

Use GitHub private vulnerability reporting from the repository's Security tab when available. Otherwise, ask the repository owner for a private reporting channel without including exploit details in a public issue. Never post working credentials, personal data, or private source documents publicly.

Include the affected revision, reproduction steps, impact, and a minimal sanitized example. No response-time or supported-release guarantee is currently established.
