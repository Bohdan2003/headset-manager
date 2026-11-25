# ADR-0024: Where to keep the agent signing key

- **Status:** Proposed
- **Date:** postponed by the user, date not recorded
- **Related:** T-008

## Context

Today the agent is signed with the debug key `~/.android/debug.keystore` on the Mac. If this key is lost, installed agents can't be updated: only removed and set up again by cable. GitHub has no signing key, so the agent is not rebuilt there.

## Decision

_Not decided. Must be decided before the pilot (T-004)._

## Consequences

_To be filled in T-008._

## Alternatives considered

_To be filled in T-008._
