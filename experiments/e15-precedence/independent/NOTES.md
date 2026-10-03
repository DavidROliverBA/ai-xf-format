# E15 independent implementation: ambiguities and judgement calls

## 1. Three fixture files have frontmatter that is not valid YAML (most important)

`fixtures/f1/alpha/concepts/common.md`, `fixtures/f1/alpha/concepts/home.md` and
`fixtures/f4/outer/team/concepts/glossary.md` each have a `description:` plain
scalar containing `": "` (e.g. `description: A path target: concepts/home.md.`).
In YAML that is "mapping values are not allowed here"; `Bun.YAML.parse` rejects it.

Clause: "A **concept** is a `.md` file in a bundle with YAML frontmatter holding `type`."
The rule is silent on unparseable frontmatter.

Choice: strict. A file whose frontmatter does not parse is not a concept (it has
no YAML frontmatter holding `type`). `results-indep.json` uses this reading.
Reason: it is the literal text, and the brief requires `Bun.YAML.parse`.

The fixtures' own descriptions suggest the author meant these files to be concepts,
so I added an opt-in lenient mode (`E15_LENIENT_YAML=1`) that quotes such values
and parses again. Only these cases change under it:

| case | strict (submitted) | lenient |
|---|---|---|
| c09 | path, broken, warning | `alpha/home` via path, silent |
| c18 | `beta/common`, candidates `[beta]` | `beta/common`, candidates `[beta, alpha]` |
| c19 | `beta/common`, candidates `[beta]` | `alpha/common`, candidates `[alpha, beta]` |
| c24 | `outer/glossary` via federation step 3, warning, `[outer]` | `team/glossary`, silent |

Recommendation: quote those descriptions in the fixtures, and have the spec say
what happens to a file with invalid frontmatter (not a concept? an error?).

## 2. Warning flag on the same-namespace qualified error

Clause: "If `namespace` is the containing bundle's own namespace: an error ... It does not resolve."
No warning is mentioned. Choice: `error: true, warning: false`. An error is
reported as an error and is not also counted as a warning. (The text never
calls this a "broken link", and broken links are what get the warning.)

## 3. Namespace source: federation entry or bundle manifest

Terms say both "Its namespace is the manifest's `namespace` value" and that the federation lists each bundle "with `namespace`".
Choice: I use the federation entry's `namespace` for lookup and ordering, and I do not read the
manifest. In every fixture the two agree. The text does not say what happens when they disagree.

## 4. Path resolution details (the text is silent on each)

- **Escaping the bundle root** (`../../x.md`): treated as "not inside the containing bundle", so broken.
- **No extension appended**: `./home` is looked up as the literal file `home` and does not resolve. Only §2's
  SHOULD covers extensions, and nothing says a consumer appends `.md`.
- **Target must be a concept**: "A concept file found there" is read as a file
  that passes the concept test (frontmatter with `type`, not `index.md` or `log.md`,
  not inside a nested bundle). Any other file is broken.
- Both lookups use normalised POSIX paths relative to the containing bundle's root.

## 5. `candidates` for step 3/4

Clause: "A warning MUST name every namespace where a concept with that `id` was found, in federation order".
Choice: every other held bundle is searched, not just up to the first hit, and `candidates`
lists all namespaces that matched at the deciding step, even when there is only one
(e.g. `["beta"]`). A match by another kind (an alias at step 3, say) is not listed. I took that
from INTERFACE.md: "at the deciding step".

## 6. Step 4 does not look at the containing bundle again

Step 4 says "in the other held bundles", so the containing bundle is excluded. Its aliases were
already tried at step 2.

## 7. Malformed `ai-xf://` values

The text says the remainder "is `namespace/id`", but not what happens when it isn't.
Choice: split at the first `/`. With no `/`, or with an empty id, the result is a broken qualified link
(a warning). The id part may contain further `/` characters and is matched literally.

## 8. Duplicate `precedence` entries / unknown entries

"A `precedence` list MUST NOT name a namespace twice", but no consumer behaviour is given.
Choice: tolerate it and keep the first occurrence. I do not report an error. Unknown namespaces and the
containing namespace are skipped, as §3 says.

## 9. Uniqueness assumed, not enforced

"Within one bundle, ids and aliases are unique." The bundle is scanned in sorted path order, and if
that is ever violated the first match wins. Uniqueness is not validated. Concepts without an `id`
cannot be targets. Non-string alias entries are ignored.

## 10. Frontmatter delimiting and other scan details

The frontmatter is the text between the first two lines equal to `---` (trailing whitespace
ignored), as the brief says. I do not require the file to start with `---`. Directories are walked
recursively, and hidden directories are walked too, since the text has no exclusions apart from nested bundles (§1).
A nested-bundle directory is skipped whether or not the federation lists it.

## 11. `from-concept` does not exist

Only path resolution uses `from-concept`, and it uses only its directory. The concept's existence is not checked.
(The c21 input originally named a file that does not exist in `zed`. The corrected
input, `concepts/reader.md`, was used for the final run, and the result is the same either way.)
