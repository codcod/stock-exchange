---
id: EXC-021
title: Apply Event-Driven Architecture patterns (Cosmic Python Part II) to platform services
project: exchange
depends-on: []
spawned-by: []
impact: low-medium
complexity: medium-high
cost: M-L
---

# EXC-021 — Apply Event-Driven Architecture patterns (Cosmic Python Part II) to platform services

## Outcome

After this ships, `platform/base/domain` exposes an explicit `Command` vs `Event` distinction
(imperative single-recipient vs broadcast best-effort), and the project's existing outbox/relay
event delivery is documented and implemented against that vocabulary — so a new event consumer
can be added without editing the matching engine's `EVENT_DESTINATIONS` routing table.

## Description

`development/design.md` already implements a real outbox pattern (matching engine writes events
to a `outbox` table; a relay polls and delivers via HTTP; at-least-once, no consumer dedup) and
already separates write-side services (matching engine, OMS) from read-side projections
(`market_data`, `notifications`) — both are Event-Driven Architecture concepts from *Architecture
Patterns with Python* (Percival & Gregory), Part II, already present without being named as such.

What's currently conflated: every cross-service message (`submit_order`, `TradeExecuted`,
`AccountUpdated`, `OrderFilled`, ...) is informally called an "event," but two different
contracts are mixed together — imperative HTTP calls that expect a caller to react to failure
(Commands), and broadcast facts delivered via the outbox/relay that are tolerated as best-effort
(Events). Naming this split explicitly (a base `Command`/`Event` type in `platform/base/domain`)
would make failure-handling expectations visible at the type level instead of only in
`development/design.md` prose.

Candidate scope, from narrowest to broadest — refinement should pick how far to go, not assume
the widest option:

1. **Command/Event base types only** (`platform/base/domain`) — naming/documentation clarity,
   no behavior change. Lowest cost, lowest risk.
2. **+ Internal per-service message bus** — e.g. `OrderManagementService.submit_order()`'s
   sequential Risk → Clearing → Matching calls become bus-dispatched handlers, easing unit
   testing in isolation. Only worth it if that method's growing complexity justifies the added
   indirection.
3. **+ Replace the outbox-relay's polling+HTTP-POST transport with a real broker** (Redis
   Streams, per `development/design.md`'s own "What's intentionally simplified" note) — enables
   multi-consumer fan-out without touching the matching engine's routing table. Adds an
   operational dependency (`infra/docker/compose.infra.yml`).
4. **+ CQRS read-model split** for `order_management`'s `orders` table (today both write model
   and read model) — a dedicated read-only order-history projection built the same way
   `notifications` already projects account events. Adds sync/idempotency surface for a read-load
   problem this project doesn't currently have.

Given `development/design.md`'s own framing — "educational... not to build a production-grade,
high-performance system" — items 3 and 4 risk solving scale problems the project doesn't have.
Refinement should default toward item 1 (and 2 only if a concrete pain point justifies it)
unless the user wants the broader scope for its own pedagogical value.

## Implementation Plan

<!-- empty until refined; must meet the READY gate before moving to 2-ready/ -->

## Review

<!-- empty until IN REVIEW -->

## History

- 2026-09-19 — created (TO DO). source: chat: discussion of applying "Architecture Patterns
  with Python" (Percival & Gregory) Part II — Event-Driven Architecture — concepts to this
  project's existing outbox/relay and service-projection design.
