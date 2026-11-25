# ADR-0012: React and Vite, not Next.js

- **Status:** Accepted
- **Date:** 2026-11-01
- **Related:** ADR-0011

## Context

We do not need SSR or API routes.

## Decision

Build the dashboard with React and Vite. FastAPI serves the build.

## Consequences

- One process, one port, no Node at the arena.
- **Checked by:** `test_serves_built_dashboard_without_hiding_api`.

## Alternatives considered

Next.js — rejected: we do not need SSR or API routes.
