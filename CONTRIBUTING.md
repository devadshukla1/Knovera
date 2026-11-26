# Contributing to Knovera

## Getting started

Follow the [README](README.md#getting-started) to install dependencies and configure a local environment. Keep real credentials, document uploads, databases, and generated files out of commits.

## Proposing changes

1. Open an issue describing the problem or proposed behavior for substantial changes.
2. Create a focused branch from `main`.
3. Make the smallest change that addresses the issue; add tests for changed behavior where appropriate.
4. Run the relevant backend or frontend tests and the frontend build for UI changes.
5. Open a pull request describing the problem, implementation, verification, and any remaining limitations.

Use clear commit messages. Include screenshots for visible UI changes and migration/setup notes for schema or configuration changes. Update `.env.example` when introducing settings, without adding working credentials.

## Validation

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests
npm.cmd --prefix frontend test
npm.cmd --prefix frontend run build
```

Run focused tests during development. Some integration and ML tests need external services or model downloads; state exactly what you ran and any missing prerequisites in your pull request.

## Reporting bugs

Include reproduction steps, expected and actual behavior, operating system, Python/Node versions, and sanitized logs. Do not attach private documents or secrets. Follow [SECURITY.md](SECURITY.md) for security-sensitive reports.

## Licensing

This repository does not currently specify an open-source license. Resolve contribution and reuse permissions with the repository owner before submitting third-party code or assets.
