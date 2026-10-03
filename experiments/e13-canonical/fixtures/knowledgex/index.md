---
okf_version: "0.2"
---

# Decision

* [Use PostgreSQL as the job queue](use-postgresql-as-the-job-queue.md) - Jobs go through a Postgres table with SKIP LOCKED, not a broker.

# Lesson

* [Brokers add an operational dependency](brokers-add-an-operational-dependency.md) - Every broker is one more thing to page someone about.

# Concept

* [SKIP LOCKED](skip-locked.md) - Postgres row locking that lets workers skip claimed rows.

# Deprecated

* [Use Redis as the job queue](use-redis-as-the-job-queue.md) - Jobs go through Redis lists.
