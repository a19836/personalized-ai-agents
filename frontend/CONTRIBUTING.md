# Contributing (Frontend)

Thanks for contributing to the frontend UI.

## Setup

```bash
cd frontend
npm install
```

For full project setup (including backend services and environment variables), see the root `README.md`.

## Run locally

```bash
npm run dev
```

The app expects backend services configured via `VITE_*` API base URL env vars.

## Build

```bash
npm run build
npm run preview
```

## What to keep in mind

- Keep changes focused and easy to review.
- Follow the existing React patterns used in `src/modules`.
- Update related docs when UI flows or configuration change.
- For UI behavior changes, include screenshots in the PR.

## Pull requests

Please include:

- what changed and why
- relevant issue reference (if any)
- confirmation that frontend build succeeds (`npm run build`)
