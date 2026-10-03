---
type: Decision
title: Use PostgreSQL as the job queue
description: Jobs go through a Postgres table with SKIP LOCKED, not a broker.
status: stable
created: 2026-10-02
generated:
  by: human:tester
  at: 2026-10-02T21:48:49Z
sources:
  - id: design
    resource: https://example.com/adr-12
supersedes:
  - use-redis-as-the-job-queue.md
---

<!-- kx: Start with one italic line telling a reader with no context what this is and why it matters. -->

## Decision

## Why

## Alternatives considered

## Reversal conditions
<!-- kx: The specific signals that should reopen this decision. -->

## Consequences

Supersedes [Use Redis as the job queue](use-redis-as-the-job-queue.md).
