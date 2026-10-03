# E13 plan: a canonical serialisation for AI-XF concepts

**Written 2026-10-03, before any run.** The pass criteria below are fixed by
this commit; results go in `e13-results.md` and may not change them. If a
criterion fails, the canonical form does not go into the spec as written.

## Why

E10 found that a database cannot regenerate a concept file from its stored
fields: re-serialising from parsed `jsonb` changed all 172 concepts (key order,
list style, quoting, comments), even though no value changed. Longview stays
byte-stable only through its own private writer conventions. Two systems that
store the same concept therefore cannot agree on a content hash, which is what
compare-and-set (E10's lost updates) and import-time change detection (E12's
re-import) both need.

The candidate rules are in [`CANONICAL.md`](./CANONICAL.md). This experiment
asks whether they are exact enough that independent implementations agree
byte for byte, and safe enough that nothing a reader sees changes.

## Hypotheses and pass criteria

| # | Hypothesis | Measure | Pass |
|---|---|---|---|
| H1 | Canonicalisation is **idempotent** | `canon(canon(x)) == canon(x)`, bytes, every concept | 100% |
| H2 | It **preserves meaning** | The YAML 1.2 core data model of `canon(x)` equals that of `x`, with numbers compared as JSON numbers; and the reference validator's findings for every bundle are identical before and after canonicalising, under both parsers | 100%, and identical findings |
| H3 | It is **exact enough to implement twice** | The Python and TypeScript implementations, written separately from `CANONICAL.md`, produce identical bytes | 100% |
| H4 | It **survives a database** (E10's failure) | Frontmatter stored as Postgres `jsonb`, read back, canonicalised, equals `canon(x)` byte for byte | 100% (E10 baseline: 0 of 172) |
| H5 | The **content hash** tracks meaning, not formatting | (a) Formatting-only variants of each concept (key order shuffled, flow or block lists, other quoting, comments added, CRLF, lists at column 0, long lines wrapped) give the same hash. (b) Single-value mutations (one scalar edited, one list item dropped, one key renamed) give a different hash | (a) 100% same, (b) 100% different |
| H6 | It **reads the same in YAML 1.1** | PyYAML's default loader (YAML 1.1) reads every non-timestamp value of `canon(x)` as the same type and value as the YAML 1.2 model does | 100% |

**Diagnostic, no pass mark:** for each producer (hand-written `examples/`, the
fixtures, the vault exporter's two bundles, Longview's export when Docker is
available), the share of concepts that are already canonical. This says how far
each producer is from the form, not whether the form works.

**Amendment, 2026-10-03, before any run.** Numbers compare as JSON numbers in
H2, which would hide one real change: a float with no fractional part (`1.0`)
is written as an integer (`1`), so a YAML 1.1 or Python reader sees its type
change. H2 now also fails if any such float exists in the corpus; the run
reports each one. This only makes H2 stricter.

## Corpus

Every concept file in: `examples/`, `experiments/fixtures/data-eng` and
`household`, the E2 bundles, `~/Documents/GitHub/psychology-kb` and
`ai-concepts-kb` (copied, read-only), and the E9 KnowledgeX notebook (saved as
`fixtures/knowledgex/`, so no third-party package is downloaded and run). H4 and the Longview
diagnostic need Docker and are skipped, with a note, without it.

## Procedure

1. `run.sh` assembles the corpus in a temp directory.
2. `canon.py` (Python, PyYAML with the YAML 1.1 resolvers replaced by YAML 1.2
   core ones) and `canon.ts` (TypeScript, the `yaml` package, core schema)
   canonicalise every file into separate output trees.
3. `measure.py` computes H1–H6 and the diagnostic, and writes `results.json`.

## What happens next

- **All pass:** propose the canonical form and the `sha256:` content hash for
  AI-XF v0.5 (a SHOULD for producers that regenerate files and for any system
  that stores concepts as fields), with `CANONICAL.md` as the normative text.
- **H3 fails:** the rules are not exact enough; tighten `CANONICAL.md` and
  re-run as E13b, recording the failure here.
- **H2 or H6 fails:** the form changes meaning; it must not ship.
