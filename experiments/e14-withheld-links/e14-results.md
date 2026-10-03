# E14 results: a withheld-link marker

**2026-10-03.** Pre-registered (`fdcd6f1`). The vault exporter now withholds a
link whose target lies outside the export and is archived, confidential or
carries a banned term: the concept gets `links: [..., {withheld: n}]`, and the
target is named nowhere (no `to`, no `Related` line, and its wiki-links in body
text and descriptions become "a note withheld from this export"). Measured on
`psychology-kb` and `ai-concepts-kb`, before (the committed bundles) and after
re-export. Numbers in `before.jsonl` and `after.jsonl`; `measure.py` reuses the
exporter's own sensitivity rule.

| | psychology before | after | ai-concepts before | after |
|---|---|---|---|---|
| Sensitive targets the slice links to | 7 | 7 | 21 | 21 |
| **H1** generated text naming them | 248 | **0** | 70 | **0** |
| **H2** withheld markers / exporter's count | 0 | **96 / 96** | 0 | **27 / 27** |
| **H2** "does not resolve" warnings | 107 | **11** (−96) | 97 | **70** (−27) |
| **H3** Level 3, stdlib and PyYAML | pass | pass | pass | pass |
| **H4** canonical | 102 / 102 | 102 / 102 | 63 / 63 | 63 / 63 |

**H5**: validator unit tests pass under both parsers (32 tests, 3 new): a
well-formed marker gives no finding and is counted in `--stats`
(`withheld_links`); `0`, a negative, a string, `true`, an extra key, or
`withheld` beside `rel`/`to` are errors.

**All five hypotheses pass**, so the marker goes into SPEC §6.1 (proposed for
v0.5).

**On the measure.** The first H1 measure counted titles anywhere, which counts
ordinary prose; the plan's clarification (recorded before the "after" run)
restricts it to what the exporter generated. Two further refinements, both
before the final numbers: ids and titles are matched as exact tokens (a link
`](./id.md)`, a label `[Title]`, a backticked id in `log.md`), because one
withheld note's id, `framing`, is an ordinary word that other notes' own
descriptions use, and another, `context-engineering`, is a substring of a clean
target's id.

**What it fixed.** The `samos` link target that started this is gone, and so are
247 other names of archived or BA-bearing notes that the exporter had been
writing into both bundles' frontmatter, Related sections and body text. The
psychology bundle's 96 withheld links are the six psychology notes the archive
classifier filed under `Archive/` because "Amos Tversky" matched `AMOS`, plus
Survivorship Bias; restoring them (a change to the classifier, left to the
author) would turn them back into ordinary links.
