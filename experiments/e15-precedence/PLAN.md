# E15 plan: one resolution order for every consumer

**Written 2026-10-04, before any run.** The hypotheses, pass marks and decision
rules below are fixed by the commit that adds this file, together with
`PROPOSED-RULE.md`, `INTERFACE.md`, `cases.json` and `fixtures/`.

## Why

A reader's comment on the AI-XF articles:

> The collision rule is where federation is actually decided. In the harness I
> use, the same name can exist repo-wide and scoped to a subdirectory, and the
> most specific one wins, which turns a collision into a feature instead of an
> error. Worth writing that precedence into the spec, otherwise two consumers
> resolve the same pair of bundles differently.

SPEC §9.2 already fixes the main order: the containing bundle first, silently,
then the other bundles alphabetically, always with a warning (tested in E2). But
reading the spec and the validator against the comment found five places where
two consumers that both follow the text could still resolve the same reference
differently:

1. **Aliases against other bundles.** §11.1 orders id, path, alias; §9.2 orders
   the own bundle before the others. Neither says how the two interleave: does
   the own bundle's alias beat another bundle's live id?
2. **Aliases in other bundles.** Whether an unqualified reference may resolve
   through another bundle's `aliases` at all is unstated. The validator never
   tries it.
3. **"Alphabetical"** is undefined. Probe, 2026-10-04: Postgres 17's default
   collation (`en_US.utf8`) sorts `teama` before `team-b` and `abb` before
   `ab-c`; byte order, Python, bun and macOS `sort` sort them the other way. A
   database-backed consumer using `ORDER BY namespace` picks a different winner
   from the validator.
4. **Nested bundles** are not covered: the comment's "scoped to a
   subdirectory". Probe, 2026-10-04: a bundle with a second bundle nested in a
   subdirectory, both defining `glossary`, fails Level 1 with a duplicate-id
   error, because the validator reads every file under the outer root as the
   outer bundle's.
5. **Paths and qualified references look alike.** §6.1 allows a bundle-relative
   path as `to`; §9.2 reads `namespace/id`. The validator reads
   `concepts/home` (a path without `.md`) as namespace `concepts`, id `home`.

The comment also suggests that a collision can be a feature: a more specific
definition deliberately overriding a general one. Between bundles owned by
different teams, a silent override is what E2 exists to prevent, so this plan
keeps cross-bundle resolution loud. It tests an explicit form of the comment's
idea instead: an optional `precedence` list in the federation manifest, which a
consumer declares and a reviewer can see, replacing byte order.

## The proposal under test

`PROPOSED-RULE.md`, in full: nested bundles are separate bundles; a `to` value is
classified by its text alone; federation order is the declared `precedence`,
then UTF-8 byte order; an id resolves own id → own alias → other bundles' ids →
other bundles' aliases → broken, with steps 3 and 4 never silent.

## Cases

`cases.json`: 25 references across four fixture federations
(`make_fixtures.py`), 10 of them on the five gaps and 15 controls, each with its
expected outcome written by hand from `PROPOSED-RULE.md` before any resolver ran,
in the form `INTERFACE.md` defines. `intent` records what the fixture's author
meant each reference to reach, `null` where no single intent exists.

## Method

Three resolutions of every case are compared:

- **(a) Expected**, by hand, in `cases.json` (committed now).
- **(b) The reference validator**, changed to implement `PROPOSED-RULE.md`, with
  a `--resolve` option printing the `INTERFACE.md` JSON. Link checking and
  `--resolve` call the same function.
- **(c) An independent resolver**, in TypeScript under bun, written by a fresh
  agent that receives only `PROPOSED-RULE.md`, `INTERFACE.md`, `fixtures/` and
  `cases-input.json` (no expected outcomes), in a directory outside this
  repository, and is told not to read anything else. It may use `Bun.YAML`.

**Before**, for the record and with no pass mark: the current validator's
behaviour on every case, read from its findings on a probe concept carrying the
case's link.

## Hypotheses and pass criteria

| # | Hypothesis | Measure | Pass |
|---|---|---|---|
| H1 | The rule text is determinate | (a), (b) and (c) agree on every field of every case | 25 / 25 |
| H2 | Cross-bundle resolution stays loud | Cases where an `id` reference resolves outside the containing bundle and `warning` is false, in (b) and (c) | 0 |
| H3 | No regression | E2's suite passes under both parsers; `examples/` passes Level 3 with 0 findings and E2's baseline file is unchanged; validator findings identical before and after on `examples/`, both `fixtures/` bundles, E2's three bundles with their federation, and `psychology-kb` and `ai-concepts-kb` where present | all |
| H4 | Nesting is a boundary | `fixtures/f4/outer` passes Level 2 on its own; `outer/team` passes; no duplicate-id finding | yes |
| H5 | Both parsers agree | Validator JSON for every fixture bundle, and `--resolve` for every case, identical under the stdlib parser and PyYAML | all |

## Decision rules

- **All of H1–H5 pass:** the rule goes into SPEC §9.2, §9.5 (`precedence`) and
  §11.1 in the next release, with a §13 entry, and the validator change ships.
- **H1 fails:** each disagreement is recorded with the clause that caused it, the
  text is revised, and the revision is tested as E15b under a new
  pre-registration. Nothing enters the spec until a run passes.
- **Step 4 (aliases in other bundles)** stays in the rule only if, run with it,
  no case with a non-null `intent` resolves to a concept other than its intent,
  and at least one such case resolves to its intent that would not without step
  4. Otherwise step 4 is removed and that variant is what is proposed.
- **H2, H3, H4 or H5 fails:** the failing part is fixed or withdrawn before
  anything enters the spec, and the result is recorded either way.

## Limits, stated in advance

The fixtures and their intents are mine, written to exercise the gaps, so H1
measures whether the text is precise, not whether the order is the one teams
would choose. One independent implementer is a small sample. The comment's
harness, where the same name lives repo-wide and in a subdirectory, maps to a
nested bundle (f4) only loosely: a harness has one author, a federation has many.

**Amendment, 2026-10-04, after the independent resolver started and before any
result was compared.** Case c21's `from_concept` named `concepts/glossary.md`,
which bundle `zed` does not have; its only concept is `concepts/reader.md`. c21
is an `id` reference, so the containing concept does not affect its outcome; the
input is corrected in `cases.json`, `cases-input.json` and the independent
resolver's copy. Expected outcomes are unchanged.

**Amendment 2, 2026-10-04, before any result was compared.** The independent
resolver reported that three fixture concepts are not valid YAML: their
unquoted `description` contained `": "`. Checking every fixture file with PyYAML
then found the same fault in all eight bundle manifests. The validator's built-in
fallback parser accepted all of them, which is why the fixtures passed when they
were written; PyYAML rejects them. The generator now quotes any value that is not
safe as a plain scalar, and every fixture file parses under PyYAML and passes
Level 2 under both parsers. Cases and expected outcomes are unchanged. The
independent resolver is re-run, without any change to its code, on the corrected
fixtures. Its first run, on the faulty fixtures, is kept as `results-indep-run1.json`
and its notes as written. The fallback parser accepting invalid YAML is a
validator defect in its own right, recorded in the results, outside H1–H5.
