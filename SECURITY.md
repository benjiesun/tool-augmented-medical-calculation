# Security policy

## Secrets

Never commit `runtime.env`, API keys, tokens, model credentials, or private endpoint URLs. The repository ignores common secret-bearing files, but ignore rules are not a substitute for review.

Before every push:

```bash
python scripts/validate_artifacts.py
git diff --cached
```

If a credential is ever staged or committed, revoke or rotate it immediately and remove it from all Git history before publishing.

## Generated-code execution

This project loads and executes Python calculator files. Treat newly generated tools as untrusted code:

- inspect the source before execution;
- run generation and validation in an isolated container or sandbox;
- do not expose the tool API directly to an untrusted network;
- use a low-privilege account without access to secrets or sensitive files.

The 55 files under `artifacts/calculators/gpt_5_5/` are the reviewed fixed artifact used by this repository, but they are still research software rather than clinically validated implementations.

## Reporting

The repository is public. Do not post credentials, patient information, or
exploit details in a public issue. Contact the repository owner privately;
use GitHub private vulnerability reporting if it is available. This document
does not imply that private reporting has been enabled.
