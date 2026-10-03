# E14 plan: a withheld-link marker

**Written 2026-10-03, before any run.** Pass criteria fixed by this commit.

## Why

Two experiments asked for the same missing piece. E11 (migration) had to replace
links to a read-restricted Confluence page with prose. The archive discussion
after E8 found that 26 of 27 archived notes the vault bundles link to contain BA
terms, and that a link **target** can leak on its own: `ai-concepts-kb` holds
`to: 2026-03-18-samos-data-migration-and-integration-analysis`, a BA system name,
because the exporter's BA gate scans note text and not the link targets it writes.

AI-XF can already say "N sources were withheld" (§7.5) without naming them. It
cannot say the same of links, so a producer must either name the target (a leak)
or drop the link silently (a list that is shorter than it looks).

## The proposal under test

A `links` entry MAY instead be a **withheld marker**: the single key `withheld`
with a positive integer, the number of links removed from this concept for a
reader who may not see them. It names nothing. It has no `rel`, no `to`, no body
mirror. The same shape as §7.5's source marker.

The vault exporter withholds a link when its target is a vault note that is
under `Archive/` or `Confidential/`, or whose own text contains a banned term,
and the target is outside the export.

## Hypotheses and pass criteria

| # | Hypothesis | Measure | Pass |
|---|---|---|---|
| H1 | Nothing withheld is named | Across every file of the re-exported `psychology-kb` and `ai-concepts-kb` (concepts, index, log, manifest): occurrences of any withheld target's id or title, and of any banned term, in link targets, `Related` labels or anywhere else the exporter generated | 0 (before: at least 1, the `samos` target) |
| H2 | The counts add up | Sum of `withheld` markers equals the number of links the exporter reports withholding; the validator's "does not resolve" warnings fall by exactly that number | exact |
| H3 | Conformance holds | Both bundles PASS Level 3 under both parsers; Level 0 (OKF) unaffected | yes |
| H4 | Canonical form holds | `ai-xf-canon.py check` on both bundles | 100% canonical |
| H5 | The validator reads the marker correctly | Unit tests: a well-formed marker gives no finding and is counted in `--stats`; `0`, a negative, a string, an extra key, or `withheld` beside `rel`/`to` are errors; both parsers agree | all pass |

If any criterion fails, the marker does not go into the spec.

**Clarification, 2026-10-03, after measuring "before", before measuring "after".**
H1's first measure counted a withheld note's title anywhere in a file, which
counts ordinary prose: titles such as "Framing" or "Event-Driven Architecture"
are common words the notes use themselves. As the H1 row says, what counts is
what the exporter generated. A leak is therefore: the target's id as a link
`to`; its id or title in a `Related` line; or more mentions of its title in an
exported concept than its source note has outside wiki-links to it. Both
"before" and "after" are measured this way.

