# Contributing (Backend)

Thanks for contributing to the backend services.

## Setup

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

For full installation, local service run commands, environment variables, and deployment details, see `backend/README.md`.

## Run tests

Use the backend test suite as the main validation step:

```bash
pytest -q tests
```

## What to keep in mind

- Keep changes small and focused.
- Update tests when behavior changes.
- Update docs when endpoints, env vars, or architecture change.
- Follow existing service/tool-handler patterns.

## Pull requests

Please include:

- what changed and why
- relevant issue reference (if any)
- confirmation that `pytest -q tests` passes
