# E15 results: one resolution order for every consumer

**2026-10-04.** Pre-registered in [`PLAN.md`](./PLAN.md) (`c7d3f0a`), with two
amendments committed before any result was compared (`2a35150`, `bee8d8c`).
Re-run with `run.sh`; the numbers are in `results.json`.

## Results

| # | Hypothesis | Result | Pass |
|---|---|---|---|
| H1 | The rule text is determinate | Expected, reference validator and independent resolver agree on **25 / 25** cases, on every field | **yes** |
| H2 | Cross-bundle resolution stays loud | 0 silent cross-bundle resolutions, in either resolver | **yes** |
| H3 | No regression | E2 suite passes under both parsers; `examples/` Level 3 clean; baseline unchanged; validator output identical before and after on all 8 corpus bundles (16 runs: `examples/`, both fixtures, E2's three, `psychology-kb`, `ai-concepts-kb`) | **yes** |
| H4 | Nesting is a boundary | `f4/outer` passes Level 2 alone under both parsers (before: duplicate-id error); `outer/team` passes; 0 duplicate-id findings | **yes** |
| H5 | Both parsers agree | `--resolve` identical on 25 / 25; corpus output identical | **yes** |

**Step 4 (aliases in other bundles) stays**, by the pre-registered rule: run
with it, 0 cases resolve against their intent, and one case (c05, a concept
renamed in another bundle) reaches its intended target only because of it.

## What changed in behaviour

7 of the 25 cases resolve differently from the validator before the change:

| Case | Before | After |
|---|---|---|
| c04, c05, c20 | broken link | resolved through another bundle's alias, with a warning |
| c16, c18 | byte order | declared `precedence` |
| c22, c23 | outer bundle fails: duplicate id `glossary` | nested team bundle is separate: `runbook` resolves to `team/runbook`, with a warning |

The validator already did what the rule says in the other gap cases (c02 own
alias first, c10 extensionless path, c11 ids before aliases, c21 byte order). The
gaps there were in the text, not the code: a second implementer had no way to
know.

## What the independent implementer found

The independent resolver was written by a fresh agent from `PROPOSED-RULE.md`,
`INTERFACE.md`, the fixtures and the case inputs only, in TypeScript under bun
([`independent/`](./independent/)). Its notes matter as much as its agreement:

- **My fixtures were invalid YAML.** Three concept descriptions, then (on
  checking) all eight bundle manifests, held an unquoted `": "`. The validator's
  built-in fallback parser accepted them; PyYAML and `Bun.YAML` reject them. The
  first run therefore disagreed on 4 cases (c09, c18, c19, c24), all traced to
  files it could not parse. The fixtures were corrected (amendment 2), and the
  same code, checked by hash, then agreed on 25 / 25. The run-one output is kept
  (`independent/results-indep-run1.json`).
- **Eleven judgement calls** where the text was silent (`independent/NOTES.md`).
  None changed a case. Three were written into the spec text afterwards: a path
  never leaves its bundle, no extension is added to a path, and a repeated
  `precedence` entry keeps its first place. Checking the validator against those
  and against the rule's existing `ai-xf://` clause found two differences, which
  were fixed and checked by four follow-up cases (`cases-followup.json`,
  `results-followup.json`; **not pre-registered**, all four agree):
  a path that climbs out of its bundle no longer resolves, and a malformed
  `ai-xf://` value is a broken qualified reference, not an id.

## A validator defect found on the way

The fallback YAML parser accepts a plain scalar containing `": "`, which YAML
forbids. On those files the two parsers disagree: the stdlib run passes, the
PyYAML run fails. That breaks the validator's own rule that both parsers produce
identical results, and E2's parser diff did not catch it because no bundle in
the repository had such a value. It is outside H1–H5 and not fixed here.

## Limits

The fixtures and their intents are mine, chosen to exercise the gaps. One
independent implementer is a small sample, and it was an AI agent, not a person.
The comment that prompted this describes a harness with one author; the nested
bundle case (f4) is the closest federation analogue, not the same thing.

## Decision

All five hypotheses pass, so by the plan the rule goes into SPEC §6.1, §9.1,
§9.2, §9.5 and §11.1 as proposed v0.6, and the validator change ships with it.
