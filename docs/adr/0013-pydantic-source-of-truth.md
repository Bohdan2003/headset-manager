# ADR-0013: Pydantic is the source of truth for the protocol

- **Status:** Accepted
- **Date:** 2026-11-01
- **Related:** ADR-0006

## Context

Three programs speak the same protocol: server, dashboard and agent.

## Decision

Describe the protocol in `server/src/headset_server/protocol.py`. Generate dashboard types from it (`openapi-typescript`, `json-schema-to-typescript`). The agent repeats the same JSON with kotlinx.serialization.

## Consequences

- Order of a change: server → `export_schema` + `npm run gen:types` → dashboard and agent.
- **Checked by:** the CI step that runs `npm run gen:types` and fails on a difference. The JSON in the agent has no automatic check.

## Alternatives considered

Not recorded.
